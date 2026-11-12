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

# macOS Sonoma/Sequoia 등에서는 스크립트 실행 후 exec python 시 번들 식별자(CFBundleExecutable)와
# 프로세스 불일치로 ControlCenter의 NSStatusItem 연결이 거부되므로, 네이티브 런처 바이너리를 우선 빌드한다.
COMPILED=0
TMP_C=$(mktemp /tmp/token_hamster_launcher.XXXXXX.c)
if command -v clang >/dev/null 2>&1 && command -v python3-config >/dev/null 2>&1; then
  cat > "$TMP_C" <<'C'
#include <Python.h>
#include <mach-o/dyld.h>
#include <libgen.h>
#include <limits.h>

int main(int argc, char **argv) {
    char path[PATH_MAX];
    uint32_t size = sizeof(path);
    _NSGetExecutablePath(path, &size);
    char *dir = dirname(path);
    char script[PATH_MAX];
    snprintf(script, sizeof(script), "%s/../Resources/widget.py", dir);

    wchar_t **w_argv = (wchar_t **)malloc(sizeof(wchar_t *) * (argc + 2));
    w_argv[0] = Py_DecodeLocale(argv[0], NULL);
    w_argv[1] = Py_DecodeLocale(script, NULL);
    for (int i = 1; i < argc; i++) {
        w_argv[i + 1] = Py_DecodeLocale(argv[i], NULL);
    }
    w_argv[argc + 1] = NULL;
    return Py_Main(argc + 1, w_argv);
}
C
  if clang $(python3-config --cflags) "$TMP_C" -o "$APP/Contents/MacOS/TokenHamster" $(python3-config --ldflags --embed) 2>/dev/null; then
    COMPILED=1
  fi
  rm -f "$TMP_C"
fi

if [ "$COMPILED" -eq 0 ]; then
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
fi
echo "만듦: $APP (런처: $([ $COMPILED -eq 1 ] && echo '네이티브 바이너리' || echo '셸 스크립트'))"
