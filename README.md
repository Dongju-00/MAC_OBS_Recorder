# macOS 동영상 녹화 도우미

Mac에서 OBS로 브라우저, 동영상 플레이어, 화면에 재생되는 영상을 녹화하는 도구입니다. OBS의 화면·오디오 캡처를 설정하고, Python 스크립트로 연결 상태와 시험 녹화 파일을 확인할 수 있습니다.

일반 동영상은 OBS의 **녹화 시작 / 녹화 중단** 버튼으로 녹화합니다. 스크립트의 `--check-obs`와 `--test-recording`은 사이트나 재생 앱에 관계없이 현재 OBS 장면을 대상으로 동작합니다. `--test-recording`은 **10초 시험 녹화 전용**입니다.

`--run`을 사용하면 현재 Chrome 탭의 영상을 처음부터 녹화하고, 종료·파일 저장을 확인한 뒤 다음 영상 버튼을 눌러 연속 녹화합니다. 사이트 주소 제한은 없으며 다음 버튼과 HTML `video`를 기준으로 동작합니다.

## 준비물과 설치 링크

- Mac과 OBS Studio: [OBS 공식 설치·다운로드 페이지](https://obsproject.com/download)
- 스크립트 실행용 Python 3: `python3 --version`으로 설치 확인
- 시스템 소리 입력용 BlackHole 2ch: [BlackHole 공식 설치·다운로드 페이지](https://existential.audio/blackhole/)
- Chrome 자동화를 사용할 경우 Google Chrome

OBS 제어에는 OBS 28 이상에 포함된 WebSocket 5 서버가 필요합니다. Python 코드는 표준 라이브러리만 사용하므로 `pip install`이나 API 키가 필요 없습니다. Node.js는 브라우저 테스트를 실행할 때만 필요합니다.

## 1. 화면 캡처 설정

1. OBS를 설치하고 실행한 뒤 녹화용 장면을 만듭니다.
2. **소스 → + → macOS 화면 캡처**를 추가합니다.
3. 특정 앱만 담으려면 **윈도우 캡처**로 재생 창을 선택합니다. 화면 전체를 담으려면 해당 디스플레이를 선택합니다.
4. macOS가 요청하는 화면 녹화 권한을 허용합니다. **시스템 설정 → 개인정보 보호 및 보안**에서 OBS 권한을 확인하고, 변경 후 필요하면 OBS를 다시 실행합니다.
5. OBS 미리보기에서 영상이 잘리지 않고 원하는 크기로 보이는지 확인합니다.

윈도우 캡처 중에는 대상 창을 최소화하거나 닫지 마세요. 디스플레이 캡처에는 그 화면에 표시되는 다른 창과 알림도 함께 담깁니다.

## 2. 시스템 소리 설정

스크립트의 OBS 점검은 현재 장면에 **음소거되지 않은 BlackHole 2ch 입력 소스**가 있는지 확인합니다. 아래 설정은 이 점검 기준에 맞춘 방법입니다.

1. BlackHole 2ch를 설치하고 설치 안내에 따라 Mac을 재시작합니다.
2. **오디오 MIDI 설정** 앱에서 왼쪽 아래 **+ → 다중 출력 장치 생성**을 선택합니다.
3. 사용 중인 스피커·이어폰과 **BlackHole 2ch**를 체크합니다. 주 장치 외 장치의 드리프트 보정을 설정합니다.
4. **시스템 설정 → 사운드 → 출력**을 방금 만든 다중 출력 장치로 바꿉니다.
5. OBS에서 **소스 → + → macOS 오디오 입력 캡처**를 추가하고 장치를 **BlackHole 2ch**로 선택합니다. 음소거는 해제합니다.
6. 같은 소리가 중복 입력되지 않도록 OBS **설정 → 오디오**의 데스크톱 오디오와 Mic/Aux는 사용 안 함으로 둡니다. 화면 캡처 소스에도 소리가 입력되면 오디오 믹서에서 해당 소스의 소리만 음소거하고 BlackHole 입력만 사용합니다.
7. 동영상을 재생하고 OBS 오디오 믹서의 레벨이 움직이는지 확인합니다. 오디오 입력 권한을 요청하면 허용합니다.

다중 출력 장치에서는 Mac 볼륨 키가 동작하지 않을 수 있습니다. 재생 앱의 볼륨이나 출력 장치의 볼륨으로 조절하세요. 녹화를 마친 뒤에는 시스템 사운드 출력을 평소 사용하던 장치로 돌려놓을 수 있습니다.

## 3. 저장 경로와 형식 설정

OBS **설정 → 출력 → 녹화**에서 저장 경로와 녹화 형식을 지정합니다. 파일 이름과 형식은 OBS 설정을 따릅니다.

MKV로 녹화한 파일은 필요하면 OBS의 **파일 → 녹화 리먹스**에서 MP4로 변환할 수 있습니다. 녹화 전에 저장 공간을 확인하세요.

## 4. OBS 제어 연결 설정

일반 녹화를 OBS 버튼으로만 진행한다면 이 단계와 Python 명령은 생략할 수 있습니다. 스크립트로 연결 점검과 시험 녹화를 하려면 다음을 설정합니다.

1. OBS **도구 → WebSocket 서버 설정**을 엽니다.
2. **WebSocket 서버 활성화**를 켭니다.
3. 포트는 기본값 **4455**를 사용합니다.
4. 인증을 켜고 서버 비밀번호를 확인합니다.

터미널에서 프로젝트 폴더로 이동한 뒤 실행합니다. 다른 경로에 내려받았다면 `cd` 경로를 바꾸세요.

```bash
cd ~/Downloads/OBS_mac_recorder
python3 recorder.py --check-obs
```

인증이 켜져 있으면 비밀번호를 묻습니다. 입력한 글자는 화면에 표시되지 않습니다. 성공하면 현재 장면, 녹화 중 여부, 저장 폴더와 윈도우 캡처 대상(해당 시)을 출력합니다. Chrome 이외 앱의 캡처 경고가 나오면 의도한 대상인지 확인하세요.

매번 입력하지 않으려면 zsh에서 현재 터미널 세션에만 비밀번호를 설정합니다.

```zsh
read -s 'OBS_WEBSOCKET_PASSWORD?OBS WebSocket 비밀번호: '
export OBS_WEBSOCKET_PASSWORD
```

서버 포트를 바꿨다면 각 명령에 `--obs-port 4456`처럼 실제 포트를 추가합니다. 연결 주소는 이 Mac의 `127.0.0.1`로 고정되어 있습니다. 비밀번호는 코드나 Git에 저장하지 마세요.

## 5. Chrome 동영상 자동 녹화

### Chrome 권한 설정

1. Chrome **보기 → 개발자 → Apple 이벤트의 JavaScript 허용**을 켭니다.
2. macOS **개인정보 보호 및 보안 → 손쉬운 사용 / 자동화**에서 실행에 사용하는 터미널이 Chrome과 System Events를 제어하도록 허용합니다.
3. 녹화할 동영상 페이지에 로그인하고 대상 탭을 선택합니다.
4. 사이트의 **자동 다음 재생은 끕니다.** 스크립트가 파일 저장을 확인하고 다음 버튼을 누릅니다.
5. 플레이어를 한 번 직접 재생하고 일시정지해 로딩과 사용자 입력을 준비합니다.

### 현재 영상과 다음 버튼 점검

```bash
python3 recorder.py --check
python3 recorder.py --diagnose
```

대상 Chrome 창과 탭을 앞으로 가져온 뒤 상태를 출력합니다. 재생·녹화·버튼 클릭은 하지 않습니다. `--check`에서는 영상이 하나이고 길이를 읽을 수 있는지도 검사합니다. `--diagnose`는 영상이 없어도 버튼 후보를 출력합니다.

- `videoCount: 1`: 선택된 HTML 영상이 하나
- `playerReady: true`, 양수 `duration`: 영상이 로드되었고 길이를 읽을 수 있음
- `focused: true`: 대상 창에서 영상 탭이 선택되어 있음
- `nextCount: 1`: 활성화된 다음 영상 버튼이 하나
- `nextDisabledCount`: 비활성화된 다음 버튼 수
- `inaccessibleFrames`: Chrome 페이지 코드에서 접근할 수 없는 iframe 수

다음 버튼은 기본으로 `다음`, `다음 영상`, `Next`, `Next video` 레이블 또는 `rel="next"`를 찾습니다. 버튼이 없거나 비활성화되면 현재 영상 저장 후 종료합니다. 후보가 여러 개면 이동하지 않고 중단합니다.

### 사이트에 맞는 버튼 설정

기본 탐색으로 다음 버튼을 찾지 못하면 CSS 선택자를 지정합니다. Chrome 개발자 도구의 요소 선택 기능으로 **다음 영상 버튼**을 선택하고 우클릭 → **Copy → Copy selector**로 복사할 수 있습니다. 다음 예제의 선택자는 실제 페이지에 맞게 바꾸세요.

```bash
python3 recorder.py --diagnose --video-next-selector '#next-video'
python3 recorder.py --check --video-next-selector '#next-video'
```

`nextCandidates`에 의도한 버튼 하나가 표시되는지 확인합니다. 선택한 버튼은 현재 탭의 다음 영상을 열어야 합니다. 새 탭·새 창을 여는 링크는 지원하지 않습니다.

화면에 영상이 여러 개 있으면 실제 플레이어를 가리키는 선택자도 지정합니다. 선택자는 HTML `<video>` 요소 자체를 가리켜야 합니다.

```bash
python3 recorder.py --check \
  --video-selector '#player video' \
  --video-next-selector '#next-video'
```

### 영상 하나 또는 여러 개 녹화

현재 영상을 처음부터 하나만 녹화하려면:

```bash
python3 recorder.py --run
```

현재 영상을 포함해 최대 10개를 연속 녹화하려면:

```bash
python3 recorder.py --run \
  --max-videos 10 \
  --video-next-selector '#next-video'
```

실행 순서는 **재생 시험 → 일시정지·0초 복귀 → OBS 시작 → 영상 재생 → 영상 종료 → OBS 종료·파일 확인 → 대기 → 다음 버튼 클릭 → 새 영상 로딩 확인**입니다. 영상마다 새 녹화 파일을 만듭니다. `--max-videos`에 도달하면 다음 버튼을 누르지 않습니다.

기본으로 플레이어를 전체화면으로 녹화합니다. 일반 화면으로 녹화하려면 `--no-fullscreen`을 추가합니다. 대상 Chrome 창의 탭을 바꾸거나 창을 최소화·닫지 마세요. 윈도우 캡처라면 다른 앱으로 전환해도 대상 탭은 선택된 상태를 유지해야 합니다. 녹화 시작 시에는 Chrome을 다시 앞으로 가져옵니다.

`Control+C`로 중단하면 영상을 일시정지하고 이 실행이 시작한 녹화를 종료·저장하려고 시도합니다. 종료 확인에 실패하면 OBS에서 직접 상태와 파일을 확인하세요. 재실행은 현재 탭의 영상을 처음부터 새로 녹화하며 자동 이어받기는 지원하지 않습니다.

### 옵션

| 옵션 | 기본값 | 용도 |
| --- | --- | --- |
| `--max-videos 10` | 1 | 현재 영상을 포함한 총 녹화 수 |
| `--video-next-selector '#next-video'` | 자동 탐색 | 다음 영상 버튼 CSS 선택자 |
| `--video-selector '#player video'` | 보이는 모든 video 중 하나 | 녹화할 HTML video 선택자 |
| `--video-timeout 14400` | 14,400초 | 영상 하나의 최대 재생 대기시간 |
| `--video-load-timeout 45` | 45초 | 첫 영상과 다음 영상의 로딩 대기시간 |
| `--no-fullscreen` | 전체화면 사용 | 일반 화면으로 녹화 |
| `--save-wait 10` | 10초 | 저장 확인 후 다음 버튼을 누르기 전 대기 |
| `--stall-seconds 120` | 120초 | 영상 진행 정체 시 중단 기준 |
| `--countdown 2` | OBS 0초 | 녹화 시작 후 재생 전 추가 대기 |
| `--obs-port 4455` | 4455 | 로컬 OBS WebSocket 서버 포트 |

기존 EaseUS 단축키 제어는 `--recorder easeus`로 선택합니다. 이때만 `--start-hotkey`, `--stop-hotkey`를 사용하며 둘 다 기본값은 `command+9`입니다. EaseUS는 실제 녹화 상태와 저장 파일을 확인하지 못합니다. `--test-hotkey`는 10초 시험 녹화의 별칭입니다.

### 자동화 지원 범위

접근 가능한 HTML `video`와 같은 탭에서 동작하는 다음 버튼이 필요합니다. 같은 출처의 iframe과 열린 shadow root도 탐색합니다. 다른 출처의 iframe, 닫힌 shadow root, 길이가 없는 라이브 방송, 별도 앱의 플레이어는 자동 제어하지 못할 수 있습니다. 이런 경우 OBS 버튼으로 직접 녹화할 수 있습니다.

URL 변경만으로 새 영상이라고 판단하지 않습니다. 실제 video 요소 교체나 미디어 로딩 갱신을 기다립니다. 자동 재생으로 영상이 먼저 바뀌거나 재생 오류·정체·저장 실패가 발생하면 다음 버튼을 누르지 않고 중단합니다.

## 파일 구성과 검증

- `recorder.py`: 명령행 실행, Chrome 제어, 녹화 흐름 관리
- `obs_control.py`: 로컬 OBS WebSocket 연결·인증, 녹화 시작·종료와 파일 확인
- `browser.js`: **Chrome 페이지 안에서 실행되는 JavaScript**. HTML video의 재생·일시정지·종료 상태와 다음 버튼을 읽고 조작합니다. Python이 필요할 때 Chrome에 전달하므로 직접 실행하거나 브라우저 확장으로 설치하지 않습니다. 다음 화면으로의 이동은 이 파일의 버튼 클릭이 담당합니다.
- `tests/`: Python 및 브라우저 모사 테스트

```bash
python3 -m unittest discover -s tests -v
node tests/browser_tests.cjs
```

테스트는 OBS 통신과 브라우저 구조를 모사합니다. 실제 OBS 앱, macOS 권한, 캡처한 화면과 시스템 소리는 Mac에서 시험 녹화 파일을 재생해 확인해야 합니다.

참고: [OBS WebSocket](https://github.com/obsproject/obs-websocket), [macOS 화면 캡처](https://obsproject.com/kb/macos-screen-capture-source), [macOS 오디오 캡처](https://obsproject.com/kb/macos-desktop-audio-capture-guide)
