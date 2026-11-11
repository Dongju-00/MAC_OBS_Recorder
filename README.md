# macOS OBS Recorder

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md)

![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey)
![Python: Standard Library](https://img.shields.io/badge/Python-standard%20library-blue)
![OBS: WebSocket 5](https://img.shields.io/badge/OBS-WebSocket%205-302E31)

A general-purpose OBS helper for recording your own content, content you have permission to record, and browser test sessions on ordinary non-DRM webpages. Run a site test once to discover its next-video control, verify recording and navigation, and save the settings. Then record from the current Chrome tab, one file at a time.

[Getting Started](#installation) · [Recording Guides](#user-guides) · [Customization](#customization) · [FAQ](#faq)

## Table of Contents

- [Intended Use and Limitations](#intended-use-and-limitations)
- [Features](#features)
- [Installation](#installation)
- [OBS Setup](#obs-setup)
- [User Guides](#user-guides)
- [Customization](#customization)
- [FAQ](#faq)
- [Developer Guide](#developer-guide)
- [Resources](#resources)

## Intended Use and Limitations

Use this tool only for content you own or have permission to record, such as your own videos, demonstrations, and browser automation tests on ordinary non-DRM webpages.

- **No DRM circumvention:** This project does not extract decryption keys, modify Widevine or other DRM settings, inject protection-disabling flags, or disable browser/OS capture protections.
- **Capture restrictions remain in effect:** Protected content may be blocked, omitted, or displayed as a black screen by the browser, operating system, or capture path. This tool does not detect all DRM or guarantee the capture behavior of any protected content. It provides no workaround for these restrictions.
- **Respect rights and service terms:** Permission to watch content does not necessarily grant permission to record or redistribute it. Do not use this tool to bypass protections or make unauthorized copies. Follow applicable copyright law and the relevant service's terms.

This notice is general project documentation, not legal advice or a guarantee that any particular use is lawful. Consult a qualified legal professional for advice about your situation.

## Features

- Record permitted application windows or displays through your OBS scene, subject to capture restrictions.
- Check the OBS connection, scene sources, BlackHole input, and recording directory.
- Make a 10-second test recording without controlling Chrome.
- Run `--test` to discover site navigation, record a short sample, and save a verified site profile.
- Record a Chrome video from the beginning and optionally continue with a next-video button.
- Verify that OBS stopped and created a nonempty file before advancing.
- Save player selectors, recording limits, and timeouts in a reusable JSON configuration.
- Run with the Python standard library. No Python packages or API keys required.

## Installation

| Requirement | Purpose |
| --- | --- |
| macOS | AppleScript control of Chrome and recording apps |
| [OBS Studio](https://obsproject.com/download), version 28 or later | Recording and the built-in WebSocket 5 server |
| Python 3 | Running the scripts |
| [BlackHole 2ch](https://existential.audio/blackhole/) | Routing system audio into the OBS input checked by this tool |
| [Google Chrome](https://www.google.com/chrome/) | Browser automation only |

Download this repository or clone it, then open a terminal in the project folder:

```bash
git clone https://github.com/Dongju-00/MAC_OBS_Recorder.git
cd MAC_OBS_Recorder
python3 --version
python3 recorder.py --help
```

Node.js is needed only for the browser tests in the [Developer Guide](#developer-guide).

## OBS Setup

### 1. Capture video

1. Open OBS and create a recording scene.
2. Add **Sources → + → macOS Screen Capture**.
3. Choose the player window for window capture, or a display for screen capture.
4. Allow OBS screen recording access in **System Settings → Privacy & Security**. Restart OBS if requested.
5. Check the preview and adjust the capture size.

Keep a captured window open and unminimized. Display capture includes other windows and notifications on that display.

### 2. Capture system audio

The OBS checks require an enabled, unmuted **BlackHole 2ch** audio input added directly to the current scene. Nested scenes, groups, and global audio inputs are not searched by this check.

1. Install BlackHole 2ch and restart your Mac when prompted.
2. Open **Audio MIDI Setup → + → Create Multi-Output Device**.
3. Select your speakers or headphones and **BlackHole 2ch**. Enable drift correction for devices other than the primary clock device. See BlackHole's [Multi-Output Device guide](https://github.com/ExistentialAudio/BlackHole/wiki/Multi-Output-Device).
4. Select the new device in **System Settings → Sound → Output**.
5. In OBS, add **Sources → + → macOS Audio Input Capture**, select **BlackHole 2ch**, and unmute it.
6. Disable unused Desktop Audio and Mic/Aux inputs in **Settings → Audio**. If the screen capture source also captures audio, mute that audio to avoid duplicates.
7. Play a video and confirm that the BlackHole meter moves in OBS. Allow audio input access if requested.

### 3. Choose recording output

Set the recording directory and format in **OBS → Settings → Output → Recording**. File names and formats follow your OBS settings.

You can record to MKV and convert it to MP4 using **File → Remux Recordings**. Check available disk space before a long session.

### 4. Enable WebSocket control

1. Open **OBS → Tools → WebSocket Server Settings**.
2. Enable the server and keep the default port, **4455**.
3. Enable authentication and note the server password.
4. Check the connection:

```bash
python3 recorder.py --check-obs
```

Enter the password when prompted; input is hidden. To reuse it in the current zsh session:

```zsh
read -s 'OBS_WEBSOCKET_PASSWORD?OBS WebSocket password: '
export OBS_WEBSOCKET_PASSWORD
```

The connection uses `127.0.0.1`. Keep the password out of source files and Git. If you change the server port, pass the matching `--obs-port` value.

## User Guides

### Test your recording setup

Start playback in any application, then run:

```bash
python3 recorder.py --test-recording
```

This records the current OBS scene for **10 seconds** and checks the saved file. Open the recording to confirm the picture and sound. Chrome is not controlled during this test.

To record other applications manually, use OBS's **Start Recording / Stop Recording** buttons after setting up your scene.

### Prepare Chrome automation

1. Enable **Chrome → View → Developer → Allow JavaScript from Apple Events**.
2. In **System Settings → Privacy & Security → Accessibility / Automation**, allow your terminal to control Chrome and System Events as requested.
3. Open the video page, sign in if needed, and select the target tab.
4. Turn off the site's automatic next-video playback. The script advances after saving.
5. Play and pause the video once to load the player and allow playback.

### Test a new site once

Open a video that has another video after it, then run:

```bash
python3 recorder.py --test
```

The test:

1. Finds the next-video control from its label or identifying attributes.
2. Rewinds the current video and records up to 10 seconds with OBS.
3. Checks playback progress, stops OBS, and verifies a nonempty saved file.
4. Actually moves to the next video and checks that new media loads and can play.
5. Pauses and rewinds that next video, then saves the successful site settings.

**The test changes the current video.** After it succeeds, `--run` starts from the next video now selected. To include the original video in a full recording, reopen it before running.

Open the sample file printed in the terminal to check its actual picture and sound. Automated checks cannot judge capture framing or audible sound. OBS must be configured before testing; `--test` does not support EaseUS.

Profiles are stored in `.site-profiles.json` beside the scripts and loaded automatically for the same scheme, hostname, and port. You do not need to pass `--config` to reuse them. A test that fails does not replace the previous profile. Run `--test` again to update a site.

YouTube uses a next control inside its video player when available; unrelated page and carousel arrows are excluded. If no enabled or disabled player next control is found, the test tries **Shift+N** and saves that method only after a successful media transition. Use a playlist when you want a defined sequence; outside a playlist, YouTube chooses the next suggested video. Other sites do not receive guessed shortcuts.

If multiple equally strong buttons are found, the test stops and asks for an explicit selector:

```bash
python3 recorder.py --diagnose
python3 recorder.py --test --video-next-selector '#your-next-button'
```

The selector is saved after a successful test, so you can omit it from later runs. If the player itself is ambiguous, also pass `--video-selector`.

### Inspect without changing videos

```bash
python3 recorder.py --check
python3 recorder.py --diagnose
```

Both commands bring the target tab forward without starting playback, recording, or clicking next. `--check` requires one loaded video with a finite duration. `--diagnose` lists button candidates even when no video is available.

| Status field | Expected result |
| --- | --- |
| `videoCount` | `1` |
| `playerReady` | `true`, with a positive `duration` |
| `focused` | `true`: the target tab is selected in its window |
| `nextCount` | `1` for button navigation; a tested YouTube shortcut can work with `0` |
| `nextDisabledCount` | Number of disabled next buttons |
| `inaccessibleFrames` | Frames the page script cannot access |

### Record one or more videos

```bash
# Record the current video from the beginning.
python3 recorder.py --run

# Record up to 10 videos, including the current video.
python3 recorder.py --run --max-videos 10
```

Saved site settings are applied automatically. If a saved button selector disappears on a later page, the script tries semantic discovery again; ambiguous candidates stop the session. Explicit selectors from the command line or `--config` override saved selectors.

The script tests playback, rewinds, starts OBS, plays the video, and stops OBS when the video ends. Each video gets a separate recording. Fullscreen is enabled by default; add `--no-fullscreen` for the normal player view. If fullscreen cannot be confirmed, the script logs a warning and records in the normal view.

After OBS stops and the file is verified, the script waits 10 seconds, uses the next button or tested shortcut, and waits for new media to load. With button navigation, no enabled next button ends the session normally. If shortcut navigation cannot load new media, the session stops with an error. Multiple button candidates stop the session so you can specify a selector. The recording limit is checked before advancing.

Keep the target tab selected and its window open and unminimized. With window capture, other apps may be in front during recording; the script brings Chrome forward when starting playback.

Press **Control+C** to interrupt. The script attempts to pause playback and stop and save the recording it started. Check OBS directly if cleanup fails. A new run records the current video from the beginning.

## Customization

### Save your settings

Copy the example once, then edit `config.json` in any text editor:

```bash
cp config.example.json config.json
```

The example contains every supported setting and preserves the existing defaults. For a site with a specific player and next button, change these entries:

```json
{
  "max_videos": 10,
  "video_selector": "#player video",
  "video_next_selector": "#next-video",
  "video_load_timeout": 60,
  "no_fullscreen": true
}
```

Replace the selectors with values from your page, then check them before recording:

```bash
python3 recorder.py --config config.json --diagnose
python3 recorder.py --config config.json --check
python3 recorder.py --config config.json --run

# Override saved settings for one run.
python3 recorder.py --config config.json --run --max-videos 1 --fullscreen
```

This configuration file is loaded **only when you pass `--config`**. Relative paths are resolved from your terminal's current directory. For recording options, precedence is **command-line options → configuration file → built-in defaults**. Nonempty player and next-button selectors from these options override the automatically loaded site profile. You can omit settings you do not need. Unknown keys and invalid values produce an error before Chrome or OBS is controlled.

Configuration keys use underscores: `--video-load-timeout` becomes `video_load_timeout`. For the boolean `no_fullscreen`, use JSON `true` or `false`; `--fullscreen` overrides a saved `true`. Set `countdown` to `null` to use the recorder-specific default. Keep a mode such as `--run` on the command line and passwords in the environment variable or interactive prompt.

`config.json` is ignored by Git. Keep your changes there; leave [config.example.json](config.example.json) as a template for other users.

### Select the player and next button

Most site-specific changes can be made with options, without editing Python or JavaScript.

By default, the script looks for one visible HTML `<video>` and a next control identified by labels such as `Next video`, `Next lesson`, `다음 동영상`, or `다음 강의`, a `rel="next"` attribute, or next-control identifiers. Shortcut suffixes such as `(Shift+N)` are supported. Video-specific controls take priority over generic `Next` labels.

1. Open Chrome Developer Tools and inspect the next-video button.
2. Right-click its element and choose **Copy → Copy selector**.
3. Replace `#next-video` below with that selector. If needed, replace `#player video` with a selector pointing directly to the HTML `<video>` element.
4. Diagnose first and confirm that `nextCandidates` contains exactly the intended enabled button.

```bash
python3 recorder.py --diagnose \
  --video-selector '#player video' \
  --video-next-selector '#next-video'

python3 recorder.py --run \
  --video-selector '#player video' \
  --video-next-selector '#next-video' \
  --max-videos 10
```

These selectors are examples, not universal values. The next button must load the next video in the **same tab**.

To save a working selector, use it with `--test`. To reset all saved site profiles, move `.site-profiles.json` elsewhere and run `--test` again. This file is ignored by Git and contains site origins and selectors, not full video URLs or passwords.

### Recording options

All times are in seconds. Run `python3 recorder.py --help` for the full command list.

| Option | Default | Change this when… |
| --- | --- | --- |
| `--max-videos` | `1` | You want to record more than the current video. |
| `--video-selector` | Automatic | The page contains multiple visible videos. |
| `--video-next-selector` | Automatic | The next button is missing or ambiguous. |
| `--video-timeout` | `14400` | A video may run longer than four hours. |
| `--video-load-timeout` | `45` | The initial or next video loads slowly. |
| `--no-fullscreen` | Fullscreen enabled | You want the normal player view. |
| `--fullscreen` | Fullscreen enabled | You want to override `no_fullscreen: true` in a configuration file. |
| `--save-wait` | `10` | You want a different delay before clicking next. |
| `--stall-seconds` | `120` | Playback may remain stalled for longer. |
| `--countdown` | `0` for OBS; `6` for EaseUS | You need a delay between starting recording and playback. |
| `--obs-port` | `4455` | You changed the OBS WebSocket server port. |

Set the **output folder, file name, format, resolution, frame rate, quality, capture target, and audio device in OBS**. These are not controlled by the options above.

### Legacy EaseUS control

Use shortcuts matching your EaseUS settings:

```bash
python3 recorder.py --run --recorder easeus \
  --start-hotkey 'command+9' --stop-hotkey 'command+9'
```

Both shortcuts default to `command+9`. Supported modifiers are `command`, `control`, `option`, and `shift`, followed by a single letter or digit. EaseUS control cannot verify the recording state or saved file. `--test-hotkey` is an alias for the 10-second test mode.

## FAQ

### Which sites support automatic recording?

Automation needs an accessible HTML `<video>` with a finite duration. Continuing also needs a same-tab next button or the tested YouTube shortcut. The script searches same-origin iframes and open shadow roots; cross-origin frames, closed shadow roots, live streams, and native app players may not be controllable. Automatic discovery does not guarantee support for every site. Use OBS manually for these cases.

### Can this tool bypass DRM or fix a protected-content black screen?

No. It uses normal OBS recording and browser playback controls and does not change content protection or browser security settings. Protected content may be excluded from capture or appear black. A successful file or playback check does not establish recording permission or prove that protected video was captured. See [Intended Use and Limitations](#intended-use-and-limitations).

### Why does the script stop instead of going to the next video?

It stops on ambiguous buttons, playback errors, stalled playback, unexpected media changes, or failed save verification. Turn off automatic next-video playback and use `--diagnose` to inspect selectors. A URL change alone does not count as new media.

### Why is there no sound, or why is the sound doubled?

Check the Multi-Output Device, system output, OBS audio permissions, and the unmuted BlackHole 2ch input. Mute duplicate audio from screen capture or global audio inputs. Replay a test recording to confirm the result.

### Why do the Mac volume keys stop working?

macOS does not provide its usual volume control for Multi-Output Devices. Adjust the playback app or individual output device volume. Restore your usual system output after recording. See the [BlackHole FAQ](https://github.com/ExistentialAudio/BlackHole#faq).

### Do the checks confirm that the recording looks and sounds correct?

No. The script checks source settings, recording state, and file existence and size. Play the test recording to verify the actual picture and sound.

## Developer Guide

| File | Responsibility |
| --- | --- |
| [recorder.py](recorder.py) | CLI options, Chrome control, and recording flow |
| [obs_control.py](obs_control.py) | Local OBS WebSocket authentication, recording control, and save checks |
| [browser.js](browser.js) | Player discovery, playback, fullscreen, and next-button actions inside Chrome |
| [site_profiles.py](site_profiles.py) | Origin-scoped local profiles and atomic profile updates |
| [config.example.json](config.example.json) | Copyable defaults for user customization |
| [tests/](tests/) | Python tests and simulated browser tests |

`browser.js` is loaded by Python and executed inside the selected Chrome tab. You do not need to run it separately or install a browser extension.

```bash
python3 -m unittest discover -s tests -v
node tests/browser_tests.cjs
```

Tests simulate OBS communication and browser structures. Actual capture, macOS permissions, and recorded audio need a test recording on your Mac. Application messages, CLI help, and password prompts are always in English, regardless of the README language. Site labels, scene names, file paths, and error details supplied by external software retain their original language.

Keep contributions within ordinary screen recording and authorized non-DRM browser testing. Do not add DRM/key extraction, protection-disabling flags, or changes intended to circumvent browser/OS capture restrictions. Language-specific READMEs describe the same behavior; update all three when commands or defaults change.

## Resources

- [OBS WebSocket](https://github.com/obsproject/obs-websocket)
- [OBS macOS Screen Capture Guide](https://obsproject.com/kb/macos-screen-capture-source)
- [OBS macOS Desktop Audio Capture Guide](https://obsproject.com/kb/macos-desktop-audio-capture-guide)
- [BlackHole](https://github.com/ExistentialAudio/BlackHole)
- [Apple FairPlay screen-capture guidance](https://developer.apple.com/library/archive/qa/qa1970/) — an example of platform-enforced capture restrictions, not a guarantee about all DRM/browser combinations.
