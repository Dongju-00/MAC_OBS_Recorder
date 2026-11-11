import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import recorder


class ConfigurationTests(unittest.TestCase):
    def parse_config(self, contents, *flags):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text(contents, encoding='utf-8')
            return recorder.parse_args(['--run', '--config', str(path), *flags])

    def test_saved_options_and_cli_overrides(self):
        contents = json.dumps(dict(max_videos=10, video_selector='#player video',
                                   video_next_selector='#next', obs_port=4456,
                                   no_fullscreen=True, save_wait=15))
        args = self.parse_config(contents, '--max-videos', '2', '--fullscreen')
        self.assertEqual(args.max_videos, 2)
        self.assertEqual(args.video_selector, '#player video')
        self.assertEqual(args.video_next_selector, '#next')
        self.assertEqual(args.obs_port, 4456)
        self.assertEqual(args.save_wait, 15)
        self.assertFalse(args.no_fullscreen)

    def test_existing_defaults_and_backend_countdown(self):
        args = recorder.parse_args(['--run'])
        self.assertEqual(args.max_videos, 1)
        self.assertEqual(args.countdown, 0)
        self.assertFalse(args.no_fullscreen)
        self.assertEqual(self.parse_config('{"recorder": "easeus"}').countdown, 6)
        self.assertEqual(self.parse_config('{"recorder": "easeus", "countdown": 2}').countdown, 2)

    def test_invalid_configuration_is_a_clear_cli_error(self):
        invalid = ['{', '[]', '{"max_video": 10}', '{"run": true}',
                   '{"password": "secret"}', '{"max_videos": true}',
                   '{"max_videos": 1.5}', '{"video_selector": 3}',
                   '{"no_fullscreen": "false"}', '{"countdown": NaN}',
                   '{"video_timeout": Infinity}', '{"recorder": "other"}',
                   '{"obs_port": 0}', '{"max_videos": 0}',
                   '{"save_wait": -1}', '{"countdown": -1}']
        for contents in invalid:
            with self.subTest(contents=contents), contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit) as raised:
                    self.parse_config(contents)
                self.assertEqual(raised.exception.code, 2)
                self.assertIn('error:', errors.getvalue())
                self.assertNotIn('Traceback', errors.getvalue())

    def test_abbreviated_config_does_not_silently_ignore_file(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            recorder.parse_args(['--run', '--conf', '/definitely/missing.json'])

    def test_missing_file_is_a_cli_error(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as raised:
                recorder.parse_args(['--run', '--config', str(Path(directory) / 'missing.json')])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn('config', errors.getvalue())

    def test_example_is_usable_and_modes_still_required(self):
        args = recorder.parse_args(['--check', '--config', 'config.example.json'])
        self.assertEqual(args.max_videos, 1)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            recorder.parse_args(['--config', 'config.example.json'])


if __name__ == '__main__':
    unittest.main()
