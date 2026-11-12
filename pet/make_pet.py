# 사용량 위젯의 밥 주는 동물: 햄스터 '토리' 픽셀 스프라이트를 코드로 그린다. (1단계: 기본 모습)
# 32x32 칸에 도형으로 큰 덩어리를 잡고, 눈·코·볼 같은 작은 부분은 칸 단위로 찍는다.
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
N = 32
PAL = {
    "o": "#eda553",   # 털 (밝은 주황)
    "O": "#cf8236",   # 털 그늘
    "h": "#f7c27c",   # 털 밝은 곳
    "c": "#fff4df",   # 배·얼굴 크림
    "C": "#efdcbb",   # 크림 그늘
    "p": "#f59e9a",   # 귀 안쪽·발·코 분홍
    "b": "#f8b9ae",   # 볼 터치
    "k": "#2a1f18",   # 눈
    "w": "#ffffff",   # 눈 반짝임
    "l": "#553722",   # 외곽선
    "s": "#3d3a34",   # 해바라기씨 껍질
    "S": "#e9e4d6",   # 해바라기씨 줄무늬
}


def blank():
    return [[None] * N for _ in range(N)]


def ell(g, box, col, only=None):
    """box=(x0,y0,x1,y1) 타원을 칠한다. only가 있으면 그 색 위에만 칠한다."""
    m = Image.new("1", (N, N), 0)
    ImageDraw.Draw(m).ellipse(box, fill=1)
    for y in range(N):
        for x in range(N):
            if m.getpixel((x, y)) and (only is None or g[y][x] in only):
                g[y][x] = col


def px(g, pts, col):
    for x, y in pts:
        g[y][x] = col


def outline(g):
    """실루엣 바깥 한 칸을 외곽선 색으로 두른다."""
    out = [row[:] for row in g]
    for y in range(N):
        for x in range(N):
            if g[y][x] is None:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < N and 0 <= yy < N and g[yy][xx] not in (None, "l"):
                        out[y][x] = "l"
                        break
    return out


def shade(g):
    """오른쪽 아래 가장자리는 그늘, 왼쪽 위 가장자리는 밝게."""
    out = [row[:] for row in g]
    for y in range(N):
        for x in range(N):
            c = g[y][x]
            if c not in ("o", "c"):
                continue
            def at(dx, dy):
                xx, yy = x + dx, y + dy
                return g[yy][xx] if 0 <= xx < N and 0 <= yy < N else None
            if at(1, 0) in (None, "l") or at(0, 1) in (None, "l") or at(1, 1) in (None, "l"):
                out[y][x] = "O" if c == "o" else "C"
            elif c == "o" and (at(-1, 0) in (None, "l") or at(0, -1) in (None, "l")) and y < 16:
                out[y][x] = "h"
    return out


# 몸통 실루엣: 줄마다 (왼쪽 끝, 오른쪽 끝). 아래가 조금 더 넓은 달걀 모양.
BODY = {5: (12, 19), 6: (10, 21), 7: (8, 23), 8: (7, 24), 9: (6, 25), 10: (6, 25), 11: (6, 25), 12: (5, 26), 13: (5, 26),
        14: (5, 26), 15: (4, 27), 16: (4, 27), 17: (4, 27), 18: (3, 28), 19: (3, 28), 20: (3, 28), 21: (3, 28),
        22: (3, 28), 23: (3, 28), 24: (4, 27), 25: (4, 27), 26: (5, 26), 27: (6, 25), 28: (7, 24), 29: (9, 22)}
EAR = {4: (5, 7), 5: (4, 8), 6: (4, 8), 7: (4, 8), 8: (5, 7)}      # 왼쪽 귀 (오른쪽은 거울)
CREAM = {12: (14, 17), 13: (11, 20), 14: (9, 22), 15: (8, 23), 16: (8, 23), 17: (8, 23), 18: (8, 23),
         19: (8, 23), 20: (8, 23), 21: (8, 23), 22: (8, 23), 23: (8, 23), 24: (9, 22), 25: (9, 22),
         26: (10, 21), 27: (11, 20), 28: (12, 19)}


def spans(g, rows, col, mirror=False):
    for y, (x0, x1) in rows.items():
        for x in range(x0, x1 + 1):
            g[y][x] = col
            if mirror:
                g[y][N - 1 - x] = col


def mpx(g, pts, col):
    """왼쪽 좌표를 주면 오른쪽에도 거울로 찍는다."""
    for x, y in pts:
        g[y][x] = col
        g[y][N - 1 - x] = col


PUFF = {13: 1, 14: 1, 15: 1, 16: 2, 17: 2, 18: 2, 19: 2, 20: 2, 21: 2, 22: 1, 23: 1, 24: 1}      # 볼주머니가 찼을 때 줄마다 넓어지는 칸 수
THIN = {19: 1, 20: 1, 21: 1, 22: 1, 23: 1, 24: 1, 25: 1, 26: 1, 27: 1}      # 배고플 때 배가 홀쭉해지는 칸 수


def widen(rows, table, k):
    """table에 있는 줄을 양옆으로 k배만큼 넓히거나(양수) 좁힌다(음수)."""
    out = {}
    for y, (x0, x1) in rows.items():
        d = round(table.get(y, 0) * k)
        out[y] = (x0 - d, x1 + d)
    return out


def body(puff=0.0, thin=0.0):
    g = blank()
    shape = widen(BODY, PUFF, puff)
    cream = widen(CREAM, PUFF, puff)
    if thin:                                                            # 배고프면 옆구리가 쏙 들어감
        shape = {y: (max(x0, 5 + (y > 24) * (y - 24)), min(x1, 26 - (y > 24) * (y - 24))) for y, (x0, x1) in shape.items()}
        cream = {y: (max(x0, 9), min(x1, 22)) for y, (x0, x1) in cream.items()}
    spans(g, EAR, "o", mirror=True)
    spans(g, shape, "o")
    mpx(g, [(5, 6), (6, 6), (5, 7), (6, 7)], "p")                       # 귀 안쪽
    spans(g, cream, "c")
    mpx(g, [(15, 8), (15, 9), (15, 10), (15, 11)], "c")                 # 이마 줄무늬
    return shade(g)


def face(g, eyes="open", mouth="smile", blush=0):
    if eyes == "open":
        mpx(g, [(10, 14), (11, 14), (10, 15), (11, 15), (10, 16), (11, 16)], "k")
        px(g, [(10, 14), (20, 14)], "w")
    elif eyes == "sad":                                                 # 처진 눈썹 + 작아진 눈
        mpx(g, [(10, 15), (11, 15), (10, 16), (11, 16)], "k")
        px(g, [(10, 15), (20, 15)], "w")
        mpx(g, [(9, 14), (10, 13), (11, 12)], "l")
    elif eyes == "blink":                                               # 깜빡임: 감은 눈 한 줄
        mpx(g, [(10, 15), (11, 15)], "k")
    elif eyes == "happy":                                               # 웃어서 감긴 눈 ^ ^
        mpx(g, [(10, 15), (11, 14), (12, 15)], "k")
    mpx(g, [(15, 16)], "p")                                             # 코
    if mouth == "smile":
        mpx(g, [(15, 18), (14, 18), (13, 17)], "l")
    elif mouth == "frown":
        mpx(g, [(15, 18), (14, 19)], "l")
    elif mouth == "big":                                                # 활짝 웃는 입
        mpx(g, [(13, 17), (14, 18), (15, 19)], "l")
        mpx(g, [(15, 18)], "p")
    bx = 8 - blush
    mpx(g, [(bx, 18), (bx + 1, 18), (bx, 19), (bx + 1, 19)], "b")       # 볼 터치


def feet(g):
    mpx(g, [(10, 29), (11, 29), (12, 29)], "p")


def base(blink=False):
    g = body()
    face(g, eyes="blink" if blink else "open")
    mpx(g, [(12, 22), (13, 22)], "p")                                   # 앞발
    feet(g)
    return outline(g)


def hungry():
    """배고픔: 홀쭉한 배, 처진 눈, 시무룩한 입, 배에 올린 손."""
    g = body(thin=1)
    face(g, eyes="sad", mouth="frown")
    mpx(g, [(13, 23), (14, 23)], "p")
    feet(g)
    return outline(g)


def seed(g, y0):
    """해바라기씨: 위가 뾰족한 까만 껍질에 밝은 줄무늬."""
    mpx(g, [(15, y0), (15, y0 + 4)], "s")
    for y in (y0 + 1, y0 + 2, y0 + 3):
        mpx(g, [(14, y)], "s")                                          # 까만 껍질 가장자리
        mpx(g, [(15, y)], "S")                                          # 가운데 밝은 줄


def eating(frame=0):
    """먹는 중: 두 손으로 씨를 들고, 씹을 때 볼이 볼록."""
    g = body(puff=0.5 if frame else 0)
    face(g, eyes="open", mouth=None, blush=1 if frame else 0)
    y0 = 17 if frame == 0 else 16
    seed(g, y0)
    mpx(g, [(12, y0 + 2), (13, y0 + 2), (12, y0 + 3), (13, y0 + 3)], "o")   # 씨를 잡은 팔
    mpx(g, [(13, y0 + 2), (13, y0 + 3)], "p")                               # 손끝
    mpx(g, [(11, y0 + 3), (12, y0 + 4), (13, y0 + 4)], "l")
    feet(g)
    return outline(g)


def full():
    """배부름: 볼주머니가 꽉 차고, 눈을 감고 웃음."""
    g = body(puff=1)
    face(g, eyes="happy", mouth="smile", blush=2)
    mpx(g, [(11, 23), (12, 23)], "p")                                   # 배 위에 올린 손
    feet(g)
    return outline(g)


def bowl(level):
    """밥그릇. level 0~3만큼 해바라기씨가 쌓인다."""
    g = blank()
    for y, (x0, x1), col in ((20, (10, 21), "c"), (21, (10, 21), "c"), (22, (11, 20), "o"),
                             (23, (12, 19), "C"), (24, (13, 18), "C")):
        for x in range(x0, x1 + 1):
            g[y][x] = col
    for need, y, (x0, x1) in ((1, 19, (11, 20)), (2, 18, (13, 18)), (3, 17, (14, 17))):
        if level >= need:
            for x in range(x0, x1 + 1):
                g[y][x] = "s" if (x + y * 2) % 3 == 0 else "S"      # 밝은 씨 사이사이에 껍질 그림자
    return outline(g)


def to_image(g, scale=1):
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    for y in range(N):
        for x in range(N):
            if g[y][x]:
                im.putpixel((x, y), tuple(int(PAL[g[y][x]][i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    return im.resize((N * scale, N * scale), Image.NEAREST) if scale > 1 else im


def preview(sprites, path, labels=None, big=8):
    """크림·잉크 배경 위에 크게, 그리고 위젯에 들어갈 크기(3배)로 보여 준다."""
    from PIL import ImageFont
    small, pad, lab = 3, 32, 44 if labels else 0
    w = len(sprites) * (N * big + pad) + pad
    band = N * big + pad * 2
    h = lab + band * 2 + N * small + pad * 2
    sheet = Image.new("RGB", (w, h), "#f7f7f4")
    d = ImageDraw.Draw(sheet)
    d.rectangle([0, lab + band, w, lab + band * 2], fill="#26251e")
    font = ImageFont.truetype(str(Path.home() / "AppData/Local/Microsoft/Windows/Fonts/Pretendard-SemiBold.otf"), 24)
    for i, g in enumerate(sprites):
        im = to_image(g, big)
        x = pad + i * (N * big + pad)
        if labels:
            d.text((x + N * big / 2, lab / 2 + 8), labels[i], font=font, fill="#26251e", anchor="mm")
        sheet.paste(im, (x, lab + pad), im)
        sheet.paste(im, (x, lab + band + pad), im)
        sm = to_image(g, small)
        sheet.paste(sm, (x + (N * big - N * small) // 2, lab + band * 2 + pad), sm)
    sheet.save(path)


if __name__ == "__main__":
    frames = {"base": base(), "hungry": hungry(), "eat0": eating(0), "eat1": eating(1), "full": full()}
    for name, g in frames.items():
        to_image(g).save(HERE / f"tori_{name}.png")
    preview([frames["base"]], HERE / "_preview_base.png", big=12)
    preview([frames["hungry"], frames["eat0"], frames["eat1"], frames["full"]], HERE / "_preview_states.png",
            labels=["배고픔", "먹는 중 1", "먹는 중 2", "배부름"])
    print("ok")
