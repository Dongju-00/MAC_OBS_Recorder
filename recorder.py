#!/usr/bin/env python3
"""macOS / Chrome / OBS recording. Python standard library only."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

from obs_control import OBSRecorder


ROOT = Path(__file__).resolve().parent


def say(message):
    print(time.strftime('[%H:%M:%S] ')+message, flush=True)


def apple(script):
    result = subprocess.run(['/usr/bin/osascript', '-'], input=script,
                            capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise RuntimeError('macOS 제어 실패: '+result.stderr.strip())
    return result.stdout.strip()


def literal(text):
    # AppleScript string literal, never a shell command.
    return '"'+str(text).replace('\\', '\\\\').replace('"', '\\"').replace('\r', '\\r').replace('\n', '\\n')+'"'


def hotkey_script(spec):
    pieces = spec.lower().split('+')
    modifiers = {'command': 'command down', 'control': 'control down',
                 'option': 'option down', 'shift': 'shift down'}
    if (len(pieces) < 2 or len(pieces[-1]) != 1
            or not re.fullmatch('[a-z0-9]', pieces[-1])
            or any(x not in modifiers for x in pieces[:-1])
            or len(set(pieces[:-1])) != len(pieces[:-1])):
        raise ValueError('단축키 형식 예: control+shift+command+9')
    # macOS HIToolbox/Events.h kVK_ANSI_* values. A Unicode keystroke "9"
    # need not reach a recorder's global shortcut handler as a physical key.
    digit_codes = {'0': 29, '1': 18, '2': 19, '3': 20, '4': 21,
                   '5': 23, '6': 22, '7': 26, '8': 28, '9': 25}
    key = ('key code '+str(digit_codes[pieces[-1]]) if pieces[-1] in digit_codes
           else 'keystroke '+literal(pieces[-1]))
    return ('tell application "System Events" to '+key
            +' using {'+', '.join(modifiers[x] for x in pieces[:-1])+'}')


def validate_page(state, allow_loading=False):
    if not state.get('focused'):
        raise RuntimeError('대상 영상 탭이 선택되어 있지 않습니다.')
    if state.get('videoCount') != 1 or not state.get('videoId'):
        raise RuntimeError('제어 가능한 영상이 정확히 1개여야 합니다. --video-selector를 확인하세요.')
    if state.get('error') or state.get('playError'):
        raise RuntimeError('영상 재생 오류: '+str(state.get('playError') or state['error']))
    if not allow_loading and not state.get('playerReady'):
        raise RuntimeError('영상 로딩이 아직 완료되지 않았습니다.')
    duration = state.get('duration')
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise RuntimeError('유한한 영상 길이를 읽지 못했습니다. 재생 후 일시정지하고 점검하세요.')


class ProgressMonitor:
    def __init__(self, initial, stall_seconds=120):
        validate_page(initial)
        self.video_id = initial['videoId']
        self.stall_seconds = stall_seconds
        self.last_time = None
        self.last_progress = None

    def update(self, state, now):
        if state.get('videoId') != self.video_id:
            raise RuntimeError('녹화 중 영상이 먼저 바뀌었습니다. 자동 다음 재생을 끄세요.')
        validate_page(state)
        if state.get('ended'): return True
        current = state.get('time', 0)
        if self.last_time is None or current > self.last_time + 0.05:
            self.last_time, self.last_progress = current, now
        elif now - self.last_progress >= self.stall_seconds:
            raise RuntimeError('영상 진행이 오래 멈췄습니다. 재생 상태를 확인하세요.')
        return False


class Chrome:
    def __init__(self, selector='', player_selector=''):
        ids = apple('tell application "Google Chrome"\n'
                    'if (count of windows) is 0 then error "영상 탭을 먼저 여세요."\n'
                    'return (id of front window as text) & "," & (id of active tab of front window as text)\nend tell')
        self.window, self.tab = [int(x) for x in ids.split(',')]
        self.selector = selector
        self.player_selector = player_selector
        self.source = (ROOT/'browser.js').read_text(encoding='utf-8')

    def focus(self):
        apple(f'''tell application "Google Chrome"
set index of window id {self.window} to 1
set minimized of window id {self.window} to false
tell window id {self.window}
repeat with n from 1 to count of tabs
if ((id of tab n) as text) is {literal(self.tab)} then
set active tab index to n
exit repeat
end if
end repeat
end tell
activate
end tell''')

    def ensure_front(self, timeout=8):
        """Bring the target window forward and wait until Chrome really is frontmost."""
        deadline = time.monotonic()+timeout
        while True:
            self.focus()
            time.sleep(0.5)
            raw = apple(f'''tell application "System Events" to set frontApp to name of first application process whose frontmost is true
tell application "Google Chrome" to set frontWindow to (id of front window) as text
return frontApp & linefeed & frontWindow''')
            front_app, front_window = raw.split('\n')[:2]
            if front_app == 'Google Chrome' and int(front_window) == self.window: return
            if time.monotonic() > deadline:
                raise RuntimeError(f'크롬 대상 창을 앞으로 가져오지 못했습니다(앞 앱={front_app}, 앞 창={front_window}, '
                                   f'대상 창={self.window}). 다른 앱이 화면을 가리고 있는지 확인하세요.')

    def enter_fullscreen(self):
        """Fullscreen the player; returns whether it is fullscreen afterwards."""
        if self.call().get('fullscreen'): return True
        self.ensure_front()
        self.call('focus-player')
        # A real key press (F13: no site shortcut) gives the page user activation, which
        # requestFullscreen needs. Only the <video> itself goes fullscreen: black
        # background, no site layout around it.
        apple('tell application "System Events" to key code 105')
        time.sleep(0.3)
        self.call('fullscreen')
        time.sleep(1.5)
        return bool(self.call().get('fullscreen'))

    def exit_fullscreen(self):
        self.call('exit-fullscreen')
        time.sleep(1.5)

    def user_gesture(self):
        self.ensure_front()  # the Space key below goes to the frontmost app
        focused = self.call('focus-player')
        if not focused.get('playerHasFocus'):
            raise RuntimeError('플레이어에 키보드 포커스를 두지 못했습니다.')
        try:
            apple(f'''tell application "Google Chrome"
if ((id of front window) as text) is not {literal(self.window)} then error "대상 크롬 창이 앞에 없습니다."
if ((id of active tab of front window) as text) is not {literal(self.tab)} then error "대상 영상 탭이 앞에 없습니다."
end tell
tell application "System Events"
if (name of first application process whose frontmost is true) is not "Google Chrome" then error "크롬이 앞에 없습니다."
key code 49
end tell''')
            time.sleep(0.2)
        finally:
            current = self.call('pause')
        if current.get('userActivated') is False:
            raise RuntimeError('Chrome이 사용자 키 입력을 확인하지 못했습니다. 영상 재생 버튼을 한 번 직접 누르고 다시 실행하세요.')

    def call(self, action='inspect'):
        if action in ('prepare', 'play', 'next', 'focus-player', 'fullscreen'):
            before = self.call()
            if not before['focused']:
                raise RuntimeError('크롬 대상 탭이 선택되어 있지 않습니다: '
                                   +json.dumps(before['focusDetails'], ensure_ascii=False))
        javascript = '('+self.source+')('+','.join(json.dumps(x) for x in
            (action, self.selector, self.player_selector))+')'
        # Pin the tab by ID. Refuse to operate a new front tab accidentally.
        script = f'''tell application "Google Chrome"
set chosen to tab id {self.tab} of window id {self.window}
set frontWindow to (id of front window) as text
set frontTab to (id of active tab of window id {self.window}) as text
set focusedTab to (frontTab is {literal(self.tab)})
end tell
tell application "System Events" to set frontApp to (name of first application process whose frontmost is true) as text
set focusFlag to "0"
if (focusedTab is true) and (frontApp is "Google Chrome") then set focusFlag to "1"
tell application "Google Chrome"
set pageResult to execute chosen javascript {literal(javascript)}
end tell
return focusFlag & linefeed & frontApp & linefeed & (frontWindow as text) & linefeed & (frontTab as text) & linefeed & pageResult'''
        raw = apple(script)
        flag, front_app, front_window, front_tab, payload = raw.split('\n', 4)
        data = json.loads(payload)
        # Normalize native IDs here. The legacy AppleScript flag can disagree
        # with the values it reports (e.g. text IDs compared with numbers).
        # Window capture needs neither Chrome nor the target window in front, so other
        # apps and other Chrome windows may be. The target tab must be active in its window.
        data['focused'] = int(front_tab) == self.tab
        data['focusDetails'] = dict(frontApp=front_app, frontWindow=int(front_window),
                                    frontTab=int(front_tab), targetWindow=self.window, targetTab=self.tab,
                                    appleScriptFocused=flag == '1')
        if data.get('failure'):
            raise RuntimeError(data['failure'])
        return data


class EaseUS:
    def __init__(self, start, stop):
        self.start_script, self.stop_script = hotkey_script(start), hotkey_script(stop)
        self.active = False

    def start(self):
        # Mark first: if Apple Events returns an error after a delivered key,
        # the finally block still attempts to stop the recorder.
        self.active = True
        apple(self.start_script)

    def stop(self):
        if self.active:
            # A repeated toggle could start a fresh recording after a lost reply.
            self.active = False
            try:
                apple(self.stop_script)
            except Exception as error:
                raise RuntimeError('녹화 종료 전송 결과를 확인할 수 없습니다. 이지어스에서 직접 확인하세요: '+str(error)) from error

    def close(self):
        pass


def create_recorder(args):
    if args.recorder == 'easeus':
        return EaseUS(args.start_hotkey,args.stop_hotkey)
    recorder = OBSRecorder(port=args.obs_port)
    try:
        status = recorder.check()
        if status['recording']:
            raise RuntimeError('OBS가 이미 녹화 중입니다. 기존 녹화를 직접 종료한 뒤 실행하세요.')
        say(f"OBS 연결 확인: 장면={status['scene']}, 저장 폴더={status['recordDirectory']}")
        target = status.get('captureTarget')
        if target:
            say('OBS 윈도우 캡처 대상: '+target)
            if 'Chrome' not in target:
                say('경고: 윈도우 캡처 대상이 Chrome 창이 아닙니다. OBS 소스의 창 선택을 확인하세요.')
        return recorder
    except BaseException:
        recorder.close()
        raise


def bring_to_front(browser):
    browser.focus()
    time.sleep(0.5)


def verify_playback(browser):
    validate_page(browser.call())
    if browser.call().get('userActivated') is False:
        browser.user_gesture()
    try:
        browser.call('play')
        deadline = time.monotonic()+10
        while True:
            time.sleep(0.2)
            current = browser.call()
            validate_page(current)
            if current.get('paused') is False: return
            if time.monotonic() > deadline:
                raise RuntimeError('녹화 전 영상 재생 시작을 확인하지 못했습니다.')
    finally:
        browser.call('pause')


def wait_video(browser, previous_id=None, timeout=45):
    """Wait for actual media replacement, not merely a changed page URL."""
    deadline = time.monotonic()+timeout
    while True:
        try:
            current = browser.call()
        except RuntimeError:
            # Apple Events may fail transiently while a new document is loading.
            current = None
        if current is not None:
            if not current.get('focused'):
                raise RuntimeError('영상 로딩 중 대상 탭이 바뀌었습니다.')
            if (current.get('videoId') and current['videoId'] != previous_id
                    and current.get('playerReady') and (previous_id is None or not current.get('ended'))):
                validate_page(current)
                return current
        if time.monotonic() >= deadline:
            raise RuntimeError('새 영상 로딩을 확인하지 못했습니다. 다음 버튼과 플레이어를 점검하세요.')
        time.sleep(0.5)


def record_one(browser, recorder, args):
    initial = browser.call()
    validate_page(initial)
    verify_playback(browser)
    browser.call('prepare')
    deadline = time.monotonic()+30
    while True:
        ready = browser.call()
        validate_page(ready, allow_loading=True)
        if ready['videoId'] != initial['videoId']:
            raise RuntimeError('녹화 준비 중 영상이 바뀌었습니다.')
        if (ready.get('playerReady') and not ready.get('seeking')
                and ready.get('time', 999) <= 0.5 and ready.get('readyState', 0) >= 2):
            break
        if time.monotonic() > deadline:
            raise RuntimeError('영상 처음 위치의 로딩을 기다리다가 중단했습니다.')
        time.sleep(0.5)
    fullscreen = not args.no_fullscreen
    try:
        bring_to_front(browser)
        if fullscreen and not browser.enter_fullscreen():
            say('전체화면을 확인하지 못했습니다. 일반 화면으로 녹화합니다.')
        say('영상 녹화를 시작합니다.')
        recorder.start()
        time.sleep(args.countdown)
        bring_to_front(browser)
        monitor = ProgressMonitor(initial, args.stall_seconds)
        monitor.update(browser.call(), time.monotonic())
        browser.call('play')
        started = time.monotonic()
        last_log = started
        while True:
            current = browser.call()
            now = time.monotonic()
            if monitor.update(current, now): break
            if now-started >= args.video_timeout:
                raise RuntimeError('영상당 최대 대기시간을 넘겼습니다.')
            if now-last_log >= 60:
                say(f"녹화 진행 {int(current['time'])} / {int(current['duration'])}초")
                last_log = now
            time.sleep(0.5)
    finally:
        try:
            browser.call('pause')
        except Exception as error:
            say('영상 일시정지 확인 실패: '+str(error))
        try:
            saved_path = recorder.stop()
            if saved_path: say('영상 녹화 파일 저장 확인: '+saved_path)
        finally:
            if fullscreen:
                try: browser.exit_fullscreen()
                except Exception as error: say('전체화면 해제 확인 실패: '+str(error))

    return initial['videoId']


def run_videos(browser, recorder, args):
    for index in range(args.max_videos):
        recorded_id = record_one(browser, recorder, args)
        if index+1 == args.max_videos: return
        time.sleep(args.save_wait)
        current = browser.call()
        if not current.get('focused'):
            raise RuntimeError('다음 영상 이동 전에 대상 탭이 바뀌었습니다.')
        if current.get('videoId') != recorded_id:
            raise RuntimeError('저장 대기 중 영상이 바뀌었습니다. 자동 다음 재생을 끄세요.')
        if current.get('nextCount', 0) == 0:
            say('사용 가능한 다음 영상 버튼이 없어 종료합니다.')
            return
        if current['nextCount'] != 1:
            raise RuntimeError('다음 영상 버튼이 여러 개입니다. --video-next-selector를 지정하세요.')
        previous_id = current['videoId']
        browser.call('next')
        wait_video(browser, previous_id, args.video_load_timeout)


def main():
    parser = argparse.ArgumentParser(description='macOS / Chrome / OBS 동영상 자동 녹화')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='현재 영상과 다음 버튼 점검')
    mode.add_argument('--diagnose', action='store_true', help='영상과 다음 버튼 후보 진단')
    mode.add_argument('--run', action='store_true', help='현재 영상부터 녹화하고 다음 버튼으로 이동')
    mode.add_argument('--test-recording', '--test-hotkey', dest='test_recording', action='store_true',
                      help='현재 OBS 장면을 10초 시험 녹화. Chrome 조작 없음')
    mode.add_argument('--check-obs', action='store_true', help='OBS 연결·장면·저장 폴더 점검')
    parser.add_argument('--recorder', choices=('obs','easeus'), default='obs')
    parser.add_argument('--obs-port', type=int, default=4455)
    parser.add_argument('--max-videos', type=int, default=1, help='현재 영상을 포함한 총 녹화 수 (기본 1)')
    parser.add_argument('--video-next-selector', default='', help='다음 영상 버튼의 CSS 선택자')
    parser.add_argument('--video-selector', default='', help='녹화할 HTML video의 CSS 선택자')
    parser.add_argument('--video-timeout', type=float, default=14400, help='영상당 최대 대기 초 (기본 14400)')
    parser.add_argument('--video-load-timeout', type=float, default=45, help='새 영상 로딩 대기 초 (기본 45)')
    parser.add_argument('--no-fullscreen', action='store_true')
    parser.add_argument('--start-hotkey', default='command+9')
    parser.add_argument('--stop-hotkey', default='command+9')
    parser.add_argument('--countdown', type=float, default=None)
    parser.add_argument('--save-wait', type=float, default=10)
    parser.add_argument('--stall-seconds', type=float, default=120)
    args = parser.parse_args()
    if args.countdown is None: args.countdown = 0 if args.recorder == 'obs' else 6
    if sys.platform != 'darwin': parser.error('macOS에서만 실제 제어할 수 있습니다.')
    if (args.max_videos < 1 or not 1 <= args.obs_port <= 65535
            or not math.isfinite(args.countdown) or args.countdown < 0
            or any(not math.isfinite(x) or x <= 0 for x in
                   (args.save_wait, args.stall_seconds, args.video_timeout, args.video_load_timeout))):
        parser.error('개수·대기시간은 양수이며 포트는 1~65535여야 합니다.')
    browser = recorder = awake = None
    try:
        if args.check_obs:
            recorder = OBSRecorder(port=args.obs_port)
            print(json.dumps(recorder.check(), ensure_ascii=False, indent=2))
            return 0
        if args.test_recording:
            recorder = create_recorder(args)
            say('10초 시험 녹화를 시작합니다. 재생 앱은 직접 조작하세요.')
            try:
                recorder.start()
                time.sleep(10)
            finally:
                path = recorder.stop()
            if path: say('시험 녹화 파일 저장 확인: '+path)
            return 0
        browser = Chrome(args.video_next_selector, args.video_selector)
        bring_to_front(browser)
        if args.check or args.diagnose:
            status = browser.call('diagnose' if args.diagnose else 'inspect')
            print(json.dumps(status, ensure_ascii=False, indent=2))
            if args.check: validate_page(status)
            return 0
        wait_video(browser, timeout=args.video_load_timeout)
        recorder = create_recorder(args)
        awake = subprocess.Popen(['/usr/bin/caffeinate', '-di', '-w', str(__import__('os').getpid())])
        run_videos(browser, recorder, args)
        say('실행 종료. 저장된 영상과 소리를 확인하세요.')
        return 0
    except KeyboardInterrupt:
        say('사용자가 중단했습니다.')
        return 130
    except Exception as error:
        say('중단: '+str(error))
        return 1
    finally:
        if recorder:
            if recorder.active:
                try: recorder.stop()
                except Exception as error: say('녹화 종료 확인 실패. OBS에서 직접 확인하세요: '+str(error))
            recorder.close()
        if awake: awake.terminate()


if __name__ == '__main__':
    raise SystemExit(main())
