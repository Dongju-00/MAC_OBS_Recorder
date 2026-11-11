#!/usr/bin/env python3
"""Automatic macOS video recording with OBS and Chrome next-video navigation.

Records each video to a separate file and advances after verifying the save.
Python standard library only.
"""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

from obs_control import OBSRecorder
from site_profiles import load_profile, save_profile, site_origin


ROOT = Path(__file__).resolve().parent


def say(message):
    print(time.strftime('[%H:%M:%S] ')+message, flush=True)


def apple(script):
    result = subprocess.run(['/usr/bin/osascript', '-'], input=script,
                            capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise RuntimeError('macOS automation failed: '+result.stderr.strip())
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
        raise ValueError('Example shortcut format: control+shift+command+9')
    # macOS HIToolbox/Events.h kVK_ANSI_* values. Text-based `keystroke`
    # may synthesize extra modifiers with a non-Latin input source (observed:
    # Shift+N became Alt+Shift+N under Korean). Send physical shortcut keys.
    key_codes = {'a': 0, 's': 1, 'd': 2, 'f': 3, 'h': 4, 'g': 5,
                 'z': 6, 'x': 7, 'c': 8, 'v': 9, 'b': 11, 'q': 12,
                 'w': 13, 'e': 14, 'r': 15, 'y': 16, 't': 17,
                 'o': 31, 'u': 32, 'i': 34, 'p': 35, 'l': 37,
                 'j': 38, 'k': 40, 'n': 45, 'm': 46,
                 '0': 29, '1': 18, '2': 19, '3': 20, '4': 21,
                 '5': 23, '6': 22, '7': 26, '8': 28, '9': 25}
    key = 'key code '+str(key_codes[pieces[-1]])
    return ('tell application "System Events" to '+key
            +' using {'+', '.join(modifiers[x] for x in pieces[:-1])+'}')


def validate_page(state, allow_loading=False):
    if not state.get('focused'):
        raise RuntimeError('The target video tab is not selected.')
    if state.get('videoCount') != 1 or not state.get('videoId'):
        raise RuntimeError('Exactly one controllable video is required. Check --video-selector.')
    if state.get('error') or state.get('playError'):
        raise RuntimeError('Video playback error: '+str(state.get('playError') or state['error']))
    if not allow_loading and not state.get('playerReady'):
        raise RuntimeError('The video has not finished loading.')
    duration = state.get('duration')
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise RuntimeError('Cannot read a finite video duration. Play and pause the video, then check again.')


class ProgressMonitor:
    def __init__(self, initial, stall_seconds=120):
        validate_page(initial)
        self.video_id = initial['videoId']
        self.stall_seconds = stall_seconds
        self.last_time = None
        self.last_progress = None

    def update(self, state, now):
        if state.get('videoId') != self.video_id:
            raise RuntimeError('The video changed during recording. Disable automatic next-video playback.')
        validate_page(state)
        if state.get('ended'): return True
        current = state.get('time', 0)
        if self.last_time is None or current > self.last_time + 0.05:
            self.last_time, self.last_progress = current, now
        elif now - self.last_progress >= self.stall_seconds:
            raise RuntimeError('Video progress has stalled. Check playback.')
        return False


class Chrome:
    def __init__(self, selector='', player_selector=''):
        ids = apple('tell application "Google Chrome"\n'
                    'if (count of windows) is 0 then error "Open a video tab first."\n'
                    'return (id of front window as text) & "," & (id of active tab of front window as text)\nend tell')
        self.window, self.tab = [int(x) for x in ids.split(',')]
        self.selector = selector
        self.player_selector = player_selector
        self.next_hotkey = ''
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
                raise RuntimeError(f'Cannot bring the target Chrome window forward (front app={front_app}, front window={front_window}, '
                                   f'target window={self.window}). Check whether another app is covering it.')

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
            raise RuntimeError('Cannot focus the video player for keyboard input.')
        try:
            apple(f'''tell application "Google Chrome"
if ((id of front window) as text) is not {literal(self.window)} then error "The target Chrome window is not in front."
if ((id of active tab of front window) as text) is not {literal(self.tab)} then error "The target video tab is not in front."
end tell
tell application "System Events"
if (name of first application process whose frontmost is true) is not "Google Chrome" then error "Chrome is not in front."
key code 49
end tell''')
            time.sleep(0.2)
        finally:
            current = self.call('pause')
        if current.get('userActivated') is False:
            raise RuntimeError('Chrome did not confirm user input. Click the video play button once and try again.')

    def call(self, action='inspect'):
        if action == 'next' and getattr(self, 'next_hotkey', ''):
            self.ensure_front()
            if not self.call().get('focused'):
                raise RuntimeError('The target tab changed before next-video navigation.')
            apple(hotkey_script(self.next_hotkey))
            return {}  # Navigation may temporarily make the document unavailable.
        if action in ('prepare', 'play', 'next', 'focus-player', 'fullscreen'):
            before = self.call()
            if not before['focused']:
                raise RuntimeError('The target Chrome tab is not selected: '
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
                raise RuntimeError('Cannot confirm delivery of the stop shortcut. Check EaseUS directly: '+str(error)) from error

    def close(self):
        pass


def create_recorder(args):
    if args.recorder == 'easeus':
        return EaseUS(args.start_hotkey,args.stop_hotkey)
    recorder = OBSRecorder(port=args.obs_port)
    try:
        status = recorder.check()
        if status['recording']:
            raise RuntimeError('OBS is already recording. Stop the existing recording manually before continuing.')
        say(f"OBS connected: scene={status['scene']}, recording directory={status['recordDirectory']}")
        target = status.get('captureTarget')
        if target:
            say('OBS window capture target: '+target)
            if 'Chrome' not in target:
                say('Warning: the window capture target is not Chrome. Check the OBS source window selection.')
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
                raise RuntimeError('Could not confirm video playback before recording.')
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
                raise RuntimeError('The target tab changed while the video was loading.')
            if (current.get('videoId') and current['videoId'] != previous_id
                    and current.get('playerReady') and (previous_id is None or not current.get('ended'))):
                validate_page(current)
                return current
        if time.monotonic() >= deadline:
            raise RuntimeError('Could not confirm new video loading. Check the next control and player.')
        time.sleep(0.5)


def record_one(browser, recorder, args, sample_seconds=None):
    initial = browser.call()
    validate_page(initial)
    if (getattr(browser, 'profile_origin', None)
            and site_origin(initial['url']) != browser.profile_origin):
        raise RuntimeError('Navigation reached another site. Run --test on that site first.')
    verify_playback(browser)
    browser.call('prepare')
    deadline = time.monotonic()+30
    while True:
        ready = browser.call()
        validate_page(ready, allow_loading=True)
        if ready['videoId'] != initial['videoId']:
            raise RuntimeError('The video changed while preparing to record.')
        if (ready.get('playerReady') and not ready.get('seeking')
                and ready.get('time', 999) <= 0.5 and ready.get('readyState', 0) >= 2):
            break
        if time.monotonic() > deadline:
            raise RuntimeError('Timed out waiting for the beginning of the video to load.')
        time.sleep(0.5)
    fullscreen = not args.no_fullscreen
    try:
        bring_to_front(browser)
        if fullscreen and not browser.enter_fullscreen():
            say('Could not confirm fullscreen. Recording in the normal player view.')
        say('Starting video recording.')
        recorder.start()
        time.sleep(args.countdown)
        bring_to_front(browser)
        monitor = ProgressMonitor(initial, args.stall_seconds)
        playback_start = browser.call()
        monitor.update(playback_start, time.monotonic())
        browser.call('play')
        started = time.monotonic()
        last_log = started
        while True:
            current = browser.call()
            now = time.monotonic()
            if monitor.update(current, now): break
            if sample_seconds is not None and now-started >= sample_seconds:
                if current.get('time', 0) <= playback_start.get('time', 0) + 0.05:
                    raise RuntimeError('Test playback did not advance during recording.')
                break
            if now-started >= args.video_timeout:
                raise RuntimeError('The per-video timeout was exceeded.')
            if now-last_log >= 60:
                say(f"Recording progress: {int(current['time'])} / {int(current['duration'])} seconds")
                last_log = now
            time.sleep(0.5)
    finally:
        try:
            browser.call('pause')
        except Exception as error:
            say('Could not confirm video pause: '+str(error))
        try:
            saved_path = recorder.stop()
            if saved_path: say('Recording file verified: '+saved_path)
        finally:
            if fullscreen:
                try: browser.exit_fullscreen()
                except Exception as error: say('Could not confirm fullscreen exit: '+str(error))

    return initial['videoId']


def apply_site_profile(browser, args):
    url = browser.call()['url']
    profile = load_profile(url)
    if not profile: return
    browser.profile_origin = site_origin(url)
    if not args.video_selector:
        browser.player_selector = profile['video_selector']
    if not args.video_next_selector:
        browser.selector = profile['video_next_selector']
        browser.next_hotkey = profile['next_hotkey']
        browser.profile_selector = bool(browser.selector) and not browser.next_hotkey
    say('Loaded the tested site profile. Run --test to update it.')


def navigation_state(browser):
    current = browser.call()
    if current.get('fullscreen'):
        browser.exit_fullscreen()
        current = browser.call()
        if current.get('fullscreen'):
            raise RuntimeError('Could not confirm fullscreen exit. Next-video navigation was stopped.')
    if (getattr(browser, 'profile_selector', False)
            and not current.get('nextCount') and not current.get('nextDisabledCount')):
        previous = browser.selector
        browser.selector = ''
        try:
            discovered = browser.call('diagnose')
        except BaseException:
            browser.selector = previous
            raise
        if discovered.get('nextCount'):
            browser.selector = discovered.get('nextSelector') or ''
            say('The page structure changed. Rediscovered the next-video control.')
            return discovered
        browser.selector = previous
    return current


def test_site(browser, recorder, args):
    """Record a sample, prove navigation, then persist only the verified selectors."""
    try:
        status = browser.call('diagnose')
        validate_page(status)
        origin = site_origin(status['url'])
        if status.get('nextCount', 0) > 1:
            raise RuntimeError('Multiple next-control candidates found. Inspect --diagnose, then run --test with --video-next-selector.')
        if status.get('nextCount', 0) == 1:
            browser.selector = args.video_next_selector or status.get('nextSelector') or ''
            browser.next_hotkey = ''
            say('Next-video navigation: button '+(browser.selector or '(automatic discovery)'))
        elif (not args.video_next_selector and not status.get('nextDisabledCount', 0)
              and (origin == 'https://youtube.com' or origin.endswith('.youtube.com'))):
            browser.next_hotkey = 'shift+n'
            say('No YouTube player next control found. Testing Shift+N navigation.')
        else:
            raise RuntimeError('No usable next-video control found. Start from a playlist item with a successor or specify --video-next-selector.')
        profile = dict(video_selector=browser.player_selector, video_next_selector=browser.selector,
                       next_hotkey=browser.next_hotkey)
        say('Recording a sample of up to 10 seconds, then navigating to the next video.')
        recorded_id = record_one(browser, recorder, args, sample_seconds=10)
        path = recorder.last_output_path
        if not path or not Path(path).is_file() or Path(path).stat().st_size <= 0:
            raise RuntimeError('Could not verify the test recording file.')
        current = navigation_state(browser)
        if not current.get('focused') or current.get('videoId') != recorded_id:
            raise RuntimeError('The target video changed after the test recording. Disable automatic next-video playback.')
        if not browser.next_hotkey and current.get('nextCount') != 1:
            raise RuntimeError('Could not verify the next control after recording. Run --test again.')
        say('Navigating to the next video: '+(browser.next_hotkey or browser.selector or 'automatically discovered button'))
        browser.call('next')
        say(f'Waiting for new video loading (up to {args.video_load_timeout:g} seconds).')
        loaded = wait_video(browser, recorded_id, args.video_load_timeout)
        if site_origin(loaded['url']) != origin:
            raise RuntimeError('The next control opened another site. The site profile was not saved.')
        verify_playback(browser)
        browser.call('prepare')
        save_profile(status['url'], profile)
        say('Site profile saved. Play the sample to check picture and sound: '+str(path))
        say('The next video is paused. To record, run: python3 recorder.py --run --max-videos 10')
    finally:
        try: browser.call('pause')
        except Exception as error: say('Could not confirm pause after testing: '+str(error))


def run_videos(browser, recorder, args):
    for index in range(args.max_videos):
        recorded_id = record_one(browser, recorder, args)
        if index+1 == args.max_videos: return
        time.sleep(args.save_wait)
        current = navigation_state(browser)
        if not current.get('focused'):
            raise RuntimeError('The target tab changed before next-video navigation.')
        if current.get('videoId') != recorded_id:
            raise RuntimeError('The video changed while waiting after saving. Disable automatic next-video playback.')
        if current.get('nextCount', 0) == 0 and not getattr(browser, 'next_hotkey', ''):
            say('No enabled next-video control remains. Finished.')
            return
        if current['nextCount'] != 1 and not getattr(browser, 'next_hotkey', ''):
            raise RuntimeError('Multiple next-video buttons found. Specify --video-next-selector.')
        previous_id = current['videoId']
        browser.call('next')
        wait_video(browser, previous_id, args.video_load_timeout)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Automatic video recording with OBS and Chrome next-video navigation',
                                     allow_abbrev=False)
    parser.add_argument('--config', metavar='PATH', help='Load recording defaults from a JSON file')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='Inspect the current video and next control')
    mode.add_argument('--diagnose', action='store_true', help='Diagnose video and next-control candidates')
    mode.add_argument('--run', action='store_true', help='Record from the current video and advance to the next')
    mode.add_argument('--test', action='store_true', help='Test a short recording and next-video navigation, then save the site profile')
    mode.add_argument('--test-recording', '--test-hotkey', dest='test_recording', action='store_true',
                      help='Record the current OBS scene for 10 seconds without controlling Chrome')
    mode.add_argument('--check-obs', action='store_true', help='Check the OBS connection, scene, and recording directory')
    parser.add_argument('--recorder', choices=('obs','easeus'), default='obs')
    parser.add_argument('--obs-port', type=int, default=4455)
    parser.add_argument('--max-videos', type=int, default=1, help='Maximum videos to record, including the current one (default: 1)')
    parser.add_argument('--video-next-selector', default='', help='CSS selector for the next-video control')
    parser.add_argument('--video-selector', default='', help='CSS selector for the HTML video to record')
    parser.add_argument('--video-timeout', type=float, default=14400, help='Maximum playback wait per video in seconds (default: 14400)')
    parser.add_argument('--video-load-timeout', type=float, default=45, help='New video loading timeout in seconds (default: 45)')
    fullscreen = parser.add_mutually_exclusive_group()
    fullscreen.add_argument('--no-fullscreen', action='store_true')
    fullscreen.add_argument('--fullscreen', dest='no_fullscreen', action='store_false',
                            help='Enable fullscreen, overriding the configuration file')
    parser.add_argument('--start-hotkey', default='command+9')
    parser.add_argument('--stop-hotkey', default='command+9')
    parser.add_argument('--countdown', type=float, default=None)
    parser.add_argument('--save-wait', type=float, default=10)
    parser.add_argument('--stall-seconds', type=float, default=120)
    # Read only the config path first; the full parser still requires an explicit mode.
    config_parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    config_parser.add_argument('--config')
    config_path = config_parser.parse_known_args(argv)[0].config
    if config_path:
        try:
            settings = json.loads(Path(config_path).expanduser().read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            parser.error(f'Cannot read config file {config_path}: {error}')
        if not isinstance(settings, dict):
            parser.error('Config must be a JSON object.')
        types = {
            'recorder': str, 'obs_port': int, 'max_videos': int,
            'video_next_selector': str, 'video_selector': str,
            'video_timeout': float, 'video_load_timeout': float,
            'no_fullscreen': bool, 'start_hotkey': str, 'stop_hotkey': str,
            'countdown': float, 'save_wait': float, 'stall_seconds': float,
        }
        for key, value in settings.items():
            if key not in types:
                parser.error(f'Unknown config option: {key}. Use keys from config.example.json.')
            if key == 'countdown' and value is None:
                continue
            expected = types[key]
            valid = (type(value) in (int, float) if expected is float else type(value) is expected)
            if not valid or (expected is float and not math.isfinite(value)):
                parser.error(f'Invalid config value for {key}: expected {expected.__name__}.')
        if 'recorder' in settings and settings['recorder'] not in ('obs', 'easeus'):
            parser.error('Config recorder must be "obs" or "easeus".')
        parser.set_defaults(**settings)
    args = parser.parse_args(argv)
    if args.countdown is None: args.countdown = 0 if args.recorder == 'obs' else 6
    if args.test and args.recorder != 'obs':
        parser.error('--test requires OBS to verify the saved recording.')
    if (args.max_videos < 1 or not 1 <= args.obs_port <= 65535
            or not math.isfinite(args.countdown) or args.countdown < 0
            or any(not math.isfinite(x) or x <= 0 for x in
                   (args.save_wait, args.stall_seconds, args.video_timeout, args.video_load_timeout))):
        parser.error('Counts and wait times must be positive, countdown must be nonnegative, and the port must be 1-65535.')
    return args


def main():
    args = parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('Live recording and browser control are supported only on macOS.')
    browser = recorder = awake = None
    try:
        if args.check_obs:
            recorder = OBSRecorder(port=args.obs_port)
            print(json.dumps(recorder.check(), ensure_ascii=False, indent=2))
            return 0
        if args.test_recording:
            recorder = create_recorder(args)
            say('Starting a 10-second test recording. Control the playback app manually.')
            try:
                recorder.start()
                time.sleep(10)
            finally:
                path = recorder.stop()
            if path: say('Test recording file verified: '+path)
            return 0
        browser = Chrome(args.video_next_selector, args.video_selector)
        bring_to_front(browser)
        if not args.test:
            apply_site_profile(browser, args)
        if args.check or args.diagnose:
            status = browser.call('diagnose' if args.diagnose else 'inspect')
            print(json.dumps(status, ensure_ascii=False, indent=2))
            if args.check: validate_page(status)
            return 0
        wait_video(browser, timeout=args.video_load_timeout)
        recorder = create_recorder(args)
        awake = subprocess.Popen(['/usr/bin/caffeinate', '-di', '-w', str(__import__('os').getpid())])
        if args.test:
            test_site(browser, recorder, args)
            return 0
        run_videos(browser, recorder, args)
        say('Finished. Check the saved video and audio.')
        return 0
    except KeyboardInterrupt:
        say('Interrupted by the user.')
        return 130
    except Exception as error:
        say('Stopped: '+str(error))
        return 1
    finally:
        if recorder:
            if recorder.active:
                try: recorder.stop()
                except Exception as error: say('Could not confirm recording stop. Check OBS directly: '+str(error))
            recorder.close()
        if awake: awake.terminate()


if __name__ == '__main__':
    raise SystemExit(main())
