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
TRIM_W, TRIM_H = 182, 257       # 부크크 B5 — 종이책 규격은 46판·A5·B5·A4 넷뿐이다(신국판 없음)
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
    "AI 휴먼을 \"거대 모델 하나\"로 파는 사이,",
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
    """앞표지 그림을 폭에 맞춰 위로 붙이고, 남는 아래는 그림의 마지막 줄 색으로 늘린다.

    두 가지를 동시에 푼다.
      ① 부크크가 앞표지 **아래 가운데에 자사 로고** 를 찍는다 — 그림의 저자명·주소 줄과 겹쳤다.
      ② 예전처럼 꽉 채우면(cover) 그림의 좌우가 잘려 나갔다.
    그림 아래쪽은 평평한 배경(검정 + 오른쪽 앰버 기둥)이라 마지막 줄을 늘려도 티가 나지 않는다.
    """
    cw, ch = cover.size
    scale = w / cw                                   # 폭에 맞춘다 — 좌우를 자르지 않는다
    r = cover.resize((w, max(1, int(ch * scale))), Image.LANCZOS)
    if r.height >= h:
        return r.crop((0, 0, w, h))
    out = Image.new("RGB", (w, h))
    out.paste(r, (0, 0))
    tail = r.crop((0, r.height - 1, w, r.height)).resize((w, h - r.height), Image.NEAREST)
    out.paste(tail, (0, r.height))                   # 마지막 줄을 아래로 늘린다(재단 여백과 같은 요령)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spine", type=float, default=14.5, help="책등 mm — 인쇄 업체 표시값으로 확정")
    a = ap.parse_args()
    if not FRONT.exists():
        print(f"[에러] 앞표지 없음: {FRONT}"); sys.exit(1)
    px = lambda mm: int(round(mm * MM))
    tw, th, bl, sp = px(TRIM_W), px(TRIM_H), px(BLEED), px(a.spine)
    W, H = px(TRIM_W * 2 + a.spine + BLEED * 2), px(TRIM_H + BLEED * 2)   # 부크크 작업규격과 정확히 일치

    canvas = Image.new("RGB", (W, H), BLACK)
    # 앞표지(우) — 합성본을 풀블리드로 (재단 여백까지 채운다)
    canvas.paste(fill_front(Image.open(FRONT).convert("RGB"), tw + bl, th + bl * 2), (bl + tw + sp, 0))
    d = ImageDraw.Draw(canvas)

    # 책등 — 흑연 + 앰버 가는 선 + 세로 제목
    sx0 = bl + tw
    # 책등에는 장식선을 두지 않는다. 17mm 폭에서는 선이 글자와 부딪히고(2026-09-06 미리보기),
    # 접지가 ±1~2mm 흔들리면 선이 앞표지로 넘어간 것처럼 보인다. 글자만 정중앙에 둔다.
    if sp > px(8):
        st = Image.new("RGBA", (H, sp), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        fs = int(sp * 0.36)          # 책등 폭의 36% — 양옆에 여백을 남긴다
        sd.text((px(22), sp // 2), TITLE, font=font(SANS, 900, fs), fill=OFF + (255,), anchor="lm")
        tw1 = sd.textlength(TITLE, font=font(SANS, 900, fs))
        sd.text((px(22) + tw1 + px(3), sp // 2), TITLE2, font=font(SERIF, 900, fs), fill=AMBER_TXT + (255,), anchor="lm")
        # 부크크는 **책등 아래쪽에도 자사 로고** 를 찍는다(미리보기에서 저자명을 덮었다).
        # 아래 45mm 는 비우고 저자명을 그 위에 둔다.
        sd.text((H - px(50), sp // 2), AUTHOR, font=font(SANS, 600, int(sp * 0.26)), fill=GREY + (255,), anchor="rm")
        sd.text((H // 2, sp // 2), "ALL THAT AI · VOL.03", font=ImageFont.truetype(MONO, int(sp * 0.20)), fill=DIM + (255,), anchor="mm")
        rot = st.rotate(-90, expand=True)      # 위→아래로 읽힘: 제목이 위, 저자가 아래 (한국 관행. Vol.02 는 반대로 나갔다)
        # 글자를 책등 정중앙에 — 글꼴 위아래 여백이 비대칭이라 sp//2 로 그리면 0.3mm 쏠린다.
        # 찍힌 잉크의 상자를 재서 그만큼 밀어 준다(부크크 미리보기에서 '오른쪽 쏠림' 으로 보였다).
        ink = rot.split()[-1].getbbox()
        shift = (sp - (ink[0] + ink[2])) // 2 if ink else 0
        canvas.paste(rot, (sx0 + shift, 0), rot)

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
    # 부크크는 뒤표지 **왼쪽 아래에 ISBN 바코드** 를, 앞표지 아래에 자사 로고를 얹는다.
    # 바코드는 40×25mm + 여백이라 아래 45mm 는 통째로 비워야 한다 — 25mm 만 비웠더니 글자를 덮었다(2026-09-06).
    repo_y = H - bl - px(50)          # 분류 태그 줄은 뺐다 — 뒤표지에서 겉돌았다
    assert yy <= repo_y - px(6), f"뒤표지 본문이 하단 영역과 겹침: 본문 끝 {yy/MM:.1f}mm > 저장소 줄 {repo_y/MM:.1f}mm"
    d.text((bx, repo_y), REPO, font=ImageFont.truetype(MONO, px(2.7)), fill=DIM)
    # ISBN 바코드는 부크크가 뒤표지 왼쪽 아래에 직접 얹는다 — 우리가 자리를 그리면 두 개가 된다.
    # 아무것도 그리지 않고 **아래 45mm 를 통째로** 비운다(바코드 40×25mm + 조용한 여백).

    canvas.save(OUT, dpi=(DPI, DPI))
    canvas.save(OUT.with_suffix(".pdf"), "PDF", resolution=DPI)
    canvas.save(OUT.with_suffix(".jpg"), "JPEG", quality=95, dpi=(DPI, DPI))
    print(f"[전개도] {OUT.with_suffix('.pdf').name} / .jpg / .png  {W}×{H}px @ {DPI}dpi")
    print(f"  책등 {a.spine}mm · 전체 {W/MM:.1f}×{H/MM:.1f}mm (재단 {BLEED}mm 포함) · 앞표지 = cover_final_2k.png")


if __name__ == "__main__":
    main()
