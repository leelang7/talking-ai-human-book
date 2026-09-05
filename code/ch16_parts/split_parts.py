# -*- coding: utf-8 -*-
"""
Ch16 — 그림 한 장을 파츠로 쪼개는 도구

캐릭터 그림 하나를 **몸통 · 왼눈 · 오른눈 · 입** 네 조각으로 자르고,
잘라낸 자리를 주변 색으로 메운 몸통을 만든다. 그리고 파츠마다
**변형 기준점(transform-origin)** 을 지정한 매니페스트를 함께 낸다.

이 도구가 지키는 것 (Ch16 §4):
    · 여백을 남긴다        — 딱 맞게 자르면 변형할 때 경계가 잘린다
    · 기준점이 파츠마다 다르다 — 눈=중앙, 입=위쪽, 몸통=바닥
    · 몸통의 구멍을 메운다   — 눈·입이 항상 그 위에 오지만 완벽할 필요는 없다

실행:
    python split_parts.py character.png --eyeL 120,96 --eyeR 180,96 --mouth 150,170
    python split_parts.py character.png --auto        # 얼굴 검출로 좌표 추정
    python split_parts.py --demo                      # 샘플 그림을 만들어 쪼갠다

산출물: parts/{body,eyeL,eyeR,mouth}.png + parts/manifest.json
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# 파츠별 기본 크기(원본 대비 비율)와 변형 기준점 — Ch16 §4
SPEC = {
    "eyeL":  {"w": 0.13, "h": 0.09, "origin": "center center", "margin": 0.6},
    "eyeR":  {"w": 0.13, "h": 0.09, "origin": "center center", "margin": 0.6},
    "mouth": {"w": 0.22, "h": 0.10, "origin": "center top",    "margin": 0.8},
}


def crop_with_margin(img, cx, cy, w, h, margin):
    """여백을 붙여 자른다. margin=0.6 이면 상하좌우로 60% 씩 더 가져온다.

    딱 맞게 자르면 눈을 늘리거나 입을 크게 벌릴 때 경계가 잘린다(Ch16 §4).
    """
    mw, mh = int(w * (1 + margin)), int(h * (1 + margin))
    x0, y0 = max(0, cx - mw // 2), max(0, cy - mh // 2)
    x1, y1 = min(img.shape[1], x0 + mw), min(img.shape[0], y0 + mh)
    return img[y0:y1, x0:x1].copy(), (x0, y0, x1 - x0, y1 - y0)


def inpaint_hole(img, boxes):
    """잘라낸 자리를 주변 색으로 메운다.

    완벽할 필요가 없다 — 눈과 입이 **항상 그 위에** 그려지기 때문이다.
    그래도 메우지 않으면 변형 중 원본 눈이 삐져나와 보인다.
    """
    mask = np.zeros(img.shape[:2], np.uint8)
    for (x, y, w, h) in boxes:
        # 실제 파츠보다 살짝 작게 지운다 — 경계가 뜨는 것 방지
        pad = int(min(w, h) * 0.12)
        mask[y + pad:y + h - pad, x + pad:x + w - pad] = 255
    return cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA)


def to_rgba(bgr):
    """PNG 로 저장할 때 알파를 붙인다(모서리를 부드럽게)."""
    h, w = bgr.shape[:2]
    a = np.full((h, w), 255, np.uint8)
    k = max(2, int(min(h, w) * 0.06))
    a[:k, :] = np.linspace(0, 255, k, dtype=np.uint8)[:, None]
    a[-k:, :] = np.linspace(255, 0, k, dtype=np.uint8)[:, None]
    return cv2.merge([*cv2.split(bgr), a])


def auto_points(img):
    """얼굴 검출로 눈·입 좌표를 추정한다. 실패하면 비율로 찍는다."""
    h, w = img.shape[:2]
    try:
        cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        f = cc.detectMultiScale(g, 1.1, 5)
        if len(f):
            x, y, fw, fh = sorted(f, key=lambda r: -r[2] * r[3])[0]
            return ((x + int(fw * 0.31), y + int(fh * 0.42)),
                    (x + int(fw * 0.69), y + int(fh * 0.42)),
                    (x + fw // 2, y + int(fh * 0.72)))
    except Exception:
        pass
    print("  ! 얼굴 검출 실패 — 비율로 추정합니다. 좌표를 직접 주는 편이 정확합니다.")
    return ((int(w * .38), int(h * .38)), (int(w * .62), int(h * .38)), (w // 2, int(h * .58)))


def make_demo():
    """샘플 캐릭터를 그려서 도구를 점검한다(그림 파일 없이 실행 가능)."""
    img = np.full((320, 260, 3), (250, 246, 240), np.uint8)
    cv2.ellipse(img, (130, 150), (100, 120), 0, 0, 360, (184, 213, 246), -1)
    cv2.ellipse(img, (98, 130), (16, 16), 0, 0, 360, (58, 47, 42), -1)
    cv2.ellipse(img, (162, 130), (16, 16), 0, 0, 360, (58, 47, 42), -1)
    cv2.ellipse(img, (130, 200), (34, 12), 0, 0, 180, (63, 68, 180), -1)
    p = os.path.join(HERE, "demo_character.png")
    cv2.imwrite(p, img)
    return p, (98, 130), (162, 130), (130, 200)


def parse_pt(s):
    x, y = s.split(",")
    return int(x), int(y)


def main():
    ap = argparse.ArgumentParser(description="2D 파츠 분할기 (Ch16)")
    ap.add_argument("image", nargs="?")
    ap.add_argument("--eyeL"), ap.add_argument("--eyeR"), ap.add_argument("--mouth")
    ap.add_argument("--auto", action="store_true", help="얼굴 검출로 좌표 추정")
    ap.add_argument("--demo", action="store_true", help="샘플 그림 생성 후 분할")
    ap.add_argument("--out", default=os.path.join(HERE, "parts"))
    a = ap.parse_args()

    if a.demo or not a.image:
        if not a.demo:
            print("이미지가 없어 데모로 실행합니다.\n")
        path, el, er, mo = make_demo()
    else:
        path = a.image
        if not os.path.exists(path):
            print(f"파일 없음: {path}"); return 1

    # 부록 H §1 — 한글 경로에서도 읽히도록 바이트로 디코딩
    with open(path, "rb") as f:
        img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print("이미지 디코딩 실패"); return 1
    h, w = img.shape[:2]

    if not (a.demo or not a.image):
        if a.auto or not (a.eyeL and a.eyeR and a.mouth):
            el, er, mo = auto_points(img)
        else:
            el, er, mo = parse_pt(a.eyeL), parse_pt(a.eyeR), parse_pt(a.mouth)

    os.makedirs(a.out, exist_ok=True)
    print(f"  원본 {w}×{h}  ·  눈L{el} 눈R{er} 입{mo}\n")

    boxes, manifest = [], {"source": os.path.basename(path), "size": [w, h], "parts": {}}
    for name, (cx, cy) in (("eyeL", el), ("eyeR", er), ("mouth", mo)):
        s = SPEC[name]
        part, box = crop_with_margin(img, cx, cy, int(w * s["w"]), int(h * s["h"]), s["margin"])
        cv2.imwrite(os.path.join(a.out, f"{name}.png"), to_rgba(part))
        boxes.append(box)
        manifest["parts"][name] = {
            "file": f"{name}.png", "box": list(box),
            "center_pct": [round(cx / w * 100, 2), round(cy / h * 100, 2)],
            "origin": s["origin"],
        }
        print(f"  {name:<6} {box[2]}×{box[3]}  기준점={s['origin']}")

    body = inpaint_hole(img, boxes)
    cv2.imwrite(os.path.join(a.out, "body.png"), body)
    manifest["parts"]["body"] = {"file": "body.png", "origin": "center bottom"}
    print(f"  {'body':<6} {w}×{h}  기준점=center bottom  (잘린 자리 메움)")

    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n  → {a.out}")
    print("  ▸ 기준점이 파츠마다 다릅니다. 눈=중앙, 입=위쪽, 몸통=바닥 (Ch16 §4)")
    print("  ▸ 여백을 붙여 잘랐습니다. 딱 맞게 자르면 변형 시 경계가 잘립니다.")
    print("  ▸ 다음: Ch17 에서 이 파츠에 음량을 물려 입을 엽니다.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
