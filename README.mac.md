# TokenHamster for macOS

A macOS port of `widget.py`, maintaining full cross-platform compatibility with Windows.

[한국어 설명](README.mac.ko.md)

## Requirements

Python 3 with Tk 8.6+ and Pillow. With Homebrew:

```bash
brew install python-tk
python3 -m pip install pillow
```

Do not use macOS system `/usr/bin/python3` which ships with outdated Tk 8.5.

## Running

- From source: `python3 widget.py`
- As an app: Run `./build_mac.sh` and move `dist/TokenHamster.app` to `/Applications`. To start on login, add it to System Settings > General > Login Items.

Since the app is self-built and unsigned, on first open: Right-click in Finder > Open.

## macOS Differences

| Feature | macOS Behavior |
|---|---|
| Settings & Cache | `~/Library/Application Support/TokenHamster` |
| Default position | Bottom-right of primary screen (accounting for menu bar and Dock) |
| Menu | Right-click or Control-click |
| Dock icon | Hidden (`LSUIElement`) |
| Menu bar icon | Click the hamster status icon to show menu (hide/show widget, refresh, reset position, switch language, quit). The icon changes in real-time based on Tori's mood (hungry / base / full). Implemented natively with Cocoa `NSStatusItem`. |
| Single instance | File lock in application support directory |
| Fonts | Pretendard, falling back to Apple SD Gothic Neo |
| `--screenshot` | Uses `screencapture` for widget area capture |

## Uninstall

Quit the app, then remove `TokenHamster.app` and `~/Library/Application Support/TokenHamster`.
