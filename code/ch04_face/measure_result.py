# -*- coding: utf-8 -*-
"""
리타게팅 결과 실측 — 드라이버별 '입이 열렸나 · 머리가 흔들렸나' 를 픽셀로 잰다 (Ch04 §5)

같은 소스·같은 음성으로 드라이버만 바꾼 결과 영상 여러 개를 받아, 첫 프레임 대비 픽셀 변화량을
세 영역에서 평균낸다. 사람 얼굴 검출에 기대는 Ch09 검증기는 동물 얼굴에서 무너지므로(§5 주석),
동물 결과는 이렇게 영역 기준으로 잰다. 값은 0~255 회색조 절대차의 평균 — 클수록 많이 움직였다.

  입 영역   세로 55~80% · 가로 35~65%  (정면 얼굴 크롭 기준 입·턱)
  머리 영역  세로 0~45%               (귀·이마 — 머리가 돌면 크게 변한다)
  눈 영역   세로 30~48% · 가로 20~80%

    python measure_result.py 테라피스트=a.mp4 d3=b.mp4 d19=c.mp4
    python measure_result.py --json _work/mint_drivers_result.json ...   결과를 JSON 으로도 저장

책의 표(Ch04 §5)는 2026-09-05 민트 렌더 셋에 이 스크립트를 돌린 값이다.
"""
import argparse
import json
import sys

import numpy as np


def load_gray(path):
    import cv2
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32))
    return frames, cap.get(cv2.CAP_PROP_FPS)


def region_delta(frames, y0, y1, x0, x1):
    H, W = frames[0].shape
    base = frames[0][int(H * y0):int(H * y1), int(W * x0):int(W * x1)]
    return [float(np.abs(f[int(H * y0):int(H * y1), int(W * x0):int(W * x1)] - base).mean()) for f in frames]


def measure(path):
    frames, fps = load_gray(path)
    mouth = region_delta(frames, 0.55, 0.80, 0.35, 0.65)
    head = region_delta(frames, 0.00, 0.45, 0.00, 1.00)
    eyes = region_delta(frames, 0.30, 0.48, 0.20, 0.80)
    return {"frames": len(frames), "fps": fps,
            "mouth_mean": round(float(np.mean(mouth)), 1), "mouth_max": round(float(np.max(mouth)), 1),
            "head_mean": round(float(np.mean(head)), 1), "eyes_mean": round(float(np.mean(eyes)), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items", nargs="+", help="이름=영상경로")
    ap.add_argument("--json", help="결과 저장 경로")
    a = ap.parse_args()
    out = {}
    print("\n  %-12s %8s %8s %8s %8s" % ("드라이버", "입 평균", "입 최대", "머리", "눈"))
    for it in a.items:
        name, path = it.split("=", 1)
        m = measure(path)
        out[name] = m
        print("  %-12s %8.1f %8.1f %8.1f %8.1f" % (name, m["mouth_mean"], m["mouth_max"], m["head_mean"], m["eyes_mean"]))
    print()
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  → %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
