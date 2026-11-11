"""Local OBS WebSocket 5 recording control; Python standard library only."""
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time


AUDIO_INPUT_KIND = 'coreaudio_input_capture'
BLACKHOLE_NAME = 'BlackHole 2ch'
BLACKHOLE_DEVICE_ID = 'BlackHole2ch_UID'


class OBSConnectionError(RuntimeError):
    pass


class OBSRequestError(RuntimeError):
    pass


class WebSocket:
    """Small RFC 6455 JSON client restricted to the local OBS server."""
    LIMIT = 1024*1024

    def __init__(self, port=4455, timeout=10):
        self.timeout = timeout
        self.socket = None
        self.deadline = time.monotonic()+timeout
        try:
            self.socket = socket.create_connection(('127.0.0.1',port),timeout=timeout)
            key = base64.b64encode(os.urandom(16)).decode()
            self.socket.sendall((f'GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n'
                'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
            header = bytearray()
            while not header.endswith(b'\r\n\r\n'):
                if len(header) >= 16384: raise OBSConnectionError('OBS HTTP 응답이 너무 큽니다.')
                header.extend(self._exact(1))
            lines = header.decode('latin1').split('\r\n')
            fields = {name.lower():value.strip() for line in lines[1:] if ':' in line
                      for name,value in [line.split(':',1)]}
            expected = base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            if (len(lines[0].split()) < 2 or lines[0].split()[1] != '101' or
                    fields.get('sec-websocket-accept','') != expected):
                raise OBSConnectionError('OBS WebSocket 연결 응답이 올바르지 않습니다.')
        except BaseException:
            self.close()
            raise

    def _exact(self, count):
        data = bytearray()
        while len(data) < count:
            remaining = self.deadline-time.monotonic()
            if remaining <= 0: raise OBSConnectionError('OBS 응답 대기시간을 넘겼습니다.')
            self.socket.settimeout(remaining)
            part = self.socket.recv(count-len(data))
            if not part: raise OBSConnectionError('OBS 연결이 종료되었습니다.')
            data.extend(part)
        return bytes(data)

    def _send(self, opcode, payload):
        mask = os.urandom(4)
        length = len(payload)
        if length > self.LIMIT: raise OBSConnectionError('OBS 요청이 너무 큽니다.')
        if length < 126: header = bytes([0x80|opcode,0x80|length])
        elif length < 65536: header = bytes([0x80|opcode,0x80|126])+struct.pack('!H',length)
        else: header = bytes([0x80|opcode,0x80|127])+struct.pack('!Q',length)
        self.socket.settimeout(self.timeout)
        self.socket.sendall(header+mask+bytes(value^mask[index%4] for index,value in enumerate(payload)))

    def send(self, message):
        self._send(1,json.dumps(message).encode())

    def receive(self, deadline=None):
        self.deadline = deadline or time.monotonic()+self.timeout
        message = bytearray()
        started = False
        while True:
            first, second = self._exact(2)
            opcode, final = first & 15, bool(first & 128)
            if first & 112 or second & 128: raise OBSConnectionError('지원하지 않는 OBS 프레임입니다.')
            length = second & 127
            if length == 126: length = struct.unpack('!H',self._exact(2))[0]
            elif length == 127: length = struct.unpack('!Q',self._exact(8))[0]
            if length > self.LIMIT or len(message)+length > self.LIMIT:
                raise OBSConnectionError('OBS 응답이 너무 큽니다.')
            if opcode >= 8 and (not final or length > 125):
                raise OBSConnectionError('잘못된 OBS 제어 프레임입니다.')
            payload = self._exact(length)
            if opcode == 8:
                code = struct.unpack('!H',payload[:2])[0] if len(payload) >= 2 else 1000
                raise OBSConnectionError(f'OBS 연결 종료 (code={code}). 인증 비밀번호와 서버 설정을 확인하세요.')
            if opcode == 9:
                self._send(10,payload)
                continue
            if opcode == 10: continue
            if opcode == 1 and not started: started = True
            elif opcode != 0 or not started: raise OBSConnectionError('OBS JSON 프레임을 확인할 수 없습니다.')
            message.extend(payload)
            if final: return json.loads(message.decode())

    def close(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None


class OBSConnection:
    def __init__(self, port=4455, password=None):
        self.port = port
        self.password = password if password is not None else os.environ.get('OBS_WEBSOCKET_PASSWORD','')
        self.transport = None
        self.sequence = 0
        try:
            self.transport = WebSocket(port)
            hello = self.transport.receive()
            if hello.get('op') != 0: raise OBSConnectionError('OBS 28 이상 / WebSocket 5 서버가 필요합니다.')
            data = dict(rpcVersion=1,eventSubscriptions=0)
            auth = hello.get('d',{}).get('authentication')
            if auth:
                if not self.password:
                    if not sys.stdin.isatty():
                        raise OBSConnectionError('OBS_WEBSOCKET_PASSWORD 환경 변수에 OBS 서버 비밀번호를 설정하세요.')
                    self.password = getpass.getpass('OBS WebSocket 비밀번호: ')
                secret = base64.b64encode(hashlib.sha256((self.password+auth['salt']).encode()).digest()).decode()
                data['authentication'] = base64.b64encode(hashlib.sha256((secret+auth['challenge']).encode()).digest()).decode()
            self.transport.send(dict(op=1,d=data))
            if self.transport.receive().get('op') != 2: raise OBSConnectionError('OBS 인증에 실패했습니다.')
        except BaseException as error:
            self.close()
            if isinstance(error,(KeyboardInterrupt,SystemExit,OBSConnectionError)):
                raise
            if isinstance(error,OSError):
                raise OBSConnectionError('OBS 연결 실패. OBS를 실행하고 도구 → WebSocket 서버 설정에서 '
                                         f'서버를 활성화하세요 (127.0.0.1:{port}).') from error
            raise OBSConnectionError('OBS 연결/인증 응답을 확인하지 못했습니다.') from error

    def request(self, kind, data=None):
        if self.transport is None or self.transport.socket is None:
            raise OBSConnectionError('OBS 연결을 다시 열어야 합니다.')
        self.sequence += 1
        request_id = str(self.sequence)
        try:
            self.transport.send(dict(op=6,d=dict(requestType=kind,requestId=request_id,requestData=data or {})))
            deadline = time.monotonic()+self.transport.timeout
            while True:
                response = self.transport.receive(deadline)
                if response.get('op') != 7 or response.get('d',{}).get('requestId') != request_id: continue
                result = response['d']
                status = result.get('requestStatus',{})
                if not status.get('result'):
                    raise OBSRequestError(f"OBS {kind} 실패 (code={status.get('code')}): {status.get('comment','')}")
                return result.get('responseData',{})
        except OBSRequestError:
            raise  # A complete negative response leaves the connection synchronized.
        except BaseException as error:
            # A partial frame cannot be resumed after an interrupt. Never let
            # cleanup send commands over a stream with an unknown frame boundary.
            self.close()
            if isinstance(error,(KeyboardInterrupt,SystemExit,OBSConnectionError)):
                raise
            raise OBSConnectionError('OBS 통신/응답 형식 오류가 발생했습니다.') from error

    def close(self):
        if self.transport is not None: self.transport.close()


class OBSRecorder:
    def __init__(self, port=4455, password=None):
        self.connection = OBSConnection(port,password)
        self.active = False
        self.last_output_path = None

    def _is_blackhole(self, name):
        settings = self.connection.request('GetInputSettings',dict(inputName=name)).get('inputSettings',{})
        if settings.get('device_id') != BLACKHOLE_DEVICE_ID: return False
        return not self.connection.request('GetInputMute',dict(inputName=name)).get('inputMuted')

    def _window_capture_target(self, enabled):
        """Describe an enabled macOS capture source set to a single window, if any."""
        for item in enabled:
            if item.get('inputKind') != 'screen_capture': continue
            settings = self.connection.request('GetInputSettings',dict(inputName=item['sourceName'])).get('inputSettings',{})
            if settings.get('type') == 1:
                return f"{settings.get('owner_name','?')} - {settings.get('window_name','?')}"
        return None

    def check(self):
        status = self.connection.request('GetRecordStatus')
        scene = self.connection.request('GetCurrentProgramScene')['currentProgramSceneName']
        sources = self.connection.request('GetSceneItemList',dict(sceneName=scene)).get('sceneItems',[])
        enabled = [item for item in sources if item.get('sceneItemEnabled')]
        if not any(item.get('inputKind') != AUDIO_INPUT_KIND for item in enabled):
            raise RuntimeError('OBS 현재 장면에 활성화된 캡처 소스가 없습니다. macOS 화면 캡처 소스를 추가하세요.')
        if not any(self._is_blackhole(item['sourceName']) for item in enabled
                   if item.get('inputKind') == AUDIO_INPUT_KIND):
            raise RuntimeError('OBS 현재 장면에 소리 소스가 없습니다. 소스 → + → macOS 오디오 입력 캡처를 추가하고 '
                               f'장치를 {BLACKHOLE_NAME}로 선택하세요 (음소거 해제).')
        directory = self.connection.request('GetRecordDirectory').get('recordDirectory')
        return dict(scene=scene,recording=status.get('outputActive',False),recordDirectory=directory,
                    captureTarget=self._window_capture_target(enabled))

    def start(self):
        if self.connection.request('GetRecordStatus').get('outputActive'):
            raise RuntimeError('OBS가 이미 녹화 중입니다. 기존 녹화를 직접 종료한 뒤 실행하세요.')
        self.last_output_path = None
        self.active = True  # An unacknowledged start still needs a cleanup attempt.
        try:
            self.connection.request('StartRecord')
        except OBSRequestError:
            self.active = False
            raise
        deadline = time.monotonic()+10
        while True:
            status = self.connection.request('GetRecordStatus')
            if status.get('outputActive') and not status.get('outputPaused'): return
            if time.monotonic() > deadline: raise RuntimeError('OBS 녹화 시작 상태를 확인하지 못했습니다.')
            time.sleep(0.2)

    def stop(self):
        if not self.active: return None
        try:
            result = self.connection.request('StopRecord')
        except OBSConnectionError:
            # StopRecord is explicit, never a toggle: a retry cannot start a recording.
            port, password = self.connection.port, self.connection.password
            self.connection.close()
            self.connection = OBSConnection(port,password)
            if not self.connection.request('GetRecordStatus').get('outputActive'):
                self.active = False
                raise RuntimeError('OBS 녹화는 종료됐지만 저장 경로 응답이 유실됐습니다. OBS 저장 폴더를 확인하세요.')
            result = self.connection.request('StopRecord')
        deadline = time.monotonic()+10
        while self.connection.request('GetRecordStatus').get('outputActive'):
            if time.monotonic() > deadline: raise RuntimeError('OBS 녹화 종료를 확인하지 못했습니다.')
            time.sleep(0.2)
        self.active = False
        path = result.get('outputPath','')
        if not path or not Path(path).is_file() or Path(path).stat().st_size <= 0:
            raise RuntimeError('OBS 저장 파일을 확인하지 못했습니다. 다음 영상으로 이동하지 않습니다.')
        self.last_output_path = path
        return path

    def close(self):
        self.connection.close()
