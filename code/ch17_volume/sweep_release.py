# -*- coding: utf-8 -*-
"""
Ch17 §4 — 닫는 속도(release) 스윕. 실제 파일 넷에서 세 지표를 같이 본다.

    조용한 프레임(RMS < 0.06) 중 입이 열린 비율   ← Ch09 §5 의 상한 35% 와 대조
    발화 끝 → 입이 닫히기까지 프레임 수
    발화 중 떨림 (|Δ| 평균)                        ← 닫힘을 빠르게 할수록 커진다

    python sweep_release.py    → _work/release_sweep.json
"""
import json, os
from measure import AUDIO, OPEN, frames_rms, run

FILES = ("_script.wav", "_chat.wav", "_stt.wav", "_live.wav")
QUIET = 0.06
RELEASES = (0.15, 0.25, 0.35, 0.5, 0.7, 1.0)


def main():
    data = {n: frames_rms(os.path.join(AUDIO, n))[0] for n in FILES}
    out = {}
    print("  release  조용한프레임 열림(평균)  발화끝→닫힘(f)  떨림(발화 중 |Δ| 평균)")
    for rel in RELEASES:
        q, cl, jt = [], [], []
        for lv in data.values():
            d = run(lv, release=rel)
            quiet = [i for i, v in enumerate(lv) if v < QUIET]
            voiced = [i for i, v in enumerate(lv) if v >= QUIET]
            q.append(sum(d[i] > OPEN for i in quiet) / len(quiet))
            tail = d[voiced[-1]:]
            cl.append(next((k for k, v in enumerate(tail) if v < OPEN), len(tail)))
            jt.append(sum(abs(d[i] - d[i - 1]) for i in voiced if i > 0) / len(voiced))
        out[str(rel)] = {"quiet_open_ratio": round(sum(q) / len(q), 3),
                         "frames_to_close": round(sum(cl) / len(cl), 1),
                         "jitter": round(sum(jt) / len(jt), 3)}
        print(f"  {rel:5.2f}        {sum(q)/len(q):5.0%}              {sum(cl)/len(cl):4.1f}           {sum(jt)/len(jt):.3f}")
    json.dump({"files": FILES, "quiet_threshold_rms": QUIET, "open_threshold": OPEN,
               "sweep": out, "ch09_quiet_max": 0.35, "chosen_release": 0.35},
              open(os.path.join("_work", "release_sweep.json"), "w", encoding="utf-8"), indent=1)
    print("  → _work/release_sweep.json")


if __name__ == "__main__":
    main()
