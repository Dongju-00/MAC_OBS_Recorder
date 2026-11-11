from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import recorder as app


def state(**changes):
    result = dict(url='https://media.example/watch', videoId='document:1:0', focused=True,
                  videoCount=1, duration=60, time=0, paused=True, ended=False, error=None,
                  playError=None, playerReady=True, seeking=False, readyState=4,
                  userActivated=True, nextCount=1, nextDisabledCount=0)
    result.update(changes)
    return result


def options(**changes):
    values = dict(countdown=0, stall_seconds=120, video_timeout=600, save_wait=1,
                  video_load_timeout=3, max_videos=2, no_fullscreen=True)
    values.update(changes)
    return SimpleNamespace(**values)


class Browser:
    """External Chrome boundary: play advances through two finite media items."""
    def __init__(self, events, save_path=None):
        self.events = events
        self.index = 1
        self.played = False
        self.save_path = save_path

    def focus(self):
        self.events.append('focus')

    def call(self, action='inspect'):
        self.events.append(action)
        if action == 'prepare': self.played = False
        if action == 'play': self.played = True
        if action == 'pause': self.played = False
        if action == 'next':
            if self.save_path and not self.save_path.is_file():
                raise AssertionError('저장된 파일 없이 이동하면 안 됨')
            self.index += 1
            self.played = False
        return state(videoId=f'document:{self.index}:0', paused=not self.played,
                     ended=self.played, time=60 if self.played else 0,
                     nextCount=1 if self.index < 2 else 0)


class Recorder:
    def __init__(self, events, path=None, fail_stop=False, fail_start=False):
        self.events = events
        self.path = path
        self.active = False
        self.fail_stop = fail_stop
        self.fail_start = fail_start

    def start(self):
        self.active = True
        self.events.append('start')
        if self.fail_start: raise RuntimeError('start failed')

    def stop(self):
        if not self.active: return None
        self.events.append('stop')
        self.active = False
        if self.fail_stop: raise RuntimeError('저장 파일 실패')
        if self.path:
            self.path.write_bytes(b'video')
            return str(self.path)

    def close(self):
        pass


class ValidationTests(unittest.TestCase):
    def test_accepts_general_urls_without_page_specific_parameters(self):
        for url in ['https://media.example/watch', 'http://localhost/video', 'file:///tmp/video.html']:
            with self.subTest(url=url): app.validate_page(state(url=url))

    def test_missing_or_ambiguous_video_is_rejected(self):
        for count in [0, 2]:
            with self.subTest(count=count), self.assertRaises(RuntimeError):
                app.validate_page(state(videoCount=count))

    def test_invalid_duration_is_rejected(self):
        for duration in [None, 0, -1, float('inf'), float('nan')]:
            with self.subTest(duration=duration), self.assertRaises(RuntimeError):
                app.validate_page(state(duration=duration))

    def test_progress_near_end_is_not_completion(self):
        monitor = app.ProgressMonitor(state())
        self.assertFalse(monitor.update(state(time=59.99), 0))
        self.assertTrue(monitor.update(state(time=60, ended=True), 1))

    def test_stall_and_media_replacement_abort(self):
        monitor = app.ProgressMonitor(state(), stall_seconds=10)
        monitor.update(state(time=5), 0)
        with self.assertRaisesRegex(RuntimeError, '진행'): monitor.update(state(time=5), 11)
        with self.assertRaises(RuntimeError): monitor.update(state(videoId='replacement'), 1)

    def test_media_and_focus_errors_abort(self):
        for changes in [dict(error=3), dict(playError='blocked'), dict(focused=False), dict(playerReady=False)]:
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                app.ProgressMonitor(state()).update(state(**changes), 1)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('recorder.time.sleep'))
        self.stack.enter_context(patch('recorder.say'))
        self.events = []

    def test_saved_file_precedes_next_click_and_limit_never_overadvances(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'video.mkv'
            browser = Browser(self.events, path)
            recorder = Recorder(self.events, path)
            app.run_videos(browser, recorder, options())
            self.assertTrue(path.is_file())
            self.assertEqual(self.events.count('start'), 2)
            self.assertEqual(self.events.count('stop'), 2)
            self.assertEqual(self.events.count('next'), 1)
            self.assertLess(self.events.index('stop'), self.events.index('next'))

    def test_single_video_limit_does_not_click_next(self):
        app.run_videos(Browser(self.events), Recorder(self.events), options(max_videos=1))
        self.assertEqual(self.events.count('start'), 1)
        self.assertNotIn('next', self.events)

    def test_no_next_button_finishes_without_click(self):
        browser = Browser(self.events)
        browser.index = 2
        app.run_videos(browser, Recorder(self.events), options())
        self.assertEqual(self.events.count('start'), 1)
        self.assertNotIn('next', self.events)

    def test_ambiguous_next_button_stops_after_saving(self):
        browser = Browser(self.events)
        original = browser.call
        browser.call = lambda action='inspect': dict(original(action), nextCount=2)
        with self.assertRaisesRegex(RuntimeError, '버튼'):
            app.run_videos(browser, Recorder(self.events), options())
        self.assertIn('stop', self.events)
        self.assertNotIn('next', self.events)

    def test_failed_save_never_moves_to_next_video(self):
        with self.assertRaisesRegex(RuntimeError, '저장'):
            app.run_videos(Browser(self.events), Recorder(self.events, fail_stop=True), options())
        self.assertNotIn('next', self.events)

    def test_failed_start_still_pauses_and_attempts_stop(self):
        with self.assertRaisesRegex(RuntimeError, 'start failed'):
            app.record_one(Browser(self.events), Recorder(self.events, fail_start=True), options())
        self.assertEqual(self.events[-2:], ['pause', 'stop'])

    def test_interrupt_pauses_and_stops_recording(self):
        browser = Browser(self.events)
        original = browser.call
        recorder = Recorder(self.events)
        def call(action='inspect'):
            if recorder.active and action == 'inspect': raise KeyboardInterrupt()
            return original(action)
        browser.call = call
        with self.assertRaises(KeyboardInterrupt): app.record_one(browser, recorder, options())
        self.assertFalse(recorder.active)
        self.assertEqual(self.events[-2:], ['pause', 'stop'])

    def test_pause_failure_still_stops_recording(self):
        browser = Browser(self.events)
        recorder = Recorder(self.events)
        original = browser.call
        def call(action='inspect'):
            if action == 'pause' and recorder.active: raise RuntimeError('pause failed')
            return original(action)
        browser.call = call
        app.record_one(browser, recorder, options())
        self.assertFalse(recorder.active)
        self.assertIn('stop', self.events)

    def test_playback_rejection_does_not_start_recording(self):
        browser = Browser(self.events)
        original = browser.call
        browser.call = lambda action='inspect': dict(original(action), playError='blocked')
        with self.assertRaises(RuntimeError):
            app.record_one(browser, Recorder(self.events), options())
        self.assertNotIn('start', self.events)

    def test_video_change_while_saving_does_not_click_past_new_video(self):
        browser = Browser(self.events)
        recorder = Recorder(self.events)
        original = recorder.stop
        def stop():
            result = original()
            browser.index += 1
            return result
        recorder.stop = stop
        with self.assertRaisesRegex(RuntimeError, '영상.*바뀌'):
            app.run_videos(browser, recorder, options())
        self.assertNotIn('next', self.events)

    def test_initial_finished_video_can_be_rewound_for_recording(self):
        result = app.wait_video(SimpleNamespace(call=lambda: state(ended=True)), timeout=3)
        self.assertTrue(result['ended'])

    def test_rewind_waits_for_unbuffered_start_before_recording(self):
        browser = Browser(self.events)
        original = browser.call
        loading = False
        def call(action='inspect'):
            nonlocal loading
            result = original(action)
            if action == 'prepare': loading = True
            elif action == 'inspect' and loading:
                loading = False
                result.update(seeking=True, playerReady=False, readyState=1)
            return result
        browser.call = call
        app.record_one(browser, Recorder(self.events), options())
        self.assertIn('start', self.events)
        self.assertEqual(self.events[-2:], ['pause', 'stop'])

    def test_transition_waits_for_media_replacement_and_loading(self):
        samples = iter([state(url='https://media.example/2'), state(videoId='new', playerReady=False),
                        state(videoId='new')])
        browser = SimpleNamespace(call=lambda: next(samples))
        result = app.wait_video(browser, 'document:1:0', timeout=3)
        self.assertEqual(result['videoId'], 'new')

    def test_transition_timeout_does_not_accept_old_video(self):
        with patch('recorder.time.monotonic', side_effect=[0, 0, 4]):
            with self.assertRaisesRegex(RuntimeError, '로딩|새 영상'):
                app.wait_video(SimpleNamespace(call=lambda: state()), 'document:1:0', timeout=3)


class CLITests(unittest.TestCase):
    def test_video_options_reach_browser_and_run(self):
        events = []
        browser = Browser(events)
        args = ['recorder.py', '--run', '--max-videos', '2', '--video-next-selector', '#advance',
                '--video-selector', '#player', '--video-timeout', '600', '--no-fullscreen']
        with patch('recorder.sys.argv', args), patch('recorder.sys.platform', 'darwin'), \
             patch('recorder.Chrome', return_value=browser) as chrome, \
             patch('recorder.create_recorder', return_value=Recorder(events)), \
             patch('recorder.subprocess.Popen') as awake, patch('recorder.time.sleep'), \
             patch('recorder.say'):
            self.assertEqual(app.main(), 0)
            self.assertEqual(chrome.call_args.args, ('#advance', '#player'))
            awake.return_value.terminate.assert_called_once()
        self.assertEqual(events.count('start'), 2)

    def test_invalid_limit_and_nonfinite_wait_are_rejected_before_control(self):
        for flags in [['--max-videos', '0'], ['--video-load-timeout', 'nan'], ['--save-wait', '-1']]:
            with self.subTest(flags=flags), patch('recorder.sys.argv', ['recorder.py', '--run', *flags]), \
                 patch('recorder.sys.platform', 'darwin'), patch('recorder.Chrome') as chrome, \
                 patch('sys.stderr'), self.assertRaises(SystemExit):
                app.main()
            chrome.assert_not_called()

    def test_hotkey_validation_rejects_injection(self):
        with self.assertRaises(ValueError): app.hotkey_script('command+" anything')
        self.assertIn('key code 25', app.hotkey_script('command+9'))

    def test_tab_identity_is_used_even_when_another_app_is_frontmost(self):
        chrome = app.Chrome.__new__(app.Chrome)
        chrome.window, chrome.tab, chrome.selector, chrome.player_selector = 10, 20, '', ''
        chrome.source = Path('browser.js').read_text()
        payload = '0\nTerminal\n11\n20\n{"videoCount":1}'
        with patch('recorder.apple', return_value=payload): self.assertTrue(chrome.call()['focused'])
        with patch('recorder.apple', return_value=payload.replace('\n20\n','\n21\n')):
            with self.assertRaises(RuntimeError): chrome.call('play')


if __name__ == '__main__': unittest.main()
