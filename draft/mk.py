# -*- coding: utf-8 -*-
"""블로그 대표 이미지. SVG로 그린 뒤 PNG로 굽는다.

네이버 블로그 에디터는 **SVG를 안 받는다**(JPG·PNG·GIF). 그래서 벡터로
그리고 PNG로 내보낸다 — 글자가 깨지지 않고 크기도 마음대로 잡힌다.
"""
import glob, pathlib, sys
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "img"
OUT.mkdir(exist_ok=True)
EXE = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))

W, H = 1200, 630          # 블로그·카톡 미리보기가 쓰는 비율
C1, C2 = "#12326b", "#0d2450"      # 투워크
D1, D2 = "#1a73e8", "#0b57d0"      # 오토포스트 Pro
INK, SUB, LINE = "#14171c", "#5b6674", "#dfe3e9"


def page(svg):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @font-face{{font-family:NG;src:local('NanumGothic');}}
    *{{margin:0;padding:0}} body{{width:{W}px;height:{H}px;overflow:hidden}}
    text{{font-family:'NanumGothic','Nanum Gothic',sans-serif}}
    </style></head><body>{svg}</body></html>"""


def tag(x, y, s, size=26, fill=SUB, weight="700", anchor="start", track=0):
    """track: 자간. 받침 없이 ㅗ·ㅡ로 끝나는 글자가 이어지면(오토포스트) 아래
    가로획이 붙어 밑줄처럼 보인다. 자간을 조금 주면 떨어진다."""
    sp = f" letter-spacing='{track}'" if track else ""
    return (f"<text x='{x}' y='{y}' font-size='{size}' fill='{fill}' "
            f"font-weight='{weight}' text-anchor='{anchor}'{sp}>{s}</text>")


def card(x, y, w, h, fill="#fff", stroke=LINE, r=14, sw=2):
    return (f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{r}' "
            f"fill='{fill}' stroke='{stroke}' stroke-width='{sw}'/>")


def brandbar(c1, c2, name, site):
    return (f"<rect x='0' y='0' width='{W}' height='10' fill='{c1}'/>"
            + tag(70, H - 46, name, 27, c1, "800", track=2.6)
            + tag(W - 70, H - 46, site, 22, SUB, "400", "end"))


def svg_wrap(inner, bg="#f7f9fc"):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' "
            f"viewBox='0 0 {W} {H}'><rect width='{W}' height='{H}' fill='{bg}'/>"
            + inner + "</svg>")


# ── 1. 벌금 ─────────────────────────────────────────────────────────
def img1():
    s = brandbar(C1, C2, "투워크", "towork.zionlabs.org")
    s += tag(70, 120, "일용직 근로계약서", 40, SUB, "700")
    s += tag(70, 196, "안 쓰면 얼마를 물어야 하나", 58, INK, "800")
    s += card(70, 250, 500, 150, "#fff", "#e6b3af")
    s += tag(110, 310, "벌칙", 24, "#b3261e")
    s += tag(110, 368, "500만원 이하의 벌금", 44, "#b3261e", "800")
    s += card(610, 250, 520, 150)
    s += tag(650, 302, "근로기준법 제17조 위반 시", 24, SUB, "400")
    s += tag(650, 342, "같은 법 제114조", 30, INK)
    s += tag(650, 382, "작성 안 한 경우 + 교부 안 한 경우", 23, SUB, "400")
    s += tag(70, 470, "벌금보다 아픈 것 — 분쟁에서 증명할 것이 없습니다", 32, C1, "800")
    return s


# ── 2. 카카오톡 흐름 ────────────────────────────────────────────────
def img2():
    s = brandbar(C1, C2, "투워크", "towork.zionlabs.org")
    s += tag(70, 120, "현장에서 근로계약서를", 40, SUB, "700")
    s += tag(70, 192, "카카오톡으로 받는 방법", 58, INK, "800")
    steps = [("현장 등록", "회사 · 한 번만"), ("출근 신청", "근로자 · 코드 6자리"),
             ("승인", "회사 · 버튼 하나"), ("카톡 서명", "근로자 · 휴대폰")]
    x, w, gap = 70, 245, 20
    for i, (t, sub) in enumerate(steps):
        cx = x + i * (w + gap)
        fill = "#fff" if i % 2 else C1
        ink = C1 if i % 2 else "#fff"
        sub_c = SUB if i % 2 else "#c5d4ef"
        s += card(cx, 250, w, 140, fill, C1)
        s += tag(cx + w / 2, 306, t, 32, ink, "800", "middle")
        s += tag(cx + w / 2, 346, sub, 20, sub_c, "400", "middle")
        if i < 3:
            s += tag(cx + w + gap / 2, 332, "›", 34, C1, "700", "middle")
    s += tag(70, 470, "발송·본인확인·서명·보관이 자동으로 돌아갑니다", 32, C1, "800")
    s += tag(70, 512, "인증번호는 한 번만 — 30일 동안 다시 쓰입니다", 26, SUB, "400")
    return s


# ── 3. 의료광고 12가지 ──────────────────────────────────────────────
def img3():
    s = brandbar(D1, D2, "오토포스트 Pro", "aiblog.zionlabs.org")
    s += tag(70, 118, "병원 블로그", 40, SUB, "700")
    s += tag(70, 190, "의료광고법에 걸리는 표현 12가지", 56, INK, "800")
    words = ["완치", "100%", "부작용 없음", "최고", "국내 1위",
             "후기", "체험담", "특효", "반영구적", "성공률 98%",
             "전문의", "평생"]
    x, y = 70, 240
    for i, wd in enumerate(words):
        col, row = i % 4, i // 4
        cx, cy = x + col * 268, y + row * 76
        s += card(cx, cy, 248, 58, "#fdeaea", "#f2c4c4", 10, 2)
        s += tag(cx + 124, cy + 38, wd, 27, "#a31515", "700", "middle")
        s += (f"<line x1='{cx+30}' y1='{cy+30}' x2='{cx+218}' y2='{cy+30}' "
              f"stroke='#a31515' stroke-width='2' opacity='.45'/>")
    s += tag(70, 520, "의료법 제56조 · 시행령 제23조 — 근거 조항과 대안까지", 29, D1, "800")
    return s


# ── 4. 세무사 광고규정 ──────────────────────────────────────────────
def img4():
    s = brandbar(D1, D2, "오토포스트 Pro", "aiblog.zionlabs.org")
    s += tag(70, 118, "세무사무소 블로그 글", 40, SUB, "700")
    s += tag(70, 190, "세무사법 시행령 제33조에 걸리지 않게", 52, INK, "800")
    rows = [("평균 환급액 300만원", "산정 기준·대상·조건을 함께"),
            ("환급 보장 · 절세 확실", "\"~일 수 있습니다\""),
            ("상담 무료 · 업계 최저", "객관적 근거가 있어야"),
            ("1위 · 유일", "조사기관·시점·대상을 밝히면 가능")]
    for i, (bad, good) in enumerate(rows):
        cy = 240 + i * 74
        s += card(70, cy, 470, 58, "#fdeaea", "#f2c4c4", 10, 2)
        s += tag(94, cy + 38, bad, 26, "#a31515", "700")
        s += tag(566, cy + 38, "→", 28, SUB, "700", "middle")
        s += card(596, cy, 534, 58, "#f2faf5", "#b6dcc2", 10, 2)
        s += tag(620, cy + 38, good, 24, "#15612c", "700")
    s += tag(70, 548, "사무소명·세무사 성명 표시는 직접 확인하셔야 합니다", 25, SUB, "400")
    return s


MAKE = {"1_벌금": img1, "2_카카오톡": img2, "3_의료광고": img3, "4_세무사": img4}

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=EXE[-1] if EXE else None)
    pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    for name, fn in MAKE.items():
        svg = svg_wrap(fn())
        (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
        tmp = OUT / f"_{name}.html"
        tmp.write_text(page(svg), encoding="utf-8")
        pg.goto(tmp.as_uri()); pg.wait_for_timeout(250)
        pg.screenshot(path=str(OUT / f"{name}.png"))
        tmp.unlink()
        print(" ", name + ".png")
    br.close()
