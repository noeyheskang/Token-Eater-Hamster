# TokenHamster Mac판

원본(Windows 전용) `widget.py`에 Mac 분기를 더한 판이다. Windows 동작은 그대로 둔다.

## 준비

Tk 8.6 이상과 Pillow가 있는 Python 3이 필요하다. Homebrew라면:

```
brew install python-tk
python3 -m pip install pillow
```

macOS 기본 `/usr/bin/python3`의 Tk 8.5는 쓰지 않는다.

## 실행

- 소스로: `python3 widget.py`
- 앱으로: `./build_mac.sh` → `dist/TokenHamster.app`을 `/Applications`로 옮겨 연다. 로그인할 때 켜려면 시스템 설정 > 일반 > 로그인 항목에 넣는다.

서명하지 않은 앱이라 처음 열 때 막히면 Finder에서 오른쪽 클릭 > 열기.

## Mac에서 달라진 점

| 항목 | Mac 동작 |
|---|---|
| 설정·캐시 | `~/Library/Application Support/TokenHamster` |
| 기본 위치 | 주 화면에서 메뉴 막대·Dock을 뺀 영역의 오른쪽 아래 |
| 메뉴 | 오른쪽 클릭 또는 Control+클릭 |
| Dock 아이콘 | 없음 |
| 메뉴 막대 아이콘 | 햄스터 아이콘을 누르면 위젯 숨기기/보이기·새로고침·위치 초기화·종료 메뉴가 뜹니다. 아이콘은 햄스터 상태(배고픔·보통·배부름)에 따라 실시간으로 바뀝니다. (Cocoa NSStatusItem 네이티브 구현) |
| 중복 실행 | 설정 폴더의 잠금 파일로 막음 |
| 글꼴 | Pretendard, 없으면 Apple SD Gothic Neo |
| `--screenshot` | `screencapture`로 위젯 영역만 찍음(겹친 창이 있으면 같이 찍힘) |

## 지우기

앱을 종료하고 `TokenHamster.app`과 `~/Library/Application Support/TokenHamster`를 지운다.

메뉴 막대에 아이콘이 많으면 노치 뒤로 가려질 수 있다. 다른 아이콘을 줄이거나 Command를 누른 채 아이콘을 끌어 순서를 바꾼다.
