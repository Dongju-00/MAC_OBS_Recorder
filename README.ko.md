# macOS OBS Recorder

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md)

![플랫폼: macOS](https://img.shields.io/badge/platform-macOS-lightgrey)
![Python: 표준 라이브러리](https://img.shields.io/badge/Python-standard%20library-blue)
![OBS: WebSocket 5](https://img.shields.io/badge/OBS-WebSocket%205-302E31)

OBS Studio를 이용한 macOS 영상 자동 녹화 프로그램입니다. 현재 Chrome 영상을 녹화하고, 영상마다 별도 파일로 저장한 뒤 다음 영상으로 자동 이동합니다. 사이트 테스트를 한 번 실행하면 다음 영상 이동 방식을 찾고 설정을 저장할 수 있습니다.

[시작하기](#설치) · [녹화 안내](#사용-안내) · [사용자 설정](#사용자-설정) · [자주 묻는 질문](#자주-묻는-질문)

## 목차

- [주요 기능](#주요-기능)
- [설치](#설치)
- [OBS 설정](#obs-설정)
- [사용 안내](#사용-안내)
- [사용자 설정](#사용자-설정)
- [자주 묻는 질문](#자주-묻는-질문)
- [개발자 안내](#개발자-안내)
- [참고 자료](#참고-자료)

## 주요 기능

- OBS 장면을 통해 앱 창이나 디스플레이를 녹화합니다.
- OBS 연결, 장면 소스, BlackHole 입력, 녹화 폴더를 점검합니다.
- Chrome을 제어하지 않고 10초 테스트 녹화를 진행합니다.
- `--test`로 사이트의 이동 방식을 찾고, 짧은 샘플을 녹화하고, 검증된 사이트 프로필을 저장합니다.
- Chrome 동영상을 처음부터 녹화하고, 선택적으로 다음 동영상 버튼을 사용해 계속 녹화합니다.
- 다음 동영상으로 이동하기 전에 OBS가 중지되고 비어 있지 않은 파일이 생성됐는지 확인합니다.
- 플레이어 선택자, 녹화 수 제한, 제한 시간을 재사용 가능한 JSON 설정에 저장합니다.
- Python 표준 라이브러리만 사용합니다. Python 패키지나 API 키가 필요하지 않습니다.

## 설치

| 요구 사항 | 용도 |
| --- | --- |
| macOS | AppleScript로 Chrome과 녹화 앱 제어 |
| [OBS Studio](https://obsproject.com/download) 28 이상 | 녹화 및 내장 WebSocket 5 서버 |
| Python 3 | 스크립트 실행 |
| [BlackHole 2ch](https://existential.audio/blackhole/) | 시스템 오디오를 이 도구가 확인하는 OBS 입력으로 전달 |
| [Google Chrome](https://www.google.com/chrome/) | 브라우저 자동화에만 사용 |

저장소를 다운로드하거나 복제한 뒤 프로젝트 폴더에서 터미널을 여세요.

```bash
git clone https://github.com/Dongju-00/MAC_OBS_Recorder.git
cd MAC_OBS_Recorder
python3 --version
python3 recorder.py --help
```

Node.js는 [개발자 안내](#개발자-안내)의 브라우저 테스트에만 필요합니다.

## OBS 설정

### 1. 화면 캡처

1. OBS를 열고 녹화용 장면을 만드세요.
2. **소스 → + → macOS 화면 캡처**를 추가하세요.
3. 창 캡처에는 플레이어 창을, 화면 캡처에는 디스플레이를 선택하세요.
4. **시스템 설정 → 개인정보 보호 및 보안**에서 OBS에 화면 기록 권한을 허용하세요. 요청이 표시되면 OBS를 다시 시작하세요.
5. 미리 보기를 확인하고 캡처 크기를 조정하세요.

캡처할 창은 열어 둔 채 최소화하지 마세요. 디스플레이 캡처에는 해당 화면의 다른 창과 알림도 포함됩니다.

### 2. 시스템 오디오 캡처

OBS 점검을 통과하려면 현재 장면에 **BlackHole 2ch** 오디오 입력을 직접 추가하고 활성화한 뒤 음소거를 해제해야 합니다. 이 점검은 중첩 장면, 그룹, 전역 오디오 입력을 검색하지 않습니다.

1. BlackHole 2ch를 설치하고, 요청이 표시되면 Mac을 다시 시작하세요.
2. **오디오 MIDI 설정 → + → 다중 출력 기기 생성**을 여세요.
3. 스피커 또는 헤드폰과 **BlackHole 2ch**를 선택하세요. 기본 클록 기기 이외의 기기에는 드리프트 보정을 활성화하세요. BlackHole의 [다중 출력 기기 안내](https://github.com/ExistentialAudio/BlackHole/wiki/Multi-Output-Device)를 참고하세요.
4. **시스템 설정 → 사운드 → 출력**에서 새 기기를 선택하세요.
5. OBS에서 **소스 → + → macOS 오디오 입력 캡처**를 추가하고 **BlackHole 2ch**를 선택한 뒤 음소거를 해제하세요.
6. **설정 → 오디오**에서 사용하지 않는 데스크톱 오디오와 마이크/보조 입력을 비활성화하세요. 화면 캡처 소스에서도 오디오를 캡처한다면 중복을 피하도록 해당 오디오를 음소거하세요.
7. 동영상을 재생하고 OBS의 BlackHole 레벨 미터가 움직이는지 확인하세요. 오디오 입력 권한을 요청하면 허용하세요.

### 3. 녹화 출력 선택

**OBS → 설정 → 출력 → 녹화**에서 녹화 폴더와 형식을 설정하세요. 파일 이름과 형식은 OBS 설정을 따릅니다.

MKV로 녹화한 뒤 **파일 → 녹화 리먹스**로 MP4로 변환할 수 있습니다. 장시간 녹화 전에는 디스크 여유 공간을 확인하세요.

### 4. WebSocket 제어 활성화

1. **OBS → 도구 → WebSocket 서버 설정**을 여세요.
2. 서버를 활성화하고 기본 포트 **4455**를 유지하세요.
3. 인증을 활성화하고 서버 비밀번호를 확인하세요.
4. 연결을 점검하세요.

```bash
python3 recorder.py --check-obs
```

안내가 나오면 비밀번호를 입력하세요. 입력 내용은 표시되지 않습니다. 현재 zsh 세션에서 재사용하려면 다음을 실행하세요.

```zsh
read -s 'OBS_WEBSOCKET_PASSWORD?OBS WebSocket password: '
export OBS_WEBSOCKET_PASSWORD
```

연결 주소는 `127.0.0.1`입니다. 소스 파일이나 Git에 비밀번호를 저장하지 마세요. 서버 포트를 바꿨다면 같은 값을 `--obs-port`로 전달하세요.

## 사용 안내

### 녹화 환경 테스트

원하는 앱에서 재생을 시작한 뒤 실행하세요.

```bash
python3 recorder.py --test-recording
```

현재 OBS 장면을 **10초간** 녹화하고 저장된 파일을 확인합니다. 녹화 파일을 열어 영상과 소리를 확인하세요. 이 테스트 중에는 Chrome을 제어하지 않습니다.

다른 앱을 수동으로 녹화하려면 장면을 설정한 뒤 OBS의 **녹화 시작 / 녹화 중단** 버튼을 사용하세요.

### Chrome 자동화 준비

1. **Chrome → 보기 → 개발자 → Apple 이벤트의 JavaScript 허용**을 활성화하세요.
2. **시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용 / 자동화**에서 요청에 따라 터미널이 Chrome과 System Events를 제어하도록 허용하세요.
3. 동영상 페이지를 열고 필요하면 로그인한 뒤 대상 탭을 선택하세요.
4. 사이트의 다음 동영상 자동 재생을 끄세요. 스크립트가 저장 후 다음 동영상으로 이동합니다.
5. 동영상을 한 번 재생했다가 일시 정지해 플레이어를 로드하고 재생을 허용하세요.

### 새 사이트 한 번 테스트하기

다음 동영상이 있는 동영상을 열고 실행하세요.

```bash
python3 recorder.py --test
```

테스트는 다음 순서로 진행됩니다.

1. 레이블이나 식별 속성으로 다음 동영상 컨트롤을 찾습니다.
2. 현재 동영상을 처음으로 되감고 OBS로 최대 10초간 녹화합니다.
3. 재생 진행을 확인하고 OBS를 중지한 뒤 비어 있지 않은 파일이 저장됐는지 확인합니다.
4. 실제로 다음 동영상으로 이동해 새 미디어가 로드되고 재생되는지 확인합니다.
5. 다음 동영상을 일시 정지하고 처음으로 되감은 뒤 성공한 사이트 설정을 저장합니다.

**테스트는 현재 동영상을 변경합니다.** 성공 후 `--run`을 실행하면 현재 선택된 다음 동영상부터 시작합니다. 원래 동영상도 전체 녹화에 포함하려면 실행 전에 다시 여세요.

터미널에 표시된 샘플 파일을 열어 실제 영상과 소리를 확인하세요. 자동 점검은 캡처 구도나 소리가 들리는지 판단할 수 없습니다. 테스트 전에 OBS를 설정해야 합니다. `--test`는 EaseUS를 지원하지 않습니다.

프로필은 스크립트 옆의 `.site-profiles.json`에 저장되며 URL 스킴, 호스트 이름, 포트가 같은 사이트에서 자동으로 로드됩니다. 재사용할 때 `--config`를 지정할 필요가 없습니다. 테스트가 실패해도 이전 프로필은 교체되지 않습니다. 사이트 설정을 갱신하려면 `--test`를 다시 실행하세요.

YouTube에서는 동영상 플레이어 내부의 다음 컨트롤을 사용할 수 있으면 이용하며, 관계없는 페이지 화살표나 캐러셀 화살표는 제외합니다. 활성 또는 비활성 상태의 플레이어 다음 컨트롤을 모두 찾지 못하면 **Shift+N**을 시도하며, 미디어 전환에 성공한 경우에만 이 방식을 저장합니다. 정해진 순서로 녹화하려면 재생목록을 사용하세요. 재생목록 밖에서는 YouTube가 다음 추천 동영상을 선택합니다. 다른 사이트에서는 추측한 단축키를 사용하지 않습니다.

동일한 우선순위의 버튼이 여러 개 발견되면 테스트를 멈추고 명시적인 선택자 지정을 요청합니다.

```bash
python3 recorder.py --diagnose
python3 recorder.py --test --video-next-selector '#your-next-button'
```

선택자는 테스트가 성공하면 저장되므로 이후 실행에서는 생략할 수 있습니다. 플레이어도 모호하다면 `--video-selector`를 함께 지정하세요.

### 동영상을 바꾸지 않고 점검하기

```bash
python3 recorder.py --check
python3 recorder.py --diagnose
```

두 명령 모두 대상 탭을 앞으로 가져오지만 재생, 녹화, 다음 버튼 클릭은 시작하지 않습니다. `--check`에는 길이가 유한한 동영상 하나가 로드되어 있어야 합니다. `--diagnose`는 동영상이 없어도 버튼 후보를 나열합니다.

| 상태 필드 | 예상 결과 |
| --- | --- |
| `videoCount` | `1` |
| `playerReady` | `true`, `duration`은 양수 |
| `focused` | `true`: 해당 창에서 대상 탭이 선택됨 |
| `nextCount` | 버튼 이동 시 `1`; 검증된 YouTube 단축키는 `0`이어도 동작 가능 |
| `nextDisabledCount` | 비활성 상태인 다음 버튼 수 |
| `inaccessibleFrames` | 페이지 스크립트가 접근할 수 없는 프레임 수 |

### 동영상 하나 또는 여러 개 녹화하기

```bash
# 현재 동영상을 처음부터 녹화합니다.
python3 recorder.py --run

# 현재 동영상을 포함해 최대 10개를 녹화합니다.
python3 recorder.py --run --max-videos 10
```

저장된 사이트 설정은 자동으로 적용됩니다. 이후 페이지에서 저장된 버튼 선택자를 찾을 수 없으면 의미 기반 자동 탐색을 다시 시도하며, 후보가 모호하면 세션을 중단합니다. 명령줄이나 `--config`로 명시한 선택자는 저장된 선택자보다 우선합니다.

스크립트는 재생을 테스트하고 처음으로 되감은 뒤 OBS를 시작하고 동영상을 재생하며, 동영상이 끝나면 OBS를 중지합니다. 각 동영상은 별도 파일로 녹화됩니다. 기본적으로 전체 화면을 사용합니다. 일반 플레이어 화면을 사용하려면 `--no-fullscreen`을 추가하세요. 전체 화면 전환을 확인할 수 없으면 경고를 출력하고 일반 화면으로 녹화합니다.

OBS가 중지되고 파일 검증이 끝나면 10초간 기다린 뒤 다음 버튼이나 검증된 단축키를 사용하고 새 미디어가 로드될 때까지 기다립니다. 버튼 이동 방식에서는 활성화된 다음 버튼이 없으면 세션이 정상 종료됩니다. 단축키 이동으로 새 미디어를 로드하지 못하면 오류로 중단됩니다. 버튼 후보가 여러 개면 선택자를 지정할 수 있도록 세션을 중단합니다. 녹화 수 제한은 다음 동영상으로 이동하기 전에 확인합니다.

대상 탭을 선택한 상태로 창을 열어 두고 최소화하지 마세요. 창 캡처를 사용하면 녹화 중 다른 앱이 앞에 있어도 됩니다. 스크립트는 재생을 시작할 때 Chrome을 앞으로 가져옵니다.

중단하려면 **Control+C**를 누르세요. 스크립트는 재생을 일시 정지하고 자신이 시작한 녹화를 중지해 저장하려고 시도합니다. 정리에 실패하면 OBS에서 직접 확인하세요. 새로 실행하면 현재 동영상을 처음부터 녹화합니다.

## 사용자 설정

### 설정 저장

예제 파일을 한 번 복사한 뒤 원하는 텍스트 편집기로 `config.json`을 수정하세요.

```bash
cp config.example.json config.json
```

예제에는 지원되는 모든 설정이 들어 있으며 기존 기본값이 유지되어 있습니다. 특정 플레이어와 다음 버튼을 사용하는 사이트라면 다음 항목을 변경하세요.

```json
{
  "max_videos": 10,
  "video_selector": "#player video",
  "video_next_selector": "#next-video",
  "video_load_timeout": 60,
  "no_fullscreen": true
}
```

선택자를 해당 페이지의 값으로 바꾸고 녹화 전에 확인하세요.

```bash
python3 recorder.py --config config.json --diagnose
python3 recorder.py --config config.json --check
python3 recorder.py --config config.json --run

# 이번 실행에만 저장된 설정을 덮어씁니다.
python3 recorder.py --config config.json --run --max-videos 1 --fullscreen
```

이 설정 파일은 **`--config`를 지정할 때만** 로드됩니다. 상대 경로는 터미널의 현재 디렉터리를 기준으로 해석합니다. 녹화 옵션의 우선순위는 **명령줄 옵션 → 설정 파일 → 내장 기본값**입니다. 이 옵션들에서 지정한 비어 있지 않은 플레이어 및 다음 버튼 선택자는 자동 로드된 사이트 프로필보다 우선합니다. 필요 없는 설정은 생략할 수 있습니다. 알 수 없는 키나 잘못된 값이 있으면 Chrome이나 OBS를 제어하기 전에 오류가 발생합니다.

설정 키에는 밑줄을 사용합니다. 예를 들어 `--video-load-timeout`은 `video_load_timeout`이 됩니다. 불리언 `no_fullscreen`에는 JSON의 `true` 또는 `false`를 사용하세요. `--fullscreen`은 저장된 `true` 값을 덮어씁니다. 녹화 도구별 기본값을 사용하려면 `countdown`을 `null`로 설정하세요. `--run` 같은 실행 모드는 명령줄에 지정하고, 비밀번호는 환경 변수나 대화형 입력으로 전달하세요.

`config.json`은 Git에서 제외됩니다. 개인 설정은 여기에 저장하고, [config.example.json](config.example.json)은 다른 사용자를 위한 템플릿으로 유지하세요.

### 플레이어와 다음 버튼 선택

대부분의 사이트별 변경은 Python이나 JavaScript를 수정하지 않고 옵션으로 처리할 수 있습니다.

기본적으로 스크립트는 화면에 보이는 HTML `<video>` 하나와 `Next video`, `Next lesson`, `다음 동영상`, `다음 강의` 같은 레이블, `rel="next"` 속성 또는 다음 컨트롤 식별자로 구분되는 다음 컨트롤을 찾습니다. `(Shift+N)` 같은 단축키 접미사도 지원합니다. 동영상 전용 컨트롤은 일반적인 `Next` 레이블보다 우선합니다.

1. Chrome 개발자 도구를 열고 다음 동영상 버튼을 검사하세요.
2. 해당 요소를 마우스 오른쪽 버튼으로 클릭하고 **Copy → Copy selector**를 선택하세요.
3. 아래의 `#next-video`를 복사한 선택자로 바꾸세요. 필요하면 `#player video`도 HTML `<video>` 요소를 직접 가리키는 선택자로 바꾸세요.
4. 먼저 진단을 실행해 `nextCandidates`에 의도한 활성 버튼만 정확히 하나 들어 있는지 확인하세요.

```bash
python3 recorder.py --diagnose \
  --video-selector '#player video' \
  --video-next-selector '#next-video'

python3 recorder.py --run \
  --video-selector '#player video' \
  --video-next-selector '#next-video' \
  --max-videos 10
```

이 선택자는 예시이며 모든 사이트에 적용되는 값이 아닙니다. 다음 버튼은 **같은 탭**에서 다음 동영상을 로드해야 합니다.

동작하는 선택자를 저장하려면 `--test`와 함께 사용하세요. 저장된 사이트 프로필을 모두 초기화하려면 `.site-profiles.json`을 다른 위치로 옮기고 `--test`를 다시 실행하세요. 이 파일은 Git에서 제외되며 사이트 오리진과 선택자만 포함합니다. 동영상의 전체 URL이나 비밀번호는 포함하지 않습니다.

### 녹화 옵션

시간 단위는 모두 초입니다. 전체 명령 목록은 `python3 recorder.py --help`로 확인하세요.

| 옵션 | 기본값 | 변경이 필요한 경우 |
| --- | --- | --- |
| `--max-videos` | `1` | 현재 동영상 이후에도 계속 녹화할 때 |
| `--video-selector` | 자동 | 페이지에 보이는 동영상이 여러 개일 때 |
| `--video-next-selector` | 자동 | 다음 버튼이 없거나 모호할 때 |
| `--video-timeout` | `14400` | 동영상이 4시간을 넘을 수 있을 때 |
| `--video-load-timeout` | `45` | 첫 동영상이나 다음 동영상이 느리게 로드될 때 |
| `--no-fullscreen` | 전체 화면 사용 | 일반 플레이어 화면을 사용할 때 |
| `--fullscreen` | 전체 화면 사용 | 설정 파일의 `no_fullscreen: true`를 덮어쓸 때 |
| `--save-wait` | `10` | 다음 버튼을 누르기 전 대기 시간을 바꿀 때 |
| `--stall-seconds` | `120` | 재생 정체가 더 오래 지속될 수 있을 때 |
| `--countdown` | OBS는 `0`, EaseUS는 `6` | 녹화 시작과 재생 사이에 대기 시간이 필요할 때 |
| `--obs-port` | `4455` | OBS WebSocket 서버 포트를 변경했을 때 |

**출력 폴더, 파일 이름, 형식, 해상도, 프레임 레이트, 품질, 캡처 대상, 오디오 장치는 OBS에서 설정하세요.** 위 옵션으로는 제어하지 않습니다.

### 기존 EaseUS 제어

EaseUS 설정과 일치하는 단축키를 사용하세요.

```bash
python3 recorder.py --run --recorder easeus \
  --start-hotkey 'command+9' --stop-hotkey 'command+9'
```

두 단축키의 기본값은 모두 `command+9`입니다. 지원하는 보조 키는 `command`, `control`, `option`, `shift`이며, 뒤에 영문자나 숫자 하나가 와야 합니다. EaseUS 제어는 녹화 상태나 저장된 파일을 검증할 수 없습니다. `--test-hotkey`는 10초 테스트 모드의 별칭입니다.

## 자주 묻는 질문

### 어떤 사이트에서 자동 녹화를 지원하나요?

자동화하려면 길이가 유한하고 접근 가능한 HTML `<video>`가 필요합니다. 연속 녹화에는 같은 탭의 다음 버튼이나 검증된 YouTube 단축키도 필요합니다. 스크립트는 동일 출처 iframe과 열린 섀도 루트를 검색합니다. 교차 출처 프레임, 닫힌 섀도 루트, 실시간 스트림, 네이티브 앱 플레이어는 제어하지 못할 수 있습니다. 자동 탐색이 모든 사이트의 지원을 보장하지는 않습니다. 이런 경우에는 OBS를 수동으로 사용하세요.

### 다음 동영상으로 넘어가지 않고 중단되는 이유는 무엇인가요?

버튼이 모호하거나, 재생 오류나 정체가 발생하거나, 미디어가 예상치 못하게 변경되거나, 저장 검증에 실패하면 중단됩니다. 다음 동영상 자동 재생을 끄고 `--diagnose`로 선택자를 점검하세요. URL만 바뀐 것은 새 미디어로 판단하지 않습니다.

### 소리가 없거나 겹쳐 들리는 이유는 무엇인가요?

다중 출력 기기, 시스템 출력, OBS 오디오 권한, 음소거가 해제된 BlackHole 2ch 입력을 확인하세요. 화면 캡처나 전역 오디오 입력에서 나오는 중복 오디오는 음소거하세요. 테스트 녹화 파일을 재생해 결과를 확인하세요.

### Mac의 음량 키가 동작하지 않는 이유는 무엇인가요?

macOS는 다중 출력 기기에 일반적인 음량 조절 기능을 제공하지 않습니다. 재생 앱이나 개별 출력 기기의 음량을 조절하세요. 녹화 후에는 평소 사용하던 시스템 출력으로 되돌리세요. [BlackHole FAQ](https://github.com/ExistentialAudio/BlackHole#faq)를 참고하세요.

### 점검으로 녹화된 영상과 소리가 올바른지 확인할 수 있나요?

아니요. 스크립트는 소스 설정, 녹화 상태, 파일의 존재 여부와 크기를 확인합니다. 실제 영상과 소리는 테스트 녹화 파일을 재생해 확인하세요.

## 개발자 안내

| 파일 | 역할 |
| --- | --- |
| [recorder.py](recorder.py) | CLI 옵션, Chrome 제어, 녹화 흐름 |
| [obs_control.py](obs_control.py) | 로컬 OBS WebSocket 인증, 녹화 제어, 저장 점검 |
| [browser.js](browser.js) | Chrome 내부의 플레이어 탐색, 재생, 전체 화면, 다음 버튼 동작 |
| [site_profiles.py](site_profiles.py) | 오리진 단위 로컬 프로필과 원자적 프로필 갱신 |
| [config.example.json](config.example.json) | 사용자 설정용으로 복사할 수 있는 기본값 |
| [tests/](tests/) | Python 테스트와 모의 브라우저 테스트 |

`browser.js`는 Python이 로드해 선택한 Chrome 탭 안에서 실행합니다. 별도로 실행하거나 브라우저 확장 프로그램을 설치할 필요가 없습니다.

```bash
python3 -m unittest discover -s tests -v
node tests/browser_tests.cjs
```

테스트는 OBS 통신과 브라우저 구조를 모의 구현합니다. 실제 캡처, macOS 권한, 녹음된 오디오는 Mac에서 테스트 녹화로 확인해야 합니다. 애플리케이션 메시지, CLI 도움말, 비밀번호 입력 안내는 README 언어와 관계없이 항상 영어로 표시됩니다. 사이트 레이블, 장면 이름, 파일 경로, 외부 소프트웨어가 제공하는 오류 상세 내용은 원래 언어를 유지합니다.

언어별 README는 같은 동작을 설명합니다. 명령이나 기본값이 바뀌면 세 문서를 모두 갱신하세요.

## 참고 자료

- [OBS WebSocket](https://github.com/obsproject/obs-websocket)
- [OBS macOS 화면 캡처 안내](https://obsproject.com/kb/macos-screen-capture-source)
- [OBS macOS 데스크톱 오디오 캡처 안내](https://obsproject.com/kb/macos-desktop-audio-capture-guide)
- [BlackHole](https://github.com/ExistentialAudio/BlackHole)
