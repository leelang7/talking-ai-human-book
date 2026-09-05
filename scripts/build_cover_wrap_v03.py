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
# ── 뒤표지 문구 — Vol.01(테슬라북) 뒤표지 구조 그대로: 헤드라인 → 포지셔닝 → ▶ 팩트 → 저자 → 인용 → 태그 ──
HEAD = ["사진 한 장으로 시작해", "말하는 사람까지 가는 여정."]
POSITION = [
    "AI 휴먼을 \"거대 모델 하나\" 로 파는 사이,",
    "이 책은 얼굴 · 목소리 · 두뇌 · 기억 네 층을",
    "소비자 GPU 한 장으로 직접 조립합니다.",
    "립싱크 · 리타게팅 · 실시간 아바타 · 페르소나 · 기억 · RAG · 통역 · 배포까지",
    "한 줄기 이야기로 — 4분짜리 영상에서 2초짜리 대화까지, 같은 얼굴, 다른 시간.",
]
FACTS = [
    "▶ 4부 33장 + 부록 10개 · 실패 카탈로그 50종",
    "▶ 모든 수치는 GPU 한 장에서 직접 잰 값 — 4분과 2초",
    "▶ 말하는 영상 · 브라우저 실시간 아바타 · 실시간 통역 실증 포함",
]
QUOTE = ["\"AI 휴먼은 하나의 거대 모델이 아니라", "네 층의 조립입니다.\""]
QUOTE_SRC = "— 서문에서"
TAGS = "IT · 컴퓨터 / 인공지능 / 생성형 AI / 컴퓨터 비전 / 음성 합성"
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

    # 뒤표지(좌) — Vol.01 구조. 도발적 헤드라인, 시장을 치는 문단, ▶ 팩트, 저자, 인용, 태그, 바코드 박스.
    bx, by = bl + px(12), bl + px(18)
    maxw = tw - px(24)
    d.rectangle((bx, by, bx + px(9), by + px(0.6)), fill=AMBER)
    d.text((bx + px(12), by - px(1.5)), "ALL THAT AI · VOL.03", font=ImageFont.truetype(MONO, px(2.8)), fill=GREY)
    yy = by + px(16)
    fh = font(SANS, 800, px(7.0))
    for line in HEAD:
        d.text((bx, yy), line, font=fh, fill=OFF); yy += px(9.8)
    yy += px(8)
    fp = font(SANS, 400, px(3.9))
    for line in POSITION:
        assert d.textlength(line, font=fp) <= maxw, f"문단 줄이 폭을 넘음: {line}"
        d.text((bx, yy), line, font=fp, fill=OFF); yy += px(6.0)
    yy += px(5)
    d.rectangle((bx, yy, bx + px(28), yy + px(0.6)), fill=AMBER); yy += px(6)
    fb = font(SANS, 700, px(4.2))
    for line in FACTS:
        assert d.textlength(line, font=fb) <= maxw, f"팩트 줄이 폭을 넘음: {line}"
        d.text((bx, yy), line, font=fb, fill=OFF); yy += px(6.6)
    yy += px(5)
    d.rectangle((bx, yy, bx + maxw, yy + px(0.25)), fill=(70, 74, 82)); yy += px(6)
    yy += px(4)
    fq = font(SERIF, 500, px(4.0))
    for line in QUOTE:
        d.text((bx, yy), line, font=fq, fill=AMBER_TXT); yy += px(6.2)
    d.text((bx, yy), QUOTE_SRC, font=font(SANS, 400, px(2.8)), fill=GREY); yy += px(6)
    # 하단: 분류 태그 · 저장소 (좌) — 바코드 박스 (우). 흐름 끝(yy)과 겹치지 않게 검사한다.
    tags_y = H - bl - px(22); repo_y = H - bl - px(14)
    assert yy <= tags_y - px(4), f"뒤표지 본문이 하단 영역과 겹침: 본문 끝 {yy/MM:.1f}mm > 태그 {tags_y/MM:.1f}mm"
    d.text((bx, tags_y), TAGS, font=font(SANS, 400, px(2.9)), fill=GREY)
    d.text((bx, repo_y), REPO, font=ImageFont.truetype(MONO, px(2.7)), fill=DIM)
    bw_, bh_ = px(42), px(24)
    bx1, by1 = bl + tw - px(12) - bw_, H - bl - px(12) - bh_
    d.rectangle((bx1, by1, bx1 + bw_, by1 + bh_), fill=(245, 245, 247))
    d.text((bx1 + bw_ // 2, by1 + bh_ // 2 - px(2)), "ISBN BARCODE", font=font(SANS, 700, px(3.0)), fill=(40, 40, 46), anchor="mm")
    d.text((bx1 + bw_ // 2, by1 + bh_ // 2 + px(3.5)), "(인쇄 업체 자동 삽입 영역)", font=font(SANS, 400, px(2.2)), fill=(110, 110, 118), anchor="mm")
    # 하단은 비워 둔다 — ISBN 바코드·출판사 마크는 업체가 최종 검수 때 배치한다.

    canvas.save(OUT, dpi=(DPI, DPI))
    canvas.save(OUT.with_suffix(".pdf"), "PDF", resolution=DPI)
    canvas.save(OUT.with_suffix(".jpg"), "JPEG", quality=95, dpi=(DPI, DPI))
    print(f"[전개도] {OUT.with_suffix('.pdf').name} / .jpg / .png  {W}×{H}px @ {DPI}dpi")
    print(f"  책등 {a.spine}mm · 전체 {W/MM:.1f}×{H/MM:.1f}mm (재단 {BLEED}mm 포함) · 앞표지 = cover_final_2k.png")


if __name__ == "__main__":
    main()
