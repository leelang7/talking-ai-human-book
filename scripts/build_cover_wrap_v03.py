# -*- coding: utf-8 -*-
"""표지 전개도 — 앞표지(합성본) + 책등 + 뒤표지. Vol.02 의 build_cover_wrap_art.py 계승.

앞표지 = ebook/cover/cover_art_final.png (Flow 두상 아트 + 코드 타이포 합성).
책등·뒤표지는 시리즈 시스템(흑연 바탕 + 앰버 강조 + 산세리프/세리프/모노)로 통일.
인쇄 규격: 사방 3mm 재단, 300dpi. 책등폭은 인쇄 업체가 주는 값(--spine)으로 확정 — 기본 14.5mm 는 305쪽 × 0.0476mm.
출판사·유통사 이름은 어디에도 쓰지 않는다. 뒤표지 하단은 비워 둔다(ISBN 바코드 자리 — 업체가 넣는다).

    python scripts/build_cover_wrap_v03.py --spine 14.5
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "ebook" / "cover" / "cover_final_2k.png"     # 확정 앞표지 = Flow 2K 원본에서 별만 제거
OUT = ROOT / "ebook" / "cover" / "cover_wrap.png"
SANS = "C:/Windows/Fonts/NotoSansKR-VF.ttf"
SERIF = "C:/Windows/Fonts/NotoSerifKR-VF.ttf"
MONO = "C:/Windows/Fonts/CascadiaMono.ttf"
DPI = 300
MM = DPI / 25.4
TRIM_W, TRIM_H = 152, 225       # 본문 판형 mm (build_book.py @page)
BLEED = 3

BLACK = (11, 12, 16)
OFF = (244, 244, 246)
GREY = (176, 180, 188)
DIM = (120, 124, 132)
AMBER = (245, 158, 11)
AMBER_TXT = (251, 191, 36)

TITLE, TITLE2 = "AI 휴먼", "해부학"
SUB = "얼굴·목소리·두뇌·기억 — 네 층을 조립하고 실측하는 법"
AUTHOR = "이석창 지음"
HOOK = "픽셀이 사람이 되는 여정"
BLURB = [
    "AI 휴먼은 하나의 모델이 아닙니다.",
    "얼굴, 목소리, 두뇌, 기억 — 네 층을 하나씩 조립하고,",
    "어디서 부서지는지 재어 가며 완성합니다.",
    "사진 한 장으로 4분 만에 말하는 영상을 만들고,",
    "브라우저에서 2초 만에 대답하는 아바타를 띄우고,",
    "그 얼굴에 인격과 기억을 넣습니다.",
]
FEATURES = [
    "Track A   사진 한 장 → 말하는 영상",
    "Track B   GPU 없이 브라우저에서 도는 실시간 아바타",
    "Track C   인격 · 기억 · 지식, 그리고 실시간 통역",
]
FOR = "AI 휴먼을 직접 만들어야 하는 개발자 · 창업자 · 강사에게."
TRUST = "모든 수치는 저자가 직접 잰 값이며, 실패한 것도 그대로 실었습니다."
REPO = "github.com/leelang7/talking-ai-human-book"


def font(path, w, px):
    f = ImageFont.truetype(path, px)
    try:
        f.set_variation_by_axes([w])
    except Exception:
        pass
    return f


def fill_front(cover, w, h):
    cw, ch = cover.size
    scale = max(w / cw, h / ch)
    r = cover.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)
    x = (r.width - w) // 2
    y = (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spine", type=float, default=14.5, help="책등 mm — 인쇄 업체 표시값으로 확정")
    a = ap.parse_args()
    if not FRONT.exists():
        print(f"[에러] 앞표지 없음: {FRONT}"); sys.exit(1)
    px = lambda mm: int(round(mm * MM))
    tw, th, bl, sp = px(TRIM_W), px(TRIM_H), px(BLEED), px(a.spine)
    W, H = tw * 2 + sp + bl * 2, th + bl * 2

    canvas = Image.new("RGB", (W, H), BLACK)
    # 앞표지(우) — 합성본을 풀블리드로 (재단 여백까지 채운다)
    canvas.paste(fill_front(Image.open(FRONT).convert("RGB"), tw + bl, th + bl * 2), (bl + tw + sp, 0))
    d = ImageDraw.Draw(canvas)

    # 책등 — 흑연 + 앰버 가는 선 + 세로 제목
    sx0 = bl + tw
    d.rectangle((sx0 + sp - px(0.8), 0, sx0 + sp, H), fill=AMBER)          # 앞표지 쪽 가장자리 앰버 선
    if sp > px(8):
        st = Image.new("RGBA", (H, sp), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        fs = int(sp * 0.42)
        sd.text((px(22), sp // 2), TITLE, font=font(SANS, 900, fs), fill=OFF + (255,), anchor="lm")
        tw1 = sd.textlength(TITLE, font=font(SANS, 900, fs))
        sd.text((px(22) + tw1 + px(3), sp // 2), TITLE2, font=font(SERIF, 900, fs), fill=AMBER_TXT + (255,), anchor="lm")
        sd.text((H - px(22), sp // 2), AUTHOR, font=font(SANS, 600, int(sp * 0.30)), fill=GREY + (255,), anchor="rm")
        sd.text((H // 2, sp // 2), "ALL THAT AI · VOL.03", font=ImageFont.truetype(MONO, int(sp * 0.22)), fill=DIM + (255,), anchor="mm")
        rot = st.rotate(-90, expand=True)      # 위→아래로 읽힘: 제목이 위, 저자가 아래 (한국 관행. Vol.02 는 반대로 나갔다)
        canvas.paste(rot, (sx0, 0), rot)

    # 뒤표지(좌) — 흑연 + 앰버 룰 + 시스템 타이포. 독자에게 파는 자리 — 내부 지표는 쓰지 않는다.
    bx, by = bl + px(16), bl + px(24)
    maxw = tw - px(32)
    d.rectangle((bx, by, bx + px(14), by + px(0.7)), fill=AMBER)
    d.text((bx + px(18), by - px(1.6)), "FACE · VOICE · BRAIN · MEMORY", font=ImageFont.truetype(MONO, px(3.2)), fill=GREY)
    d.text((bx, by + px(12)), TITLE, font=font(SANS, 900, px(14)), fill=OFF)
    d.text((bx, by + px(29)), TITLE2, font=font(SERIF, 900, px(12)), fill=AMBER_TXT)
    d.text((bx, by + px(46)), SUB, font=font(SERIF, 400, px(4.6)), fill=GREY)
    yy = by + px(64)
    d.text((bx, yy), HOOK, font=font(SANS, 700, px(7.2)), fill=OFF); yy += px(13)
    fb = font(SANS, 400, px(4.6))
    for line in BLURB:
        assert d.textlength(line, font=fb) <= maxw, f"소개 줄이 폭을 넘음: {line}"
        d.text((bx, yy), line, font=fb, fill=OFF); yy += px(7.4)
    yy += px(5)
    d.rectangle((bx, yy, bx + px(40), yy + px(0.5)), fill=AMBER); yy += px(7)
    ff = font(SANS, 500, px(4.2))
    for line in FEATURES:
        assert d.textlength(line, font=ff) <= maxw, f"목록 줄이 폭을 넘음: {line}"
        d.text((bx, yy), line, font=ff, fill=GREY); yy += px(6.8)
    yy += px(5)
    d.text((bx, yy), FOR, font=font(SANS, 400, px(4.2)), fill=GREY); yy += px(7)
    d.text((bx, yy), TRUST, font=font(SERIF, 400, px(4.0)), fill=DIM); yy += px(9)
    d.text((bx, yy), REPO, font=ImageFont.truetype(MONO, px(3.4)), fill=DIM)
    # 하단은 비워 둔다 — ISBN 바코드·출판사 마크는 업체가 최종 검수 때 배치한다.

    canvas.save(OUT, dpi=(DPI, DPI))
    canvas.save(OUT.with_suffix(".pdf"), "PDF", resolution=DPI)
    canvas.save(OUT.with_suffix(".jpg"), "JPEG", quality=95, dpi=(DPI, DPI))
    print(f"[전개도] {OUT.with_suffix('.pdf').name} / .jpg / .png  {W}×{H}px @ {DPI}dpi")
    print(f"  책등 {a.spine}mm · 전체 {W/MM:.1f}×{H/MM:.1f}mm (재단 {BLEED}mm 포함) · 앞표지 = cover_final_2k.png")


if __name__ == "__main__":
    main()
