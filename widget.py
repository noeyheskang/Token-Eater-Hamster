# -*- coding: utf-8 -*-
"""Claude 사용량 위젯: 로컬 Claude Code 로그에서 토큰 사용량을 읽어 보여 준다."""
import sys, os, json, time, threading, queue, argparse, ctypes
from datetime import datetime
from ctypes import wintypes

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")
# 실행 파일(exe)로 묶였을 때는 사용 기록 캐시와 설정을 %LOCALAPPDATA%\TokenHamster 에 둔다.
FROZEN = getattr(sys, "frozen", False)
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "TokenHamster") if FROZEN else APP_DIR
os.makedirs(DATA_DIR, exist_ok=True)
CACHE_PATH = os.path.join(DATA_DIR, "cache.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
KEEP_SEC = 8 * 86400
H5 = 5 * 3600
D7 = 7 * 86400

INK, CREAM, MUTED, HAIR, ORANGE, RED = "#26251e", "#f7f7f4", "#a09c92", "#45433a", "#f54e00", "#cf2d56"
BAR_NORMAL = "#cfcbbf"
RECENT = 180                       # 최근 3분 안에 토큰을 썼으면 '먹는 중'
NAME = "토리"                      # 햄스터 기본 이름 (오른쪽 클릭 > 이름 바꾸기로 사용자마다 바꿈)
NAME_MAX = 8                       # 이름 최대 글자 수
HUNGRY_BELOW, FULL_FROM = 15, 80   # 평소 최대 대비 %: 이보다 낮으면 배고픔 / 이 이상이면 배부름
MOOD_TEXT = {"hungry": "배고파요…", "eat": "냠냠 먹는 중", "base": "기분 좋아요", "full": "배불러요!"}
SEED = ("..#..", ".###.", ".###.", "#####", "#####", "#####", ".###.")      # 게이지용 씨앗 모양


# ---------------------------------------------------------------- 스캔
def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            c = json.load(f)
        if c.get("version") == 1:
            return c
    except Exception:
        pass
    return {"version": 1, "files": {}}


def save_cache(c):
    tmp = CACHE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(c, f, separators=(",", ":"))
        os.replace(tmp, CACHE_PATH)
    except Exception:
        pass


def list_logs(now):
    out = []
    for dp, _dn, fn in os.walk(LOG_ROOT):
        for n in fn:
            if n.endswith(".jsonl"):
                p = os.path.join(dp, n)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                if now - st.st_mtime <= KEEP_SEC:
                    out.append((p, st.st_size, st.st_mtime))
    return out


def read_new(path, ent, size):
    """ent['off'] 뒤의 완성된 줄만 읽어 ent['msgs']에 합친다."""
    msgs = ent["msgs"]
    with open(path, "rb") as f:
        f.seek(ent["off"])
        data = f.read(max(0, size - ent["off"]))
    end = data.rfind(b"\n")
    if end < 0:
        return  # 아직 완성된 줄이 없음
    chunk = data[: end + 1]
    ent["off"] += len(chunk)
    for ln, line in enumerate(chunk.split(b"\n")):
        if b'"assistant"' not in line or b'"usage"' not in line:
            continue
        try:
            d = json.loads(line.decode("utf-8", errors="ignore"))
        except Exception:
            continue
        if d.get("type") != "assistant":
            continue
        m = d.get("message") or {}
        u = m.get("usage")
        if not isinstance(u, dict):
            continue
        ts = parse_ts(d.get("timestamp") or "")
        if ts is None:
            continue
        mid = m.get("id") or d.get("requestId") or "%s:%d:%d" % (os.path.basename(path), ent["off"], ln)
        v = [int(u.get("input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0),
             int(u.get("output_tokens") or 0)]
        old = msgs.get(mid)
        if old:
            v = [max(a, b) for a, b in zip(v, old[2:5])]
            ts = min(ts, old[0])
            model = old[1] if old[1] != "?" else (m.get("model") or "?")
        else:
            model = m.get("model") or "?"
        msgs[mid] = [ts, model] + v


def scan(now=None):
    """증분 스캔 후 {id: [ts, model, in, cc, out]} 반환(파일 간 중복 제거)."""
    now = now or time.time()
    cache = load_cache()
    files = cache["files"]
    seen = set()
    changed = False
    for path, size, mt in list_logs(now):
        seen.add(path)
        ent = files.get(path)
        if ent is None or size < ent["off"] or size < ent.get("size", 0):
            ent = {"off": 0, "size": 0, "msgs": {}}
            files[path] = ent
        if size == ent["size"] and ent["off"] > 0:
            continue
        try:
            read_new(path, ent, size)
        except OSError:
            continue
        ent["size"] = size
        changed = True
    for p in list(files):
        if p not in seen:
            del files[p]
            changed = True
    cutoff = now - KEEP_SEC
    merged = {}
    for ent in files.values():
        ms = ent["msgs"]
        old = [k for k, r in ms.items() if r[0] < cutoff]
        for k in old:
            del ms[k]
            changed = True
        for k, r in ms.items():
            o = merged.get(k)
            if o is None:
                merged[k] = r
            else:
                merged[k] = [min(o[0], r[0]), o[1] if o[1] != "?" else r[1]] + \
                            [max(a, b) for a, b in zip(o[2:5], r[2:5])]
    if changed:
        save_cache(cache)
    return merged


# ---------------------------------------------------------------- 계산
def compute(merged, now=None):
    now = now or time.time()
    ev = sorted((r[0], r[2] + r[3] + r[4], r[1]) for r in merged.values()
                if now - D7 <= r[0] <= now)
    t5 = t7 = 0
    by5, by7 = {}, {}
    for ts, tok, model in ev:
        t7 += tok
        by7[model] = by7.get(model, 0) + tok
        if ts >= now - H5:
            t5 += tok
            by5[model] = by5.get(model, 0) + tok
    # 정확한 슬라이딩 윈도(끝점이 각 이벤트인 5시간 구간)의 최대값
    mx, s, i = 0, 0, 0
    for j, (ts, tok, _m) in enumerate(ev):
        s += tok
        while ev[i][0] <= ts - H5:
            s -= ev[i][1]
            i += 1
        mx = max(mx, s)
    mx = max(mx, t5)
    pct = (t5 / mx * 100) if mx else 0.0
    recent = sum(tok for ts, tok, _m in ev if ts >= now - RECENT)       # 방금 쓴 토큰 = 햄스터가 먹는 중
    return {"now": now, "tokens_5h": t5, "tokens_7d": t7, "max_5h_in_7d": mx, "tokens_recent": recent,
            "pct_of_max": round(pct, 1), "messages_7d": len(ev),
            "by_model_5h": dict(sorted(((k, v) for k, v in by5.items() if v), key=lambda x: -x[1])),
            "by_model_7d": dict(sorted(((k, v) for k, v in by7.items() if v), key=lambda x: -x[1]))}


def fmt(n):
    n = int(n)
    if n < 10000:
        return "{:,}".format(n)
    if n < 10000000:                       # 1천만 미만: 59.4만
        return "%.1f만" % (n / 1e4)
    if n < 100000000:                      # 1억 미만: 9,209만
        return "{:,}만".format(round(n / 1e4))
    return "%.2f억" % (n / 1e8)


def short_model(m):
    return m[7:] if m.startswith("claude-") else m


# ---------------------------------------------------------------- GUI
def work_area():
    r = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
    return r.left, r.top, r.right, r.bottom


def run_gui(args):
    import tkinter as tk
    import tkinter.font as tkfont
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    # 단일 실행
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    name = "Local\\ClaudeUsageWidget" + ("_shot" if (args.screenshot or args.selftest) else "")
    mutex = k32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == 183:
        return
    try:
        S = ctypes.windll.user32.GetDpiForSystem() / 96.0
    except Exception:
        S = 1.0
    if args.screenshot and args.scale:          # 게시물용으로 크게 찍을 때만
        S = args.scale
    W, H = int(310 * S), int(112 * S)

    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg=INK)
    fams = set(tkfont.families())
    fam = "Pretendard" if "Pretendard" in fams else "Malgun Gothic"

    def F(px, bold=False):
        return tkfont.Font(family=fam, size=-int(px * S), weight="bold" if bold else "normal")
    f_title, f_small, f_lab = F(13, True), F(10), F(11)
    f_num, f_pct = F(16, True), F(11, True)

    # 햄스터와 밥그릇 그림: pet/make_pet.py가 찍은 픽셀을 창 배율에 맞춰 키운다.
    sys.path.insert(0, os.path.join(APP_DIR, "pet"))
    import make_pet as mp
    from PIL import Image, ImageTk
    PX = max(1, int(3 * S))            # 픽셀 한 칸의 크기. 정수여야 또렷하다.

    def sprite(grid, crop=False):
        im = mp.to_image(grid, PX)
        if crop:
            im = im.crop(im.getbbox())
        bg = Image.new("RGB", im.size, INK)
        bg.paste(im, (0, 0), im)
        return ImageTk.PhotoImage(bg)
    pets = {"hungry": sprite(mp.hungry()), "base": sprite(mp.base()), "blink": sprite(mp.base(blink=True)),
            "eat0": sprite(mp.eating(0)), "eat1": sprite(mp.eating(1)), "full": sprite(mp.full())}
    bowls = [sprite(mp.bowl(i), crop=True) for i in range(4)]

    settings = {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except Exception:
        pass

    def save_settings():
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False)
        except Exception:
            pass

    # 햄스터 이름: 사용자마다 settings.json에 따로 저장한다 (오른쪽 클릭 > 이름 바꾸기)
    pet_name = {"v": (args.name or settings.get("name") or NAME)[:NAME_MAX]}

    def default_pos():
        l, t, r, b = work_area()
        return r - W - int(12 * S), b - H - int(12 * S)

    def valid(x, y):
        vx = ctypes.windll.user32.GetSystemMetrics(76)
        vy = ctypes.windll.user32.GetSystemMetrics(77)
        vw = ctypes.windll.user32.GetSystemMetrics(78)
        vh = ctypes.windll.user32.GetSystemMetrics(79)
        return vx - W + 40 <= x <= vx + vw - 40 and vy <= y <= vy + vh - 40

    if args.pos:
        px_, py_ = [int(v) for v in args.pos.split(",")]
    elif "x" in settings and valid(settings["x"], settings["y"]):
        px_, py_ = settings["x"], settings["y"]
    else:
        px_, py_ = default_pos()
    root.geometry("%dx%d+%d+%d" % (W, H, px_, py_))

    cv = tk.Canvas(root, width=W, height=H, bg=INK, highlightthickness=0, bd=0)
    cv.pack()

    state = {"data": None, "err": None, "stamp": "", "shown": False, "tip": None, "after": None}

    anim = {"n": 0, "key": None, "pet": None}

    def mood():
        """토큰 사용량으로 햄스터 상태를 정한다."""
        d = state["data"]
        if d is None:
            return "base"
        if d.get("tokens_recent", 0) > 0:
            return "eat"
        pct = d["pct_of_max"]
        return "hungry" if pct < HUNGRY_BELOW else "full" if pct >= FULL_FROM else "base"

    def pet_key():
        m = mood()
        if m == "eat":
            return "eat%d" % (anim["n"] % 2)                 # 두 컷을 번갈아 = 오물오물
        if m == "base":
            return "blink" if anim["n"] % 10 == 9 else "base"   # 가끔 눈 깜빡
        return m

    def draw():
        cv.delete("all")
        cv.create_rectangle(0, 0, W - 1, H - 1, outline=HAIR)
        s = S
        d = state["data"]
        pct = d["pct_of_max"] if d else 0

        # 왼쪽: 햄스터와 밥그릇 (사용량이 늘수록 씨가 쌓인다)
        anim["key"] = pet_key()
        anim["pet"] = cv.create_image(56 * s, 104 * s, image=pets[anim["key"]], anchor="s")
        level = 0 if pct < 15 else 1 if pct < 45 else 2 if pct < 80 else 3
        cv.create_image(127 * s, 104 * s - PX, image=bowls[level], anchor="s")

        # 오른쪽: 이름·상태, 사용량, 씨앗 게이지
        x0, x1 = 164 * s, 298 * s
        name = pet_name["v"]
        cv.create_text(x0, 15 * s, text=name, anchor="w", fill=CREAM, font=f_title)
        status = "읽는 중…" if d is None else MOOD_TEXT[mood()]
        right = state["stamp"]
        if state["err"]:
            right = "! 오류 " + state["stamp"]
        cv.create_text(x1, 15 * s, text=right, anchor="e", fill=MUTED, font=f_small)
        sx = x0 + f_title.measure(name) + 6 * s
        if sx + f_small.measure(status) <= x1 - f_small.measure(right) - 6 * s:   # 이름이 길면 상태 글은 생략
            cv.create_text(sx, 15 * s, text=status, anchor="w", fill=MUTED, font=f_small)
        cv.create_line(x0, 27 * s, x1, 27 * s, fill=HAIR)
        cv.create_text(x0, 43 * s, text="최근 5시간", anchor="w", fill=MUTED, font=f_lab)
        cv.create_text(x0, 64 * s, text="최근 7일", anchor="w", fill=MUTED, font=f_lab)
        if d is None:
            return
        cv.create_text(x1, 43 * s, text=fmt(d["tokens_5h"]), anchor="e", fill=CREAM, font=f_num)
        cv.create_text(x1, 64 * s, text=fmt(d["tokens_7d"]), anchor="e", fill=CREAM, font=f_num)
        col = RED if pct >= 95 else ORANGE if pct >= 80 else CREAM
        filled = min(10, -(-int(pct * 10) // 100))           # 10%마다 씨앗 하나 (올림)
        u = max(1, int(S))
        for i in range(10):
            c = col if i < filled else HAIR
            gx, gy = x0 + i * 8 * s, 87 * s
            for r, row in enumerate(SEED):
                for k, ch in enumerate(row):
                    if ch == "#":
                        cv.create_rectangle(gx + k * u, gy + r * u, gx + (k + 1) * u, gy + (r + 1) * u,
                                            fill=c, outline="")
        cv.create_text(x1, 90 * s, text="%d%%" % round(pct), anchor="e",
                       fill=col if pct >= 80 else MUTED, font=f_pct)

    def tick():
        """0.4초마다 햄스터 그림만 바꾼다 (먹는 중 오물오물, 가끔 눈 깜빡)."""
        anim["n"] += 1
        key = pet_key()
        if anim["pet"] and key != anim["key"]:
            cv.itemconfig(anim["pet"], image=pets[key])
            anim["key"] = key
        root.after(400, tick)

    def tip_text():
        d = state["data"]
        if d is None:
            return "읽는 중…"
        L = ["[최근 5시간] " + fmt(d["tokens_5h"]) + " 토큰"]
        for m, v in d["by_model_5h"].items():
            L.append("   %s  %s" % (short_model(m), fmt(v)))
        L.append("[최근 7일] " + fmt(d["tokens_7d"]) + " 토큰")
        for m, v in d["by_model_7d"].items():
            L.append("   %s  %s" % (short_model(m), fmt(v)))
        L.append("7일 중 5시간 최대 " + fmt(d["max_5h_in_7d"]))
        L.append("")
        L.append("%s 밥 규칙: 방금(3분 안) 토큰을 쓰면 먹는 중," % pet_name["v"])
        L.append("평소 최대의 %d%% 미만이면 배고픔, %d%% 이상이면 배부름." % (HUNGRY_BELOW, FULL_FROM))
        L.append("")
        L.append("토큰 = 입력 + 캐시 쓰기 + 출력 (캐시 읽기 제외)")
        L.append("Anthropic 공식 플랜 한도 %가 아니에요.")
        L.append("이 PC의 Claude Code / 데스크톱 앱 Code 탭")
        L.append("로그만 집계해요 (웹 claude.ai, 다른 PC 제외).")
        L.append("마지막 갱신 " + datetime.fromtimestamp(d["now"]).strftime("%Y-%m-%d %H:%M:%S"))
        return "\n".join(L)

    def hide_tip(_e=None):
        if state["after"]:
            root.after_cancel(state["after"])
            state["after"] = None
        if state["tip"]:
            state["tip"].destroy()
            state["tip"] = None

    def show_tip():
        state["after"] = None
        if state["tip"]:
            return
        t = tk.Toplevel(root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.configure(bg=HAIR)
        tk.Label(t, text=tip_text(), justify="left", anchor="w", bg=INK, fg=CREAM, font=F(11),
                 padx=int(10 * S), pady=int(8 * S)).pack(padx=1, pady=1)
        t.update_idletasks()
        tw, th = t.winfo_reqwidth(), t.winfo_reqheight()
        x, y = root.winfo_x(), root.winfo_y() - th - 4
        l, tp, r, b = work_area()
        if y < tp:
            y = root.winfo_y() + H + 4
        x = max(l, min(x + W - tw, r - tw))
        t.geometry("+%d+%d" % (x, y))
        state["tip"] = t

    def enter(_e):
        hide_tip()
        state["after"] = root.after(400, show_tip)

    cv.bind("<Enter>", enter)
    cv.bind("<Leave>", hide_tip)

    # 드래그
    drag = {}

    def press(e):
        hide_tip()
        drag["dx"], drag["dy"] = e.x_root - root.winfo_x(), e.y_root - root.winfo_y()

    def motion(e):
        hide_tip()
        root.geometry("+%d+%d" % (e.x_root - drag["dx"], e.y_root - drag["dy"]))

    def release(_e):
        settings["x"], settings["y"] = root.winfo_x(), root.winfo_y()
        save_settings()

    cv.bind("<ButtonPress-1>", press)
    cv.bind("<B1-Motion>", motion)
    cv.bind("<ButtonRelease-1>", release)

    refresh_evt = threading.Event()
    q = queue.Queue()

    def reset_pos():
        x, y = default_pos()
        root.geometry("+%d+%d" % (x, y))
        settings.pop("x", None)
        settings.pop("y", None)
        save_settings()

    def rename():
        from tkinter import simpledialog
        hide_tip()
        new = simpledialog.askstring("이름 바꾸기", "햄스터 이름을 적어 주세요 (%d자까지)" % NAME_MAX,
                                     initialvalue=pet_name["v"], parent=root)
        if new is None:
            return
        new = " ".join(new.split())[:NAME_MAX]
        if not new:
            return
        pet_name["v"] = settings["name"] = new
        save_settings()
        draw()

    def quit_():
        hide_tip()
        root.destroy()

    menu = tk.Menu(root, tearoff=0, bg=INK, fg=CREAM, activebackground=ORANGE, activeforeground=CREAM,
                   font=F(11), bd=0)
    menu.add_command(label="지금 새로고침", command=refresh_evt.set)
    menu.add_command(label="이름 바꾸기", command=rename)
    menu.add_command(label="위치 초기화", command=reset_pos)
    menu.add_separator()
    menu.add_command(label="종료", command=quit_)
    cv.bind("<Button-3>", lambda e: (hide_tip(), menu.tk_popup(e.x_root, e.y_root)))

    stop = {"v": False}

    def worker():
        while not stop["v"]:
            try:
                res = ("ok", compute(scan()))
            except Exception as ex:
                res = ("err", str(ex))
            q.put(res)
            refresh_evt.wait(60)
            refresh_evt.clear()

    def poll():
        try:
            while True:
                kind, val = q.get_nowait()
                if kind == "ok":
                    if args.demo:                           # 사진용: 상태만 흉내 낸 예시 값
                        p = args.demo.split(",")
                        val["pct_of_max"] = float(p[0])
                        val["tokens_5h"] = int(val["max_5h_in_7d"] * float(p[0]) / 100)
                        val["tokens_recent"] = 1 if "eat" in p else 0
                    state["data"], state["err"] = val, None
                else:
                    state["err"] = val
                state["stamp"] = datetime.now().strftime("%H:%M")
                state["shown"] = True
                draw()
                root.attributes("-topmost", True)
        except queue.Empty:
            pass
        root.after(300, poll)

    draw()
    root.deiconify()
    root.update()
    threading.Thread(target=worker, daemon=True).start()
    poll()
    tick()

    if args.screenshot:
        def shot_wait():
            if state["shown"]:
                root.after(600, shot)
            elif time.time() - t0 > 180:
                root.destroy()
            else:
                root.after(300, shot_wait)

        def shot():
            # 화면을 캡처하면 뒤나 위에 있는 다른 창(카톡 등)이 찍힐 수 있어서,
            # PrintWindow로 위젯 창 자기 자신의 픽셀만 받아 온다.
            import ctypes
            from ctypes import wintypes
            from PIL import Image
            root.update()
            u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32
            hwnd = u32.GetParent(root.winfo_id()) or root.winfo_id()
            rc = wintypes.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rc))
            w, h = rc.right - rc.left, rc.bottom - rc.top
            hdc = u32.GetWindowDC(hwnd)
            mdc = g32.CreateCompatibleDC(hdc)
            bmp = g32.CreateCompatibleBitmap(hdc, w, h)
            g32.SelectObject(mdc, bmp)
            ok = u32.PrintWindow(hwnd, mdc, 2)          # PW_RENDERFULLCONTENT

            class BIH(ctypes.Structure):
                _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                            ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16),
                            ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32),
                            ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32),
                            ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]
            bih = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
            buf = ctypes.create_string_buffer(w * h * 4)
            g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
            g32.DeleteObject(bmp)
            g32.DeleteDC(mdc)
            u32.ReleaseDC(hwnd, hdc)
            if ok:
                Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1).save(args.screenshot)
            root.destroy()
        t0 = time.time()
        root.after(300, shot_wait)

    if args.selftest:
        # 사람이 누르지 않고도 툴팁·끌기·위치 초기화·메뉴가 도는지 확인한다. 설정은 임시 파일에만 쓴다.
        def selftest():
            import traceback
            global SETTINGS_PATH
            SETTINGS_PATH = args.selftest + ".settings.json"
            res = []
            try:
                show_tip()
                root.update()
                res.append("tip shown: %s, lines: %d" % (bool(state["tip"]), tip_text().count("\n") + 1))
                hide_tip()
                res.append("tip hidden: %s" % (state["tip"] is None))
                x, y = root.winfo_x(), root.winfo_y()
                cv.event_generate("<ButtonPress-1>", x=20, y=20, rootx=x + 20, rooty=y + 20)
                cv.event_generate("<B1-Motion>", x=20, y=20, rootx=x + 60, rooty=y + 50)
                root.update()
                res.append("drag moved by: %s (expected (40, 30))" % ((root.winfo_x() - x, root.winfo_y() - y),))
                cv.event_generate("<ButtonRelease-1>", x=20, y=20)
                root.update()
                res.append("position saved: %s" % (settings.get("x") == root.winfo_x()))
                reset_pos()
                root.update()
                res.append("reset: %s, back at default: %s" % ("x" not in settings,
                                                            (root.winfo_x(), root.winfo_y()) == default_pos()))
                res.append("menu items: %s" % [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
                                               if menu.type(i) == "command"])
                anim["n"] = 0
                keys = []
                for _ in range(12):
                    anim["n"] += 1
                    keys.append(pet_key())
                res.append("frames: %s" % keys)
            except Exception:
                res.append(traceback.format_exc())
            with open(args.selftest, "w", encoding="utf-8") as f:
                f.write("\n".join(res))
            root.destroy()

        def selftest_wait():
            if state["shown"]:
                root.after(500, selftest)
            else:
                root.after(300, selftest_wait)
        root.after(300, selftest_wait)

    root.mainloop()
    stop["v"] = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--now", type=float)
    ap.add_argument("--screenshot")
    ap.add_argument("--scale", type=float, default=0, help="--screenshot 때 위젯 배율 (예: 3)")
    ap.add_argument("--pos")
    ap.add_argument("--name", help="이번 실행에서만 쓸 햄스터 이름 (저장하지 않음)")
    ap.add_argument("--selftest", help="툴팁·끌기·메뉴 자동 시험 결과를 적을 파일 경로")
    ap.add_argument("--demo", help="사진용 예시 상태. 평소 최대 대비 %%[,eat] (예: 92 또는 46,eat)")
    args = ap.parse_args()
    if args.once:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        t = time.time()
        r = compute(scan(args.now), args.now)
        r["elapsed_sec"] = round(time.time() - t, 2)
        r["text"] = {"5h": fmt(r["tokens_5h"]), "7d": fmt(r["tokens_7d"]), "max5h": fmt(r["max_5h_in_7d"])}
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    run_gui(args)


if __name__ == "__main__":
    main()
