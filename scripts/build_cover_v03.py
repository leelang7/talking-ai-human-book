# -*- coding: utf-8 -*-
"""Vol.02 표지 — All That AI 시리즈 디자인 시스템(Vol.01 '테슬라북') 계승.

Vol.01(Tesla_book/ebook/cover/cover_upaper.svg)의 레이아웃을 그대로 따르되
내용은 Vol.02, 강조색은 건강 테마 틸(Vol.01=레드와 구분). 폰트 웨이트
정확도를 위해 PIL + Noto Sans KR 가변폰트로 렌더(cairosvg 의 VF weight 한계 회피).

출력: ebook/cover/cover_final.png (1600×2400, 신국판 2:3 근사)
"""
from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ebook" / "cover" / "cover_final.png"
NOTO = "C:/Windows/Fonts/NotoSansKR-VF.ttf"

S = 3                       # 슈퍼샘플(고해상 출력용)
W, H = 1200 * S, 1800 * S   # Vol.01 SVG 좌표계 그대로(2:3)
OUT_W, OUT_H = 2400, 3600   # 출력 해상도(≈330dpi @ B5 패널) — 부크크 300dpi 대응

# 팔레트 — Vol.01=레드, Vol.02=틸, Vol.03=앰버(목소리·온기)
BLK_TOP, BLK_BOT = (11, 12, 16), (5, 5, 7)
ACC_TOP, ACC_BOT = (245, 158, 11), (180, 83, 9)     # 컬럼 그라디언트
ACC = (251, 191, 36)                                # 강조 텍스트(밝은 틸)
OFF = (244, 244, 246)

_cache = {}
def f(px, weight=400):
    k = (px, weight)
    if k not in _cache:
        ft = ImageFont.truetype(NOTO, px * S)
        try: ft.set_variation_by_axes([weight])
        except Exception: pass
        _cache[k] = ft
    return _cache[k]


def vgrad(w, h, top, bot):
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g.resize((w, h))


def tracked(d, x, y, s, ft, fill, track, anchor="lm"):
    track *= S
    ws = [d.textlength(c, font=ft) for c in s]
    total = sum(ws) + track * (len(s) - 1)
    xx = x - (total if anchor.startswith("r") else total / 2 if anchor.startswith("m") else 0)
    for c, wd in zip(s, ws):
        d.text((xx, y), c, font=ft, fill=fill, anchor="lm")
        xx += wd + track


def main():
    img = Image.new("RGB", (W, H))
    img.paste(vgrad(780 * S, H, BLK_TOP, BLK_BOT), (0, 0))          # 좌 블랙
    img.paste(vgrad(420 * S, H, ACC_TOP, ACC_BOT), (780 * S, 0))    # 우 틸 컬럼
    d = ImageDraw.Draw(img)

    # 우측 컬럼 상단 라벨
    tracked(d, 800 * S, 180 * S, "PIXEL→FACE→VOICE", f(16, 600), (255, 255, 255), 5)
    # 우측 컬럼 세로 시리즈 라벨
    vt = Image.new("RGBA", (H, 420 * S), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vt)
    tracked(vd, H // 2, 210 * S, "ALL THAT AI · VOL.03 · 2026", f(20, 600),
            (255, 255, 255), 11, anchor="m")
    img.paste(vt.rotate(90, expand=True), (780 * S, 0), vt.rotate(90, expand=True))
    # 우측 컬럼 하단 번호 02
    d.text((800 * S, 1700 * S), "03", font=f(170, 900), fill=(255, 255, 255), anchor="ls")
    d.rectangle((800 * S, 1726 * S, 860 * S, 1729 * S), fill=(255, 255, 255))

    # 좌측 상단 브랜드 라인
    d.rectangle((90 * S, 150 * S, 150 * S, 153 * S), fill=ACC)
    tracked(d, 166 * S, 159 * S, "FACE · VOICE · BRAIN · MEMORY", f(17, 600),
            (244, 244, 246), 5)

    # 좌측 메인 타이포
    d.text((90 * S, 545 * S), "사진 한 장에서", font=f(50, 400), fill=OFF, anchor="ls")
    d.text((90 * S, 620 * S), "실시간 대화 아바타까지", font=f(50, 400), fill=OFF, anchor="ls")
    d.text((90 * S, 790 * S), "AI 휴먼", font=f(118, 900), fill=OFF, anchor="ls")
    d.text((90 * S, 895 * S), "해부학", font=f(96, 800), fill=ACC, anchor="ls")

    # 구분선
    d.rectangle((90 * S, 1000 * S, 270 * S, 1003 * S), fill=ACC)
    # 부제
    d.text((90 * S, 1065 * S), "얼굴·목소리·두뇌·기억 —", f(26, 500),
           fill=(244, 244, 246), anchor="ls") if False else \
        d.text((90 * S, 1065 * S), "얼굴·목소리·두뇌·기억 —",
               font=f(26, 500), fill=(220, 224, 228), anchor="ls")
    d.text((90 * S, 1105 * S), "네 층을 조립하고 실측하는 법.",
           font=f(26, 500), fill=(220, 224, 228), anchor="ls")

    # 저자·출판사·푸터
    d.text((90 * S, 1620 * S), "이석창 지음", font=f(36, 700), fill=OFF, anchor="ls")
    d.text((90 * S, 1670 * S), "펴낸곳 · 부크크", font=f(22, 500),
           fill=(210, 214, 218), anchor="ls")
    tracked(d, 90 * S, 1718 * S, "github.com/leelang7 · youtube.com/@aidoer",
            f(15, 500), (170, 174, 180), 2)

    out = img.resize((OUT_W, OUT_H), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT, quality=95)
    print(f"[Vol.03 표지] {OUT.name}  {OUT_W}×{OUT_H} (시리즈 시스템 계승·앰버 강조·고해상)")


if __name__ == "__main__":
    main()
