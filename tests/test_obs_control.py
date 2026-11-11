import base64
import hashlib
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch

import obs_control as obs
import recorder as app


class FakeOBS:
    """A protocol-speaking server over a real local socket pair."""
    def __init__(self, output, password=None, active=False, reject_start=False, save=True, engine=None, bad_start=False):
        self.client, self.server = socket.socketpair()
        self.server.settimeout(3)
        self.output = str(output)
        self.password = password
        self.engine = engine if engine is not None else dict(active=active)
        self.bad_start = bad_start
        self.reject_start = reject_start
        self.save = save
        self.requests = []
        self.masked = []
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    @property
    def active(self): return self.engine['active']

    @active.setter
    def active(self,value): self.engine['active']=value

    def exact(self, count):
        data = bytearray()
        while len(data) < count:
            chunk = self.server.recv(count-len(data))
            if not chunk: raise EOFError()
            data.extend(chunk)
        return bytes(data)

    def send(self, message, opcode=1):
        payload = json.dumps(message).encode() if opcode == 1 and not isinstance(message,bytes) else message
        if len(payload) < 126: header = bytes([0x80|opcode, len(payload)])
        else: header = bytes([0x80|opcode, 126])+struct.pack('!H', len(payload))
        self.server.sendall(header+payload)

    def receive(self):
        first, second = self.exact(2)
        length = second & 127
        if length == 126: length = struct.unpack('!H', self.exact(2))[0]
        elif length == 127: length = struct.unpack('!Q', self.exact(8))[0]
        masked = bool(second & 128)
        self.masked.append(masked)
        mask = self.exact(4) if masked else b''
        data = self.exact(length)
        if masked: data = bytes(value ^ mask[index%4] for index,value in enumerate(data))
        if first & 15 == 8: raise EOFError()
        if first & 15 == 10: return self.receive()  # pong
        return json.loads(data)

    def run(self):
        try:
            headers = bytearray()
            while not headers.endswith(b'\r\n\r\n'): headers.extend(self.exact(1))
            key = next(line.split(':',1)[1].strip() for line in headers.decode().split('\r\n')
                       if line.lower().startswith('sec-websocket-key:'))
            accept = base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            self.server.sendall(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n'
                                 'Connection: Upgrade\r\nSec-WebSocket-Accept: '+accept+'\r\n\r\n').encode())
            hello = dict(rpcVersion=1)
            if self.password is not None: hello['authentication'] = dict(salt='salt', challenge='challenge')
            self.send(dict(op=0,d=hello))
            identify = self.receive()
            if self.password is not None:
                secret = base64.b64encode(hashlib.sha256((self.password+'salt').encode()).digest()).decode()
                expected = base64.b64encode(hashlib.sha256((secret+'challenge').encode()).digest()).decode()
                if identify['d'].get('authentication') != expected:
                    self.send(struct.pack('!H',4009),opcode=8)
                    return
            self.send(dict(op=2,d=dict(negotiatedRpcVersion=1)))
            self.send(b'alive',opcode=9)
            while True:
                request = self.receive()['d']
                kind = request['requestType']
                self.requests.append(kind)
                result, data = True, {}
                if kind == 'GetRecordStatus': data = dict(outputActive=self.active,outputPaused=False)
                elif kind == 'GetCurrentProgramScene': data = dict(currentProgramSceneName='Video')
                elif kind == 'GetSceneItemList': data = dict(sceneItems=[dict(sourceName='Chrome',sceneItemEnabled=True),
                    dict(sourceName='Audio',sceneItemEnabled=True,inputKind='coreaudio_input_capture')])
                elif kind == 'GetInputSettings': data = dict(inputSettings=dict(device_id='BlackHole2ch_UID'))
                elif kind == 'GetInputMute': data = dict(inputMuted=False)
                elif kind == 'GetRecordDirectory': data = dict(recordDirectory=str(Path(self.output).parent))
                elif kind == 'StartRecord':
                    if self.reject_start: result = False
                    else: self.active = True
                    if self.bad_start:
                        self.send(b'\xff')
                        continue
                elif kind == 'StopRecord':
                    self.active = False
                    if self.save: Path(self.output).write_bytes(b'test-recording')
                    data = dict(outputPath=self.output)
                self.send(dict(op=7,d=dict(requestId=request['requestId'],requestType=kind,
                    requestStatus=dict(result=result,code=100 if result else 500,comment='start rejected'),responseData=data)))
        except (EOFError, ConnectionError, OSError):
            pass
        except BaseException as error:
            self.error = error
        finally:
            self.server.close()

    def __enter__(self):
        self.thread.start()
        self.patch = patch('obs_control.socket.create_connection',return_value=self.client)
        self.patch.start()
        return self

    def __exit__(self, *_):
        self.client.close()
        self.thread.join(3)
        self.patch.stop()
        if self.error: raise self.error


class OBSControlTests(unittest.TestCase):
    def test_connection_check_does_not_stop_existing_user_recording(self):
        with FakeOBS('/tmp/unused-obs-test.mkv',active=True) as server, \
             patch('recorder.sys.platform','darwin'), patch('recorder.sys.argv',['recorder.py','--check-obs']), \
             patch('builtins.print') as output, patch('recorder.say'), \
             patch('recorder.Chrome',side_effect=AssertionError('OBS checks must not control Chrome')):
            self.assertEqual(app.main(),0)
            self.assertTrue(json.loads(output.call_args.args[0])['recording'])
        self.assertTrue(server.active)
        self.assertNotIn('StartRecord',server.requests)
        self.assertNotIn('StopRecord',server.requests)

    def test_check_requires_unmuted_blackhole_source(self):
        with FakeOBS('/tmp/unused-obs-test.mkv') as server:
            recorder = obs.OBSRecorder()
            self.assertEqual(recorder.check()['scene'],'Video')
            original = recorder.connection.request
            def replace(kind,data=None):
                if kind == 'GetInputSettings': return dict(inputSettings=dict(device_id='BuiltInMic'))
                return original(kind,data)
            with patch.object(recorder.connection,'request',side_effect=replace):
                with self.assertRaisesRegex(RuntimeError,'BlackHole 2ch'):
                    recorder.check()
            recorder.close()

    def test_interrupted_start_response_reconnects_before_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'recover.mkv'
            with FakeOBS(output) as first, FakeOBS(output,engine=first.engine) as recovery, \
                 patch('obs_control.socket.create_connection',side_effect=[first.client,recovery.client]):
                recorder=obs.OBSRecorder()
                original=obs.WebSocket._exact
                interrupted=False
                def receive(transport,count):
                    nonlocal interrupted
                    data=original(transport,count)
                    if first.requests and first.requests[-1]=='StartRecord' and not interrupted:
                        interrupted=True
                        raise KeyboardInterrupt()
                    return data
                try:
                    with patch.object(obs.WebSocket,'_exact',receive):
                        with self.assertRaises(KeyboardInterrupt): recorder.start()
                    self.assertTrue(recorder.active)
                    self.assertEqual(recorder.stop(),str(output))
                    self.assertFalse(first.active)
                finally: recorder.close()
            self.assertEqual(first.requests.count('StartRecord'),1)
            self.assertEqual(recovery.requests.count('StopRecord'),1)

    def test_malformed_start_response_reconnects_for_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'decode-error.mkv'
            with FakeOBS(output,bad_start=True) as first, FakeOBS(output,engine=first.engine) as recovery, \
                 patch('obs_control.socket.create_connection',side_effect=[first.client,recovery.client]):
                recorder=obs.OBSRecorder()
                try:
                    with self.assertRaises(obs.OBSConnectionError): recorder.start()
                    self.assertEqual(recorder.stop(),str(output))
                    self.assertFalse(first.active)
                finally: recorder.close()

    def test_default_cli_tests_obs_without_hotkeys_or_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'test.mkv'
            with FakeOBS(output) as server, patch('recorder.sys.platform','darwin'), \
                 patch('recorder.sys.argv',['recorder.py','--test-recording']), patch('recorder.say'), \
                 patch('recorder.time.sleep'), patch('recorder.apple',side_effect=AssertionError('OBS control must not send hotkeys')), \
                 patch('recorder.Chrome',side_effect=AssertionError('Scene-only recording tests must not navigate Chrome')):
                self.assertEqual(app.main(),0)
            self.assertGreater(output.stat().st_size,0)
            self.assertEqual(server.requests.count('StartRecord'),1)
            self.assertEqual(server.requests.count('StopRecord'),1)

    def test_interrupt_during_test_still_stops_and_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'interrupted.mkv'
            with FakeOBS(output) as server, patch('recorder.sys.platform','darwin'), \
                 patch('recorder.sys.argv',['recorder.py','--test-recording']), patch('recorder.say'), \
                 patch('recorder.time.sleep',side_effect=KeyboardInterrupt):
                self.assertEqual(app.main(),130)
            self.assertTrue(output.is_file())
            self.assertEqual(server.requests.count('StopRecord'),1)

    def test_recording_is_confirmed_and_saved_path_returned(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'video.mkv'
            with FakeOBS(target,password='secret') as server:
                recorder = obs.OBSRecorder(password='secret')
                try:
                    recorder.check()
                    recorder.start()
                    self.assertTrue(recorder.active)
                    self.assertEqual(recorder.stop(),str(target))
                    self.assertFalse(recorder.active)
                    self.assertGreater(target.stat().st_size,0)
                    recorder.stop()
                finally: recorder.close()
            self.assertEqual(server.requests.count('StartRecord'),1)
            self.assertEqual(server.requests.count('StopRecord'),1)
            self.assertTrue(all(server.masked))

    def test_existing_recording_is_never_stopped(self):
        with FakeOBS('/tmp/unused-obs-test.mkv',active=True) as server:
            recorder = obs.OBSRecorder()
            try:
                with self.assertRaisesRegex(RuntimeError,'already recording'): recorder.start()
                recorder.stop()
            finally: recorder.close()
        self.assertNotIn('StartRecord',server.requests)
        self.assertNotIn('StopRecord',server.requests)

    def test_start_failure_does_not_claim_recording(self):
        with FakeOBS('/tmp/unused-obs-test.mkv',reject_start=True) as server:
            recorder = obs.OBSRecorder()
            try:
                with self.assertRaises(RuntimeError): recorder.start()
                self.assertFalse(recorder.active)
                recorder.stop()
            finally: recorder.close()
        self.assertNotIn('StopRecord',server.requests)

    def test_missing_saved_file_is_failure(self):
        with tempfile.TemporaryDirectory() as folder, FakeOBS(Path(folder)/'missing.mkv',save=False):
            recorder=obs.OBSRecorder()
            try:
                recorder.start()
                with self.assertRaisesRegex(RuntimeError,'saved recording file'):
                    recorder.stop()
                self.assertFalse(recorder.active)
            finally: recorder.close()

    def test_wrong_password_fails_without_starting(self):
        with FakeOBS('/tmp/unused-obs-test.mkv',password='secret') as server:
            with self.assertRaisesRegex(RuntimeError,'authentication|4009'):
                obs.OBSRecorder(password='wrong')
        self.assertEqual(server.requests,[])
