# -*- coding: utf-8 -*-
"""
Ch04 §3 ★ — 미디엄샷 드라이버는 왜 "싱크가 안 맞는" 것처럼 보이는가

본문의 주장은 이렇다.

> 얼굴이 화면의 4분의 1 정도를 차지하는 미디엄샷을 드라이버로 쓰면, 입 모션이
> 낮은 해상도로 추출된다. 그 약한 모션이 소스 얼굴로 옮겨지면 입이 조금밖에
> 안 움직이고, 사용자는 이것을 "싱크가 안 맞는다" 고 느낀다.

말로는 그럴듯하다. **재 보자.**

합성 얼굴을 프레임 안에 여러 크기로 담고(카메라가 하듯 **줄여서** 넣는다),
파이프라인이 하는 그대로 얼굴을 크롭해 256×256 으로 맞춘 다음 둘을 잰다.

  · **디테일**   입 영역의 라플라시안 분산 — 초점 측정의 표준 지표
  · **총 진폭**  입을 다물었을 때와 벌렸을 때 화면이 달라지는 양

**결과는 본문의 설명을 반쯤만 지지한다.** 총 진폭은 거의 안 변하고
디테일만 4.7배 차이가 난다. 무엇이 실제로 사라지는지는 아래 표를 보라.

난수를 쓰지 않으므로 몇 번을 돌려도 같은 값이 나온다.

    python closeup.py
"""
import numpy as np

FRAME_H, FRAME_W = 1080, 1920
CROP = 256                       # 파이프라인이 얼굴을 맞추는 크기
TEETH_LINES = 7                  # 입 안의 고주파 성분 — 잃을 것이 있어야 잰다


CANON = 1024                     # "실제 얼굴" 을 그리는 해상도 — 카메라가 담기 전


def _canon_face(mouth_open: float):
    """실제 얼굴 하나. **모든 이목구비가 얼굴 크기에 비례한다.**

    치아 선을 목표 크기에서 바로 그리면 안 된다 — 그러면 작은 얼굴일수록
    선이 촘촘해져서 앨리어싱이 '디테일' 로 잡힌다. 실제로 첫 측정이 그렇게
    거꾸로 나왔다. 카메라는 **큰 것을 작게 담는다.** 그 순서를 지켜야 한다.
    """
    h = CANON
    w = int(h * 0.72)
    img = np.full((h, w), 30, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    face = (((yy - h / 2) / (h / 2)) ** 2 + ((xx - w / 2) / (w / 2)) ** 2) <= 1.0
    img[face] = 180

    for sx in (-0.22, 0.22):
        ey, ex = int(h * 0.38), int(w / 2 + w * sx)
        r = max(1, int(h * 0.035))
        img[ey - r:ey + r, ex - r * 2:ex + r * 2] = 40

    mh = max(2, int(h * 0.03 + h * 0.10 * mouth_open))
    mw = int(w * 0.34)
    my, mx = int(h * 0.72), w // 2
    y0, y1 = my - mh // 2, my + mh // 2
    x0, x1 = mx - mw // 2, mx + mw // 2
    img[y0:y1, x0:x1] = 60
    step = max(2, (y1 - y0) // TEETH_LINES)          # 선 간격도 입 크기에 비례
    for ty in range(y0 + step // 2, y1, step):
        img[ty:ty + max(1, step // 4), x0:x1] = 230
    return img


def synth_frame(face_ratio: float, mouth_open: float = 1.0):
    """카메라가 담은 프레임. 실제 얼굴을 **줄여서** 프레임에 넣는다.

    이 순서가 요점이다 — 얼굴이 화면에서 작으면 센서가 그만큼 적게 담고,
    그때 잃은 것은 나중에 확대해도 돌아오지 않는다.
    """
    img = np.full((FRAME_H, FRAME_W), 30, dtype=np.float32)
    fh = max(8, int(FRAME_H * face_ratio))
    fw = int(fh * 0.72)
    face = _resize(_canon_face(mouth_open), fh, fw)      # ← 카메라의 다운샘플

    cy, cx = FRAME_H // 2, FRAME_W // 2
    y0, x0 = cy - fh // 2, cx - fw // 2
    img[y0:y0 + fh, x0:x0 + fw] = face
    return img, (x0, y0, fw, fh)


def _resize(src, out_h, out_w):
    """이중선형 리샘플. 줄일 때는 디테일이 사라지고, 늘릴 때는 생기지 않는다."""
    h, w = src.shape
    ys = np.linspace(0, h - 1, out_h)
    xs = np.linspace(0, w - 1, out_w)
    y0 = np.floor(ys).astype(int).clip(0, h - 2)
    x0 = np.floor(xs).astype(int).clip(0, w - 2)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    a = src[np.ix_(y0, x0)]
    b = src[np.ix_(y0, x0 + 1)]
    c = src[np.ix_(y0 + 1, x0)]
    d = src[np.ix_(y0 + 1, x0 + 1)]
    return (a * (1 - fy) * (1 - fx) + b * (1 - fy) * fx
            + c * fy * (1 - fx) + d * fy * fx).astype(np.float32)


def _laplacian_var(a):
    """라플라시안 분산 — 남아 있는 디테일의 양. 초점 측정의 표준 지표."""
    k = (a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:] - 4 * a[1:-1, 1:-1])
    return float(k.var())


def mouth_patch(face_ratio: float, mouth_open: float = 1.0):
    """파이프라인이 하는 그대로 — 얼굴을 크롭해 256 으로 맞추고 입 영역을 낸다."""
    img, (x0, y0, fw, fh) = synth_frame(face_ratio, mouth_open)
    crop = img[y0:y0 + fh, x0:x0 + fw]
    resized = _resize(crop, CROP, CROP)
    return resized[int(CROP * 0.60):int(CROP * 0.86), int(CROP * 0.28):int(CROP * 0.72)]


def detail_after_crop(face_ratio: float, mouth_open: float = 1.0) -> dict:
    fh = max(8, int(FRAME_H * face_ratio))
    return {"face_px": fh,
            "mouth_px": max(1, int(fh * 0.13)),
            "detail": _laplacian_var(mouth_patch(face_ratio, mouth_open))}


def gross_amplitude(face_ratio: float) -> float:
    """입을 다물었을 때와 벌렸을 때 화면이 달라지는 양 — **대조군.**

    이 값은 얼굴 크기와 거의 무관하다. 그것이 이 측정의 요점이다 —
    변하지 않는 것이 있어야 변하는 것이 무엇인지 특정된다.
    """
    a = mouth_patch(face_ratio, 0.0)
    b = mouth_patch(face_ratio, 1.0)
    return float(np.abs(b - a).mean())


def report(ratios=(0.15, 0.25, 0.40, 0.55, 0.70, 0.85)):
    base = gross_amplitude(max(ratios))
    rows = []
    for r in ratios:
        d = detail_after_crop(r)
        s = gross_amplitude(r)
        rows.append({"ratio": r, "face_px": d["face_px"], "mouth_px": d["mouth_px"],
                     "detail": d["detail"], "amplitude": s,
                     "amp_rel": s / base if base else 0.0})
    return rows


def _demo():
    rows = report()
    top = max(r["detail"] for r in rows)
    print()
    print("  카메라가 얼굴을 프레임의 몇 할로 담느냐에 따라,")
    print("  크롭·리사이즈 뒤 입에 남는 것" + chr(10))
    print("   비율   얼굴px  입px   입 디테일  꽉참대비    총 진폭  꽉참대비")
    print("  " + "─" * 64)
    for r in rows:
        print(f"   {r['ratio']:.2f}   {r['face_px']:>5}  {r['mouth_px']:>4}"
              f"  {r['detail']:>9.0f}  {r['detail'] / top:>7.0%}"
              f"   {r['amplitude']:>7.1f}  {r['amp_rel']:>7.0%}")
    print()
    med = next(x for x in rows if x["ratio"] == 0.25)
    big = next(x for x in rows if x["ratio"] == 0.85)
    print(f"  미디엄샷(0.25)과 클로즈업(0.85)을 견주면 —")
    print(f"    입 디테일  {med['detail']:.0f} → {big['detail']:.0f}"
          f"   ({big['detail'] / med['detail']:.1f}배)")
    print(f"    총 진폭    {med['amplitude']:.1f} → {big['amplitude']:.1f}"
          f"   ({big['amplitude'] / med['amplitude']:.2f}배)")
    print()
    print("  **입이 열리는 양은 거의 그대로이고, 입 모양의 해상도만 무너진다.**")
    print("  거칠게 벌어졌다 닫히기는 하는데 소리에 맞는 모양이 안 나온다 —")
    print("  그것이 '싱크가 안 맞는다' 로 느껴지는 실체다.")
    print()


if __name__ == "__main__":
    _demo()
