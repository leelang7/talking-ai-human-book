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
OUT = ROOT / "ebook" / "cover" / ("cover_art_final.png" if "--art" in __import__("sys").argv else "cover_final.png")
NOTO = "C:/Windows/Fonts/NotoSansKR-VF.ttf"

S = 3                       # 슈퍼샘플(고해상 출력용)
W, H = 1200 * S, 1800 * S   # Vol.01 SVG 좌표계 그대로(2:3)
OUT_W, OUT_H = 2400, 3600   # 출력 해상도 — 인쇄 300dpi 대응 (출판사·유통사 표기는 업체가 넣는다 — 표지에 쓰지 않는다)

# 팔레트 — Vol.01=레드, Vol.02=틸, Vol.03=앰버(목소리·온기)
BLK_TOP, BLK_BOT = (11, 12, 16), (5, 5, 7)
ACC_TOP, ACC_BOT = (245, 158, 11), (180, 83, 9)     # 컬럼 그라디언트
ACC = (251, 191, 36)                                # 강조 텍스트(밝은 틸)
OFF = (244, 244, 246)

_cache = {}
SERIF = "C:/Windows/Fonts/NotoSerifKR-VF.ttf"     # 제목 '해부학' · 부제 — 해부도의 세리프
MONO = "C:/Windows/Fonts/CascadiaMono.ttf"         # 라벨·시리즈 표기·푸터 — 계측기의 모노스페이스


def _vf(path, px, weight):
    k = (path, px, weight)
    if k not in _cache:
        ft = ImageFont.truetype(path, px * S)
        try: ft.set_variation_by_axes([weight])
        except Exception: pass
        _cache[k] = ft
    return _cache[k]


def f(px, weight=400):          # 산세리프 — 윗줄 · 'AI 휴먼' · 저자
    return _vf(NOTO, px, weight)


def fs(px, weight=400):         # 세리프 — '해부학' · 부제
    return _vf(SERIF, px, max(200, weight))


def fm(px, weight=400):         # 모노 — 라벨 · 세로 표기 · 링크
    k = ("mono", px)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(MONO, px * S)
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
    tracked(d, 800 * S, 180 * S, "PIXEL→FACE→VOICE", fm(15), (255, 255, 255), 5)
    # 우측 컬럼 세로 시리즈 라벨
    vt = Image.new("RGBA", (H, 420 * S), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vt)
    tracked(vd, H // 2, 210 * S, "ALL THAT AI · VOL.03 · 2026", fm(19),
            (255, 255, 255), 11, anchor="m")
    img.paste(vt.rotate(90, expand=True), (780 * S, 0), vt.rotate(90, expand=True))
    # 우측 컬럼 하단 번호 02
    d.text((800 * S, 1700 * S), "03", font=f(170, 900), fill=(255, 255, 255), anchor="ls")
    d.rectangle((800 * S, 1726 * S, 860 * S, 1729 * S), fill=(255, 255, 255))

    # 좌측 상단 브랜드 라인
    d.rectangle((90 * S, 150 * S, 150 * S, 153 * S), fill=ACC)
    tracked(d, 166 * S, 159 * S, "FACE · VOICE · BRAIN · MEMORY", fm(16),
            (244, 244, 246), 5)

    # 좌측 메인 타이포
    d.text((90 * S, 545 * S), "사진 한 장에서", font=f(50, 400), fill=OFF, anchor="ls")
    d.text((90 * S, 620 * S), "실시간 대화 아바타까지", font=f(50, 400), fill=OFF, anchor="ls")
    d.text((90 * S, 790 * S), "AI 휴먼", font=f(118, 900), fill=OFF, anchor="ls")
    d.text((90 * S, 895 * S), "해부학", font=fs(104, 900), fill=ACC, anchor="ls")

    # 구분선
    d.rectangle((90 * S, 1000 * S, 270 * S, 1003 * S), fill=ACC)
    # 부제
    d.text((90 * S, 1065 * S), "얼굴·목소리·두뇌·기억 —", fs(26, 400),
           fill=(244, 244, 246), anchor="ls") if False else \
        d.text((90 * S, 1065 * S), "얼굴·목소리·두뇌·기억 —",
               font=fs(26, 400), fill=(220, 224, 228), anchor="ls")
    d.text((90 * S, 1105 * S), "네 층을 조립하고 실측하는 법.",
           font=fs(26, 400), fill=(220, 224, 228), anchor="ls")

    # 저자·출판사·푸터
    d.text((90 * S, 1620 * S), "이석창 지음", font=f(36, 700), fill=OFF, anchor="ls")
    tracked(d, 90 * S, 1680 * S, "github.com/leelang7 · youtube.com/@aidoer",
            fm(14), (170, 174, 180), 2)

    # ── 아트 합성 (--art 두상.png) ───────────────────────────────────────
    # Flow/Gemini 로 뽑은 '검정 배경 위 두상만' 이미지를 스크린 블렌드로 얹는다.
    # 검정은 투명처럼 사라지고 유리·빛만 남아 컬럼 위에 비친다. 글자·컬럼·03 은 이 코드가 그린다.
    # 우하단 워터마크는 아트의 아래 띠(--trim-bottom, 기본 13%)를 잘라 버린다 — 픽셀은 만지지 않는다.
    import sys as _sys
    if "--art" in _sys.argv:
        from PIL import ImageChops
        import numpy as _np
        art = Image.open(_sys.argv[_sys.argv.index("--art") + 1]).convert("RGB")
        tb = float(_sys.argv[_sys.argv.index("--trim-bottom") + 1]) if "--trim-bottom" in _sys.argv else 0.13
        aw, ah = art.size
        art = art.crop((0, 0, aw, int(ah * (1 - tb))))                         # 별이 있는 아래 띠 제거
        # 피사체 자동 크롭 — 검정보다 밝은 화소의 상자 + 여유 5%
        lum = _np.array(art.convert("L"))            # 복사본(asarray 는 읽기 전용)
        # 업스케일 JPEG 는 가장자리에 옅은 밝기 띠가 생겨 상자가 화면 끝까지 늘어난다 — 문턱을 올리고 테두리 2% 는 뺀다
        eh, ew = lum.shape; lum[:, :int(ew * 0.02)] = 0; lum[:, -int(ew * 0.02):] = 0; lum[:int(eh * 0.02), :] = 0
        ys, xs = _np.where(lum > 40)
        pad = int(max(art.size) * 0.05)
        box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(art.size[0], xs.max() + pad), min(art.size[1], ys.max() + pad))
        art = art.crop(box)
        # 검정점 보정 — 렌더의 '검정' 은 (12,12,14) 쯤이라 그대로 스크린하면 두상 둘레에 옅은 사각 얼룩이 남는다.
        # 바닥값을 0 으로 내리고 나머지를 늘린다 (레벨 보정 = 픽셀 편집이 아니라 합성 전처리).
        a = _np.asarray(art).astype(_np.float32)
        floor = float(_np.percentile(a.reshape(-1, 3).max(axis=1), 2))       # 배경 밝기(하위 2%)
        a = _np.clip((a - floor) / (255.0 - floor), 0, 1) * 255.0
        art = Image.fromarray(a.astype(_np.uint8))
        target_h = int(H * 0.64); s = target_h / art.size[1]
        art = art.resize((int(art.size[0] * s), target_h), Image.LANCZOS)
        cx, top = int(W * 0.60), int(H * 0.16)                                # 컬럼 경계(0.65W) 에 걸치되 세로 시리즈 글자는 비켜 간다
        x = min(max(0, cx - art.size[0] // 2), W - art.size[0]); y = top
        region = img.crop((x, y, x + art.size[0], y + art.size[1]))
        # 매트 — 검정 둘레는 완전 투명, 피사체만 스크린. 밝기로 만든 알파에 가장자리 페더를 곱한다.
        L = _np.asarray(art.convert("L")).astype(_np.float32)
        matte = _np.clip((L - 8.0) / 36.0, 0, 1)
        from PIL import ImageFilter as _IF
        matte = _np.asarray(Image.fromarray((matte * 255).astype(_np.uint8)).filter(_IF.GaussianBlur(1.5))).astype(_np.float32) / 255.0
        aw2, ah2 = art.size; fx = int(aw2 * 0.06); fy = int(ah2 * 0.06)
        ramp = _np.ones((ah2, aw2), _np.float32)
        ramp[:, :fx] *= _np.linspace(0, 1, fx)[None, :]; ramp[:, -fx:] *= _np.linspace(1, 0, fx)[None, :]
        ramp[:fy, :] *= _np.linspace(0, 1, fy)[:, None]; ramp[-fy:, :] *= _np.linspace(1, 0, fy)[:, None]
        matte = matte * ramp
        scr = _np.asarray(ImageChops.screen(region, art)).astype(_np.float32); bg = _np.asarray(region).astype(_np.float32)
        outp = bg + (scr - bg) * matte[..., None]
        img.paste(Image.fromarray(_np.clip(outp, 0, 255).astype(_np.uint8)), (x, y))
        print(f"[아트 합성] 피사체 상자 {box} → {art.size} @ ({x // S},{y // S})")
    out = img.resize((OUT_W, OUT_H), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT, quality=95)
    print(f"[Vol.03 표지] {OUT.name}  {OUT_W}×{OUT_H} (시리즈 시스템 계승·앰버 강조·고해상)")


if __name__ == "__main__":
    main()
