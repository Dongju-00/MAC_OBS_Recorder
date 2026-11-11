from contextlib import ExitStack, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import recorder as app
import site_profiles
from test_recorder import Browser, Recorder, options, state


class ProfileTests(unittest.TestCase):
    def test_exact_origins_are_isolated_and_updates_keep_other_sites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profiles.json'
            profile = dict(video_selector='', video_next_selector='#advance', next_hotkey='')
            site_profiles.save_profile('https://one.example/watch?secret=x', profile, path)
            site_profiles.save_profile('https://two.example/first', profile, path)
            self.assertEqual(site_profiles.load_profile('https://one.example/second', path), profile)
            self.assertIsNone(site_profiles.load_profile('http://one.example/second', path))
            self.assertIsNone(site_profiles.load_profile('https://one.example:8443/', path))
            self.assertNotIn('secret', path.read_text())
            self.assertEqual(len(json.loads(path.read_text())['sites']), 2)

    def test_corruption_is_reported_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profiles.json'
            for contents in ['{', '[]', '{"version": 1, "sites": []}',
                             '{"version": 1, "sites": {"https://one.example": {"next_hotkey": 2}}}']:
                path.write_text(contents)
                with self.assertRaises(RuntimeError):
                    site_profiles.load_profile('https://one.example', path)
                self.assertEqual(path.read_text(), contents)

    def test_explicit_selectors_override_saved_profile_and_shortcut(self):
        browser = Browser([])
        browser.selector = '#explicit'
        browser.player_selector = '#player'
        args = options(video_next_selector='#explicit', video_selector='#player')
        profile = dict(video_next_selector='', video_selector='#saved', next_hotkey='shift+n')
        with patch('recorder.load_profile', return_value=profile), patch('recorder.say'):
            app.apply_site_profile(browser, args)
        self.assertEqual(browser.selector, '#explicit')
        self.assertEqual(browser.player_selector, '#player')
        self.assertFalse(getattr(browser, 'next_hotkey', ''))

    def test_saved_profile_is_applied_without_a_config_argument(self):
        browser = Browser([])
        browser.selector = browser.player_selector = ''
        profile = dict(video_next_selector='#saved', video_selector='#video', next_hotkey='')
        with patch('recorder.load_profile', return_value=profile), patch('recorder.say'):
            app.apply_site_profile(browser, options(video_next_selector='', video_selector=''))
        self.assertEqual(browser.selector, '#saved')
        self.assertEqual(browser.player_selector, '#video')

    def test_stale_saved_selector_is_rediscovered_on_a_later_page(self):
        browser = Browser([])
        browser.selector = '#old'
        browser.profile_selector = True
        browser.call = lambda action='inspect': state(nextCount=0 if browser.selector else 1,
                                                      nextSelector='#new')
        with patch('recorder.say'):
            result = app.navigation_state(browser)
        self.assertEqual(result['nextCount'], 1)
        self.assertEqual(browser.selector, '#new')

    def test_saved_shortcut_does_not_cross_origins(self):
        browser = Browser([])
        browser.profile_origin = 'https://www.youtube.com'
        with self.assertRaises(RuntimeError):
            app.record_one(browser, Recorder([]), options())


class SiteTestFlowTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('recorder.time.sleep'))
        self.stack.enter_context(patch('recorder.say'))
        self.directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.events = []
        self.path = Path(self.directory) / 'sample.mkv'
        self.browser = Browser(self.events, self.path)
        self.browser.enter_fullscreen = lambda: True
        self.browser.exit_fullscreen = lambda: None
        self.browser.selector = self.browser.player_selector = self.browser.next_hotkey = ''
        self.recorder = Recorder(self.events, self.path)
        self.recorder.last_output_path = str(self.path)
        self.args = options(video_next_selector='', video_selector='', recorder='obs')
        original = self.browser.call
        def call(action='inspect'):
            result = original(action)
            if action == 'diagnose': result['nextSelector'] = '#advance'
            return result
        self.browser.call = call
        self.save = self.stack.enter_context(patch('recorder.save_profile'))

    def test_sample_is_saved_before_navigation_and_profile_persists_after_transition(self):
        app.test_site(self.browser, self.recorder, self.args)
        self.assertTrue(self.path.is_file())
        self.assertLess(self.events.index('stop'), self.events.index('next'))
        self.assertEqual(self.browser.index, 2)
        self.assertFalse(self.browser.played)
        self.assertEqual(self.save.call_args.args[1]['video_next_selector'], '#advance')

    def test_failed_save_never_navigates_or_updates_profile(self):
        self.recorder.fail_stop = True
        with self.assertRaises(RuntimeError): app.test_site(self.browser, self.recorder, self.args)
        self.assertNotIn('next', self.events)
        self.save.assert_not_called()

    def test_ambiguous_or_missing_controls_do_not_record(self):
        original = self.browser.call
        for count in [0, 2]:
            self.browser.call = lambda action='inspect', count=count: dict(original(action), nextCount=count)
            with self.subTest(count=count), self.assertRaises(RuntimeError):
                app.test_site(self.browser, self.recorder, self.args)
        self.assertNotIn('start', self.events)
        self.assertNotIn('next', self.events)
        self.save.assert_not_called()

    def test_rejected_setup_pauses_an_already_playing_page(self):
        self.browser.played = True
        original = self.browser.call
        self.browser.call = lambda action='inspect': dict(original(action), nextCount=2)
        with self.assertRaises(RuntimeError): app.test_site(self.browser, self.recorder, self.args)
        self.assertFalse(self.browser.played)
        self.assertNotIn('start', self.events)
        self.save.assert_not_called()

    def test_failed_transition_does_not_save_profile(self):
        with patch('recorder.wait_video', side_effect=RuntimeError('loading failed')):
            with self.assertRaises(RuntimeError): app.test_site(self.browser, self.recorder, self.args)
        self.save.assert_not_called()
        self.assertFalse(self.browser.played)

    def test_media_change_during_sample_does_not_click_next(self):
        original = self.recorder.stop
        def stop():
            result = original()
            self.browser.index += 1
            return result
        self.recorder.stop = stop
        with self.assertRaises(RuntimeError): app.test_site(self.browser, self.recorder, self.args)
        self.assertNotIn('next', self.events)
        self.save.assert_not_called()

    def test_youtube_without_a_button_uses_verified_shortcut(self):
        original = self.browser.call
        self.browser.call = lambda action='inspect': dict(original(action), url='https://www.youtube.com/watch?v=one', nextCount=0)
        app.test_site(self.browser, self.recorder, self.args)
        self.assertEqual(self.browser.next_hotkey, 'shift+n')
        self.assertEqual(self.save.call_args.args[1]['next_hotkey'], 'shift+n')

    def test_test_mode_is_separate_from_scene_only_recording(self):
        self.assertTrue(app.parse_args(['--test']).test)
        self.assertFalse(app.parse_args(['--test-recording']).test)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            app.parse_args(['--test', '--recorder', 'easeus'])

    def test_sample_requires_progress_even_if_rewind_stops_just_above_zero(self):
        original = self.browser.call
        self.browser.call = lambda action='inspect': dict(original(action), time=0.3, ended=False)
        with patch('recorder.time.monotonic', side_effect=[0, 0, 0, 0, 11]):
            with self.assertRaisesRegex(RuntimeError, 'playback'):
                app.record_one(self.browser, self.recorder, self.args, sample_seconds=10)
        self.assertIn('stop', self.events)

    def test_sample_stops_at_ten_seconds_while_video_is_still_playing(self):
        original = self.browser.call
        samples = iter([1, 4, 9])
        def call(action='inspect'):
            result = original(action)
            result['ended'] = False
            result['time'] = next(samples) if action == 'inspect' and self.recorder.active and self.browser.played else 0
            return result
        self.browser.call = call
        with patch('recorder.time.monotonic', side_effect=[0, 0, 0, 0, 4, 8, 10]):
            app.record_one(self.browser, self.recorder, self.args, sample_seconds=10)
        self.assertEqual(self.events.count('start'), 1)
        self.assertEqual(self.events.count('stop'), 1)
        self.assertFalse(self.recorder.active)
        self.assertFalse(self.browser.played)
        self.assertTrue(self.path.is_file())

    def test_failed_fullscreen_exit_prevents_navigation_and_profile_save(self):
        original = self.browser.call
        self.browser.call = lambda action='inspect': dict(original(action), fullscreen=True)
        with self.assertRaises(RuntimeError): app.test_site(self.browser, self.recorder, self.args)
        self.assertNotIn('next', self.events)
        self.save.assert_not_called()

    def test_test_mode_is_wired_to_setup_without_loading_old_profiles(self):
        with patch('recorder.sys.argv', ['recorder.py', '--test']), \
             patch('recorder.sys.platform', 'darwin'), \
             patch('recorder.Chrome', return_value=self.browser), \
             patch('recorder.create_recorder', return_value=self.recorder), \
             patch('recorder.subprocess.Popen'), patch('recorder.load_profile') as load:
            self.assertEqual(app.main(), 0)
        load.assert_not_called()
        self.assertEqual(self.browser.index, 2)
        self.save.assert_called_once()

    def test_native_hotkey_is_sent_to_the_pinned_chrome_window(self):
        chrome = app.Chrome.__new__(app.Chrome)
        chrome.window, chrome.tab = 10, 20
        chrome.selector = chrome.player_selector = ''
        chrome.next_hotkey = 'shift+n'
        chrome.source = Path('browser.js').read_text()
        payload = '1\nGoogle Chrome\n10\n20\n{"focused":true}'
        with patch.object(chrome, 'ensure_front'), patch('recorder.apple', return_value=payload) as apple:
            chrome.call('next')
        # Text-based keystroke "n" can introduce Option under a Korean input source.
        # A physical ANSI N key must preserve only the requested Shift modifier.
        self.assertIn('key code 45 using {shift down}', apple.call_args.args[0])


if __name__ == '__main__': unittest.main()
