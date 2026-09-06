# -*- coding: utf-8 -*-
"""감정 4종 클로닝 A/B — 제로샷 · 파인튜닝 · 음색 변환을 숫자로 (Ch03 §3)

같은 화자, 같은 대사로 뽑아 둔 wav 를 읽어 넷을 잰다.

    길이(초)          — 낭독 속도
    끝 늘어짐(초)     — 마지막 유성 구간이 얼마나 끌리는가 (한국어 클로닝의 고질)
    음높이 중앙값(Hz) — 목소리의 자리
    음높이 폭 IQR(Hz) — 감정 표현의 폭

    python measure_clone_ab.py [--dir D:/_감정_XTTS_vs_OpenVoice] [--json _work/clone_emotion_ab.json]

책의 표(Ch03 §3)는 2026-06-29 산출물에 이 스크립트를 돌린 값이다.
파일이 없으면(다른 기계) 건너뛴다 — 원본 음원은 저장소에 넣지 않는다(용량·초상).
"""
import argparse
import glob
import json
import os
import sys

DEFAULT_DIRS = [r"D:\_감정_XTTS_vs_OpenVoice", r"D:\_감정_XTTS_vs_OpenVoice_감정대사"]


def measure(path):
    import numpy as np
    import librosa
    y, sr = librosa.load(path, sr=None, mono=True)
    f0 = librosa.yin(y, fmin=70, fmax=400, sr=sr)
    v = f0[(f0 > 75) & (f0 < 380)]
    s = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    thr = s.max() * 0.08
    idx = np.nonzero(s > thr)[0]
    tail = 0.0
    if len(idx):
        j = end = idx[-1]
        while j > 0 and s[j] > thr * 0.6:          # 끝에서 되짚어 유성 구간의 시작을 찾는다
            j -= 1
        tail = (end - j) * 256 / sr
    return {"sec": round(len(y) / sr, 2),
            "tail_s": round(tail, 3),
            "f0_med": round(float(np.median(v)), 1) if len(v) else None,
            "f0_iqr": round(float(np.percentile(v, 75) - np.percentile(v, 25)), 1) if len(v) else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", action="append", default=None)
    ap.add_argument("--json", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work", "clone_emotion_ab.json"))
    a = ap.parse_args()
    dirs = a.dir or DEFAULT_DIRS
    rows = []
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(d, "*.wav"))):
            rows.append(dict(file=os.path.basename(p), folder=os.path.basename(d), **measure(p)))
    if not rows:
        print("  음원이 없다 — 이 검사는 저자 기계에서만 돈다. 결과는 _work/clone_emotion_ab.json 에 있다.")
        return 0
    for r in rows:
        print("  %-32s %5.2f초 · 끝 %.3f초 · %sHz(폭 %s)" % (r["file"], r["sec"], r["tail_s"], r["f0_med"], r["f0_iqr"]))
    os.makedirs(os.path.dirname(a.json), exist_ok=True)
    json.dump(rows, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
