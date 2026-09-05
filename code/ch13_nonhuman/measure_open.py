# -*- coding: utf-8 -*-
"""
입 벌린 소스는 입을 다물 수 있나 — 결과 영상의 '입 공동(어두운 픽셀) 비율' 을 프레임마다 잰다 (Ch13 §5)

리타게팅은 소스의 입 모양에서 *출발* 한다. 입을 다문 소스는 드라이버가 열 때 열리고 다물 때 닫힌다.
입을 벌린 소스는 드라이버가 다물어도 소스의 벌어진 입이 그대로 남는다 — 그 사실을 숫자로 확인한다.

  입 공동 비율 = 입 영역(세로 58~80% · 가로 35~65%)에서 밝기 70 미만인 픽셀의 비율
  다문 프레임  = 그 비율이 0.02 미만인 프레임 수

    python measure_open.py 닫힘=a.mp4 열림=b.mp4 [--json _work/open_source_result.json]

책의 수치(Ch13 §5)는 2026-06-02 렌더(s39 · cat_open2, 같은 드라이버)에 이 스크립트를 돌린 값이다.
"""
import argparse
import json
import sys

import numpy as np


def cavity_ratio(path, thresh=70):
    import cv2
    cap = cv2.VideoCapture(path)
    out = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        H, W = g.shape
        box = g[int(H * 0.58):int(H * 0.80), int(W * 0.35):int(W * 0.65)]
        out.append(float((box < thresh).mean()))
    return out, cap.get(cv2.CAP_PROP_FPS)


def measure(path):
    r, fps = cavity_ratio(path)
    return {"frames": len(r), "fps": fps, "first": round(r[0], 3), "min": round(min(r), 3),
            "max": round(max(r), 3), "mean": round(float(np.mean(r)), 3),
            "closed_frames": int(sum(1 for x in r if x < 0.02)),
            "t_min": round(int(np.argmin(r)) / fps, 2), "t_max": round(int(np.argmax(r)) / fps, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items", nargs="+", help="이름=영상경로")
    ap.add_argument("--json")
    a = ap.parse_args()
    out = {}
    print("\n  %-14s %6s %6s %6s %6s %8s" % ("소스", "첫", "최소", "최대", "평균", "다문 프레임"))
    for it in a.items:
        name, path = it.split("=", 1)
        m = measure(path)
        out[name] = m
        print("  %-14s %6.3f %6.3f %6.3f %6.3f %5d/%d" % (name, m["first"], m["min"], m["max"], m["mean"], m["closed_frames"], m["frames"]))
    print()
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  → %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
