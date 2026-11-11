# macOS OBS Recorder

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md)

![平台：macOS](https://img.shields.io/badge/platform-macOS-lightgrey)
![Python：标准库](https://img.shields.io/badge/Python-standard%20library-blue)
![OBS：WebSocket 5](https://img.shields.io/badge/OBS-WebSocket%205-302E31)

一款使用 OBS Studio 的 macOS 视频自动录制程序。它录制当前 Chrome 视频，将每个视频保存为独立文件，然后自动跳转到下一个视频。先运行一次网站测试，即可查找下一个视频的导航方式并保存设置。

[快速上手](#安装) · [录制指南](#使用指南) · [自定义设置](#自定义设置) · [常见问题](#常见问题)

## 目录

- [功能](#功能)
- [安装](#安装)
- [OBS 设置](#obs-设置)
- [使用指南](#使用指南)
- [自定义设置](#自定义设置)
- [常见问题](#常见问题)
- [开发指南](#开发指南)
- [参考资料](#参考资料)

## 功能

- 通过 OBS 场景录制应用窗口或显示器画面。
- 检查 OBS 连接、场景来源、BlackHole 输入和录制目录。
- 无需控制 Chrome，即可进行 10 秒测试录制。
- 运行 `--test`，自动查找网站导航控件、录制短样本，并保存验证通过的网站配置。
- 从头录制 Chrome 中的视频，并可通过“下一个视频”按钮继续录制。
- 跳转前确认 OBS 已停止录制，且已生成非空文件。
- 将播放器选择器、录制数量上限和超时设置保存到可重复使用的 JSON 配置中。
- 仅使用 Python 标准库，无需安装 Python 包或提供 API 密钥。

## 安装

| 所需软件或系统 | 用途 |
| --- | --- |
| macOS | 通过 AppleScript 控制 Chrome 和录制应用 |
| [OBS Studio](https://obsproject.com/download) 28 或更高版本 | 录制及内置 WebSocket 5 服务器 |
| Python 3 | 运行脚本 |
| [BlackHole 2ch](https://existential.audio/blackhole/) | 将系统音频路由到本工具检查的 OBS 输入 |
| [Google Chrome](https://www.google.com/chrome/) | 仅用于浏览器自动化 |

下载或克隆本仓库，然后在项目文件夹中打开终端：

```bash
git clone https://github.com/Dongju-00/MAC_OBS_Recorder.git
cd MAC_OBS_Recorder
python3 --version
python3 recorder.py --help
```

只有运行[开发指南](#开发指南)中的浏览器测试时才需要 Node.js。

## OBS 设置

### 1. 捕获视频画面

1. 打开 OBS，创建一个录制场景。
2. 添加 **来源 → + → macOS 屏幕捕获**。
3. 如需捕获窗口，选择播放器窗口；如需捕获屏幕，选择显示器。
4. 在 **系统设置 → 隐私与安全性** 中授予 OBS 屏幕录制权限。若系统提示，请重启 OBS。
5. 检查预览画面，调整捕获尺寸。

请保持被捕获的窗口打开，不要最小化。捕获显示器时，该显示器上的其他窗口和通知也会被录入。

### 2. 捕获系统音频

OBS 检查要求当前场景中直接添加了已启用且未静音的 **BlackHole 2ch** 音频输入。该检查不会搜索嵌套场景、分组或全局音频输入。

1. 安装 BlackHole 2ch，并按提示重启 Mac。
2. 打开 **音频 MIDI 设置 → + → 创建多输出设备**。
3. 选中扬声器或耳机，以及 **BlackHole 2ch**。为主时钟设备以外的设备启用漂移校正。参见 BlackHole 的[多输出设备指南](https://github.com/ExistentialAudio/BlackHole/wiki/Multi-Output-Device)。
4. 在 **系统设置 → 声音 → 输出** 中选择新设备。
5. 在 OBS 中添加 **来源 → + → macOS 音频输入捕获**，选择 **BlackHole 2ch**，并取消静音。
6. 在 **设置 → 音频** 中禁用不使用的桌面音频和麦克风／辅助音频输入。如果屏幕捕获来源也捕获音频，请将该音频静音，以免重复收音。
7. 播放视频，确认 OBS 中的 BlackHole 音量表有变化。如有提示，请授予音频输入权限。

### 3. 选择录制输出

在 **OBS → 设置 → 输出 → 录制** 中设置录制目录和格式。文件名和格式遵循 OBS 设置。

可以先录制为 MKV，再通过 **文件 → 录像转封装** 转换为 MP4。长时间录制前，请检查可用磁盘空间。

### 4. 启用 WebSocket 控制

1. 打开 **OBS → 工具 → WebSocket 服务器设置**。
2. 启用服务器，保留默认端口 **4455**。
3. 启用身份验证，并记下服务器密码。
4. 检查连接：

```bash
python3 recorder.py --check-obs
```

按提示输入密码，输入内容不会显示。如需在当前 zsh 会话中重复使用该密码：

```zsh
read -s 'OBS_WEBSOCKET_PASSWORD?OBS WebSocket password: '
export OBS_WEBSOCKET_PASSWORD
```

连接地址为 `127.0.0.1`。请勿将密码写入源文件或提交到 Git。如果更改了服务器端口，请传入对应的 `--obs-port` 值。

## 使用指南

### 测试录制设置

在任意应用中开始播放，然后运行：

```bash
python3 recorder.py --test-recording
```

此命令会录制当前 OBS 场景 **10 秒**，并检查保存的文件。请打开录像，确认画面和声音。此测试不会控制 Chrome。

如需手动录制其他应用，请设置好场景后使用 OBS 的 **开始录制／停止录制** 按钮。

### 准备 Chrome 自动化

1. 启用 **Chrome → 视图 → 开发者 → 允许来自 Apple 事件的 JavaScript**。
2. 在 **系统设置 → 隐私与安全性 → 辅助功能／自动化** 中，按提示允许终端控制 Chrome 和 System Events。
3. 打开视频页面，按需登录，并选中目标标签页。
4. 关闭网站自动播放下一个视频的功能。脚本会在保存后跳转。
5. 播放视频一次后暂停，让播放器完成加载并允许后续播放。

### 首次使用网站时运行测试

打开一个后面还有下一个视频的视频，然后运行：

```bash
python3 recorder.py --test
```

测试将执行以下操作：

1. 根据标签或可识别属性查找“下一个视频”控件。
2. 将当前视频跳回开头，并通过 OBS 录制最多 10 秒。
3. 检查播放进度，停止 OBS，并验证保存的文件非空。
4. 实际跳转到下一个视频，检查新媒体是否已加载且可以播放。
5. 暂停下一个视频并将其跳回开头，然后保存测试成功的网站设置。

**测试会切换当前视频。** 测试成功后，`--run` 将从此时选中的下一个视频开始录制。如果希望完整录制原来的视频，请在运行前重新打开它。

请打开终端输出的样本文件，检查实际画面和声音。自动检查无法判断取景范围或声音是否可听见。测试前必须配置好 OBS；`--test` 不支持 EaseUS。

网站配置保存在脚本旁的 `.site-profiles.json` 中。访问相同协议、主机名和端口的网站时会自动加载，无需传入 `--config`。失败的测试不会替换已有配置。如需更新网站配置，请再次运行 `--test`。

YouTube 会优先使用视频播放器内部的“下一个”控件，并排除无关的页面箭头和轮播箭头。如果没有找到已启用或已禁用的播放器“下一个”控件，测试会尝试 **Shift+N**，且仅在成功切换媒体后才保存此方法。如需确定的播放顺序，请使用播放列表；不在播放列表中时，由 YouTube 选择下一个推荐视频。脚本不会为其他网站猜测快捷键。

如果找到多个匹配程度相同的按钮，测试会停止，并要求明确指定选择器：

```bash
python3 recorder.py --diagnose
python3 recorder.py --test --video-next-selector '#your-next-button'
```

测试成功后会保存该选择器，后续运行时可以省略。如果播放器本身也存在歧义，请同时传入 `--video-selector`。

### 检查而不切换视频

```bash
python3 recorder.py --check
python3 recorder.py --diagnose
```

这两个命令都会将目标标签页切到前台，但不会开始播放、录制或点击“下一个”。`--check` 要求有且仅有一个已加载且时长有限的视频。即使没有可用视频，`--diagnose` 也会列出候选按钮。

| 状态字段 | 预期结果 |
| --- | --- |
| `videoCount` | `1` |
| `playerReady` | `true`，且 `duration` 为正数 |
| `focused` | `true`：目标标签页在其窗口中处于选中状态 |
| `nextCount` | 按钮导航时为 `1`；经过测试的 YouTube 快捷键在值为 `0` 时也可能有效 |
| `nextDisabledCount` | 已禁用的“下一个”按钮数量 |
| `inaccessibleFrames` | 页面脚本无法访问的框架数量 |

### 录制一个或多个视频

```bash
# 从头录制当前视频。
python3 recorder.py --run

# 最多录制 10 个视频，包含当前视频。
python3 recorder.py --run --max-videos 10
```

保存的网站设置会自动应用。如果保存的按钮选择器在后续页面中失效，脚本会再次尝试根据语义查找；候选结果有歧义时，会停止录制会话。命令行或 `--config` 中明确提供的选择器会覆盖已保存的选择器。

脚本会测试播放、跳回开头、启动 OBS、播放视频，并在视频结束时停止 OBS。每个视频单独生成一个录制文件。默认启用全屏；添加 `--no-fullscreen` 可使用普通播放器视图。如果无法确认已进入全屏，脚本会记录警告，并在普通视图中录制。

OBS 停止且文件验证通过后，脚本会等待 10 秒，使用“下一个”按钮或经过测试的快捷键跳转，再等待新媒体加载。使用按钮导航时，如果没有已启用的“下一个”按钮，会正常结束录制会话。如果快捷键导航无法加载新媒体，则会报错并停止。存在多个候选按钮时，脚本会停止，以便您指定选择器。跳转前会先检查录制数量是否已达上限。

请保持目标标签页选中、窗口打开且未最小化。使用窗口捕获时，录制过程中其他应用可以位于前台；脚本会在开始播放时将 Chrome 切到前台。

按 **Control+C** 可中断。脚本会尝试暂停播放，并停止、保存由它启动的录制。如果清理失败，请直接检查 OBS。再次运行会从头录制当前视频。

## 自定义设置

### 保存设置

先复制一次示例文件，然后使用任意文本编辑器修改 `config.json`：

```bash
cp config.example.json config.json
```

示例包含所有受支持的设置，并保留现有默认值。如果网站需要指定播放器和“下一个”按钮，可修改以下条目：

```json
{
  "max_videos": 10,
  "video_selector": "#player video",
  "video_next_selector": "#next-video",
  "video_load_timeout": 60,
  "no_fullscreen": true
}
```

将选择器替换为页面中的实际值，并在录制前检查：

```bash
python3 recorder.py --config config.json --diagnose
python3 recorder.py --config config.json --check
python3 recorder.py --config config.json --run

# 仅在本次运行中覆盖已保存的设置。
python3 recorder.py --config config.json --run --max-videos 1 --fullscreen
```

此配置文件**只有在传入 `--config` 时才会加载**。相对路径以终端当前目录为基准解析。录制选项的优先级为：**命令行选项 → 配置文件 → 内置默认值**。这些选项中的非空播放器和“下一个”按钮选择器会覆盖自动加载的网站配置。可以省略不需要的设置。未知键或无效值会在控制 Chrome 或 OBS 之前报错。

配置键使用下划线：`--video-load-timeout` 对应 `video_load_timeout`。布尔值 `no_fullscreen` 使用 JSON 的 `true` 或 `false`；`--fullscreen` 会覆盖保存的 `true`。将 `countdown` 设为 `null`，即可使用对应录制工具的默认值。`--run` 等运行模式仍须在命令行中指定；密码请通过环境变量或交互提示提供。

Git 会忽略 `config.json`。请将个人修改保存在该文件中，并保留 [config.example.json](config.example.json) 作为供其他用户使用的模板。

### 选择播放器和下一个按钮

大多数网站专用设置都可以通过选项完成，无需修改 Python 或 JavaScript。

默认情况下，脚本会查找一个可见的 HTML `<video>`，并通过 `Next video`、`Next lesson`、`다음 동영상`、`다음 강의` 等标签、`rel="next"` 属性或“下一个”控件标识来查找对应控件。支持 `(Shift+N)` 等快捷键后缀。视频专用控件的优先级高于通用的 `Next` 标签。

1. 打开 Chrome 开发者工具，检查“下一个视频”按钮。
2. 右键点击对应元素，选择 **复制 → 复制选择器**。
3. 将下面的 `#next-video` 替换为该选择器。如有需要，将 `#player video` 替换为直接指向 HTML `<video>` 元素的选择器。
4. 先运行诊断，确认 `nextCandidates` 中恰好只有预期的已启用按钮。

```bash
python3 recorder.py --diagnose \
  --video-selector '#player video' \
  --video-next-selector '#next-video'

python3 recorder.py --run \
  --video-selector '#player video' \
  --video-next-selector '#next-video' \
  --max-videos 10
```

这些选择器仅为示例，并非通用值。“下一个”按钮必须在**同一标签页**中加载下一个视频。

如需保存有效的选择器，请配合 `--test` 使用。如需重置所有已保存的网站配置，请将 `.site-profiles.json` 移到其他位置，再次运行 `--test`。Git 会忽略此文件；其中包含网站源信息（协议、主机名和端口）及选择器，不包含完整视频 URL 或密码。

### 录制选项

所有时间均以秒为单位。运行 `python3 recorder.py --help` 可查看完整命令列表。

| 选项 | 默认值 | 何时修改 |
| --- | --- | --- |
| `--max-videos` | `1` | 希望录制多个视频。 |
| `--video-selector` | 自动 | 页面中有多个可见视频。 |
| `--video-next-selector` | 自动 | 找不到“下一个”按钮，或存在歧义。 |
| `--video-timeout` | `14400` | 视频可能超过四小时。 |
| `--video-load-timeout` | `45` | 首个或下一个视频加载较慢。 |
| `--no-fullscreen` | 启用全屏 | 希望使用普通播放器视图。 |
| `--fullscreen` | 启用全屏 | 希望覆盖配置文件中的 `no_fullscreen: true`。 |
| `--save-wait` | `10` | 希望调整点击“下一个”前的等待时间。 |
| `--stall-seconds` | `120` | 播放可能停滞更长时间。 |
| `--countdown` | OBS 为 `0`；EaseUS 为 `6` | 需要在开始录制与开始播放之间增加延迟。 |
| `--obs-port` | `4455` | 更改了 OBS WebSocket 服务器端口。 |

请在 **OBS 中设置输出文件夹、文件名、格式、分辨率、帧率、画质、捕获目标和音频设备**。上述选项不控制这些设置。

### 旧版 EaseUS 控制方式

请使用与 EaseUS 设置一致的快捷键：

```bash
python3 recorder.py --run --recorder easeus \
  --start-hotkey 'command+9' --stop-hotkey 'command+9'
```

两个快捷键的默认值均为 `command+9`。支持的修饰键包括 `command`、`control`、`option` 和 `shift`，后接单个字母或数字。EaseUS 控制方式无法验证录制状态或保存的文件。`--test-hotkey` 是 10 秒测试模式的别名。

## 常见问题

### 哪些网站支持自动录制？

自动化要求存在可访问且时长有限的 HTML `<video>`。继续录制还需要同一标签页内的“下一个”按钮，或经过测试的 YouTube 快捷键。脚本会搜索同源 iframe 和开放的 Shadow DOM；跨源框架、封闭的 Shadow DOM、直播和原生应用播放器可能无法控制。自动发现功能不保证支持所有网站。遇到这些情况时，请手动使用 OBS。

### 为什么脚本停止了，没有跳转到下一个视频？

当按钮存在歧义、播放出错、播放停滞、媒体意外变化或保存验证失败时，脚本会停止。请关闭自动播放下一个视频，并使用 `--diagnose` 检查选择器。仅 URL 发生变化不算加载了新媒体。

### 为什么没有声音，或者声音重叠？

请检查多输出设备、系统输出、OBS 音频权限，以及未静音的 BlackHole 2ch 输入。将屏幕捕获或全局音频输入中的重复音频静音。回放测试录像以确认结果。

### 为什么 Mac 音量键失效了？

macOS 不为多输出设备提供通常的音量控制。请调整播放应用或单个输出设备的音量。录制后请恢复常用的系统输出。参见 [BlackHole 常见问题](https://github.com/ExistentialAudio/BlackHole#faq)。

### 检查能确认录制的画面和声音正确吗？

不能。脚本只检查来源设置、录制状态，以及文件是否存在且非空。请播放测试录像，验证实际画面和声音。

## 开发指南

| 文件 | 职责 |
| --- | --- |
| [recorder.py](recorder.py) | 命令行选项、Chrome 控制和录制流程 |
| [obs_control.py](obs_control.py) | 本地 OBS WebSocket 身份验证、录制控制和保存检查 |
| [browser.js](browser.js) | 在 Chrome 中查找播放器，执行播放、全屏和“下一个”按钮操作 |
| [site_profiles.py](site_profiles.py) | 按网站源隔离的本地配置，以及配置的原子更新 |
| [config.example.json](config.example.json) | 可复制使用的自定义设置默认值 |
| [tests/](tests/) | Python 测试和模拟浏览器测试 |

`browser.js` 由 Python 加载，并在选中的 Chrome 标签页内执行。无需单独运行它，也无需安装浏览器扩展。

```bash
python3 -m unittest discover -s tests -v
node tests/browser_tests.cjs
```

测试会模拟 OBS 通信和浏览器结构。实际捕获、macOS 权限及录制音频需要在您的 Mac 上通过测试录制验证。无论 README 使用哪种语言，应用消息、命令行帮助和密码提示始终为英语。网站标签、场景名称、文件路径，以及外部软件提供的错误详情保留原始语言。

各语言版本的 README 描述相同行为；命令或默认值更改时，请同步更新全部三个版本。

## 参考资料

- [OBS WebSocket](https://github.com/obsproject/obs-websocket)
- [OBS macOS 屏幕捕获指南](https://obsproject.com/kb/macos-screen-capture-source)
- [OBS macOS 桌面音频捕获指南](https://obsproject.com/kb/macos-desktop-audio-capture-guide)
- [BlackHole](https://github.com/ExistentialAudio/BlackHole)
