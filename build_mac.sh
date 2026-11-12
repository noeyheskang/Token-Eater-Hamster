#!/bin/bash
# TokenHamster.app 만들기 (macOS). 결과: dist/TokenHamster.app
# 앱 안에는 widget.py와 pet/만 들어가고, 실행은 이 Mac에 깔린 Python 3 + Tk + Pillow로 한다.
set -euo pipefail
cd "$(dirname "$0")"

APP=dist/TokenHamster.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/pet"
cp widget.py "$APP/Contents/Resources/"
cp pet/make_pet.py "$APP/Contents/Resources/pet/"

# 아이콘: 햄스터(토리) 스프라이트로 .icns를 만든다.
TMP=$(mktemp -d)
python3 - "$TMP" "$APP/Contents/Resources/TokenHamster.icns" <<'PY'
import os, sys
from PIL import Image

out_dir = os.path.join(sys.argv[1], "icon.iconset")
os.makedirs(out_dir, exist_ok=True)
target_icns = sys.argv[2]

sys.path.insert(0, "pet")
import make_pet as mp

grid = mp.base()
im32 = mp.to_image(grid, 1)

for s in (16, 32, 128, 256, 512):
    for k in (1, 2):
        n = s * k
        name = "icon_%dx%d%s.png" % (s, s, "@2x" if k == 2 else "")
        im = im32.resize((n, n), Image.NEAREST if n >= 32 else Image.Resampling.LANCZOS)
        im.save(os.path.join(out_dir, name))

# Pillow를 통해 .icns 저장
imgs_pil = [im32.resize((n, n), Image.NEAREST) for n in (1024, 512, 256, 128, 64, 32)]
imgs_pil.append(im32.resize((16, 16), Image.Resampling.LANCZOS))
imgs_pil[0].save(target_icns, format="ICNS", append_images=imgs_pil[1:])
PY
if command -v iconutil >/dev/null 2>&1; then
  iconutil -c icns "$TMP/icon.iconset" -o "$APP/Contents/Resources/TokenHamster.icns" 2>/dev/null || true
fi
rm -rf "$TMP"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>TokenHamster</string>
  <key>CFBundleDisplayName</key><string>TokenHamster</string>
  <key>CFBundleIdentifier</key><string>local.tokenhamster.widget</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>TokenHamster</string>
  <key>CFBundleIconFile</key><string>TokenHamster</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/TokenHamster" <<'SH'
#!/bin/bash
# Tk와 Pillow가 있는 Python 3을 찾아 위젯을 띄운다.
RES="$(cd "$(dirname "$0")/../Resources" && pwd)"
for PY in /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
  if [ -x "$PY" ] && "$PY" -c "import tkinter, PIL; assert tkinter.TkVersion >= 8.6" 2>/dev/null; then
    exec "$PY" "$RES/widget.py" "$@"
  fi
done
osascript -e 'display alert "TokenHamster" message "Tk 8.6 이상과 Pillow가 있는 Python 3이 필요합니다.\n\nbrew install python-tk\npython3 -m pip install pillow"' >/dev/null
exit 1
SH
chmod +x "$APP/Contents/MacOS/TokenHamster"
echo "만듦: $APP"
