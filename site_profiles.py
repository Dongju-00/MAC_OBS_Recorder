"""Local, origin-scoped navigation profiles produced by a successful --test."""
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit


PROFILE_PATH = Path(__file__).resolve().parent / '.site-profiles.json'
FIELDS = {'video_selector', 'video_next_selector', 'next_hotkey'}


def site_origin(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            raise ValueError('Only HTTP(S) video pages can have site profiles.')
        host = parsed.hostname.lower()
        if ':' in host: host = '[' + host + ']'
        port = parsed.port
        suffix = f':{port}' if port and port != {'http': 80, 'https': 443}[parsed.scheme] else ''
        return f'{parsed.scheme}://{host}{suffix}'
    except (ValueError, TypeError) as error:
        raise RuntimeError(f'Cannot determine the site origin: {error}') from error


def _read(path):
    if not path.exists(): return {'version': 1, 'sites': {}}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('sites'), dict):
            raise ValueError('Invalid profile structure')
        for origin, profile in data['sites'].items():
            if site_origin(origin) != origin or not isinstance(profile, dict) or set(profile) != FIELDS:
                raise ValueError('Invalid site profile')
            if any(not isinstance(value, str) for value in profile.values()):
                raise ValueError('Profile values must be strings')
            if profile['next_hotkey'] not in ('', 'shift+n'):
                raise ValueError('Unknown navigation shortcut')
        return data
    except (OSError, ValueError, RuntimeError) as error:
        raise RuntimeError(f'Cannot read the site profile file: {path}. Move the file aside and run --test again. ({error})') from error


def load_profile(url, path=None):
    path = Path(path) if path is not None else PROFILE_PATH
    # Existing local-file recording still works; profiles are HTTP(S)-only.
    if urlsplit(url).scheme not in ('http', 'https'): return None
    return _read(path)['sites'].get(site_origin(url))


def save_profile(url, profile, path=None):
    path = Path(path) if path is not None else PROFILE_PATH
    data = _read(path)
    data['sites'][site_origin(url)] = dict(profile)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', delete=False) as output:
            temporary = Path(output.name)
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)
