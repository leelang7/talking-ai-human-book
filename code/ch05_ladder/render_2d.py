# -*- coding: utf-8 -*-
"""
Ch05 §3 — 1단이 정말 GPU 없이 도는가

결정표의 *"GPU 불필요"* 는 주장이다. 재 본다.

2D 파츠 합성은 **이미지 네 장을 옮기고 눌러서 겹치는 일** 이 전부다.
여기서는 그 합성만 순수 numpy 로 돌려 프레임당 비용을 잰다. 브라우저는
이보다 빠르다(GPU 합성을 쓴다) — 즉 이 값은 **가장 느린 쪽의 값** 이다.

    python render_2d.py
"""
import time

import numpy as np

W, H = 512, 512
PARTS = ("body", "eye_l", "eye_r", "mouth")

# 파츠마다 변형 기준점이 다르다 (Ch16 §3) — 눈=중앙 / 입=위 / 몸통=바닥
ANCHOR = {"body": "bottom", "eye_l": "center", "eye_r": "center", "mouth": "top"}


def make_parts(seed=0):
    """투명 배경 파츠 넷. 실제 그림 대신 사각형이지만 합성 비용은 같다."""
    rng = np.random.default_rng(seed)
    parts = {}
    boxes = {"body": (140, 200, 232, 300), "eye_l": (190, 180, 44, 26),
             "eye_r": (280, 180, 44, 26), "mouth": (216, 250, 80, 44)}
    for name, (x, y, w, h) in boxes.items():
        rgba = np.zeros((h, w, 4), dtype=np.float32)
        rgba[..., :3] = rng.random((h, w, 3), dtype=np.float32) * 0.5 + 0.4
        rgba[..., 3] = 1.0
        parts[name] = {"img": rgba, "x": x, "y": y}
    return parts


def _squash(rgba, scale_y, anchor):
    """세로로 눌러 찌그러뜨린다. 기준점에 따라 남는 자리가 달라진다."""
    h, w, _ = rgba.shape
    nh = max(1, int(round(h * scale_y)))
    ys = np.linspace(0, h - 1, nh)
    y0 = np.floor(ys).astype(int).clip(0, h - 2)
    fy = (ys - y0)[:, None, None]
    out = rgba[y0] * (1 - fy) + rgba[y0 + 1] * fy
    pad_total = h - nh
    if anchor == "center":
        top = pad_total // 2
    elif anchor == "top":
        top = 0
    else:                                   # bottom
        top = pad_total
    full = np.zeros_like(rgba)
    full[top:top + nh] = out
    return full


def composite(parts, blink=0.0, mouth=0.0):
    """한 프레임. blink 1.0 = 완전히 감음, mouth 1.0 = 완전히 벌림."""
    canvas = np.zeros((H, W, 3), dtype=np.float32)
    for name in PARTS:
        p = parts[name]
        img = p["img"]
        if name.startswith("eye"):
            img = _squash(img, max(0.02, 1.0 - blink), ANCHOR[name])
        elif name == "mouth":
            img = _squash(img, 0.25 + 0.75 * mouth, ANCHOR[name])
        h, w, _ = img.shape
        y, x = p["y"], p["x"]
        a = img[..., 3:4]
        region = canvas[y:y + h, x:x + w]
        canvas[y:y + h, x:x + w] = region * (1 - a) + img[..., :3] * a
    return canvas


def measure(frames=120):
    parts = make_parts()
    composite(parts)                          # 워밍업 — 첫 호출은 할당 비용이 섞인다
    t0 = time.perf_counter()
    for i in range(frames):
        composite(parts, blink=(i % 30) / 30.0, mouth=(i % 7) / 7.0)
    dt = time.perf_counter() - t0
    return {"frames": frames, "seconds": dt,
            "ms_per_frame": dt / frames * 1000.0, "fps": frames / dt}


def _demo():
    m = measure()
    print()
    print(f"  512×512 · 파츠 4개 · {m['frames']}프레임 합성")
    print(f"    프레임당 {m['ms_per_frame']:.2f}ms  →  {m['fps']:.0f}fps  (CPU 만으로)")
    print()
    budget = 1000 / 60
    print(f"  60fps 예산은 프레임당 {budget:.1f}ms 입니다. "
          f"{'통과' if m['ms_per_frame'] < budget else '초과'}.")
    print()
    print("  결정표의 'GPU 불필요' 는 주장이 아니라 측정입니다.")
    print("  브라우저는 GPU 합성을 쓰므로 이보다 빠릅니다 — 이건 가장 느린 쪽의 값입니다.")
    print()
    parts = make_parts()
    for name, anchor in ANCHOR.items():
        img = parts[name]["img"]
        sq = _squash(img, 0.3, anchor)
        rows = np.where(sq[..., 3].sum(axis=1) > 0)[0]
        print(f"    {name:7} 기준={anchor:7} 눌린 뒤 남는 행 {rows[0]}~{rows[-1]}"
              f" / 전체 {img.shape[0]}")
    print()


if __name__ == "__main__":
    _demo()
