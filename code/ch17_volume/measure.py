# -*- coding: utf-8 -*-
"""
Ch17 실측 — 진짜 음성 파일로 MouthDriver 를 돌려 본다.

  ① 무음 파일(_silent.wav)에서 '날것' 과 '네 처리' 가 각각 입을 몇 프레임 여는가
  ② 발화 파일(_script.wav)에서 열림 비율, 그리고 말이 끝난 뒤 닫히기까지 몇 프레임인가
  ③ 노이즈 게이트(②')를 끄면 무음에서 무슨 일이 나는가 — 회귀가 잡은 그 결함

    python measure.py    → _work/measure.json
"""
import json, os, struct, wave
from mouth import MouthDriver
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402

AUDIO = os.path.join(where("musetalk"), "data", "audio")
FPS = 30
OPEN = 0.05          # 이 위면 '입이 열렸다' 고 본다 (3단 이미지에서 1단 이상)


def frames_rms(path):
    with wave.open(path, "rb") as w:
        sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    assert sw == 2, sw
    s = struct.unpack(f"<{len(raw)//2}h", raw)
    if ch > 1:
        s = s[::ch]
    s = [x / 32768.0 for x in s]
    hop = int(sr / FPS)
    return [MouthDriver.rms(s[i:i + hop]) for i in range(0, len(s) - hop + 1, hop)], sr


def run(levels, **kw):
    d = MouthDriver(**kw)
    return [d.feed(v) for v in levels]


def main():
    out = {}
    raw_kw = dict(attack=1.0, release=1.0, floor=0.0, curve=1.0, noise_gate=0.0)
    for name in ("_silent.wav", "_script.wav", "_chat.wav", "_stt.wav", "_live.wav"):
        lv, sr = frames_rms(os.path.join(AUDIO, name))
        raw, drv, nogate = run(lv, **raw_kw), run(lv), run(lv, noise_gate=0.0)
        voiced = [i for i, v in enumerate(lv) if v >= 0.02]
        rec = {"sr": sr, "frames": len(lv), "rms_max": round(max(lv), 4), "rms_median": round(sorted(lv)[len(lv)//2], 4),
               "open_ratio_raw": round(sum(v > OPEN for v in raw) / len(lv), 3),
               "open_ratio_driven": round(sum(v > OPEN for v in drv) / len(lv), 3),
               "open_ratio_no_gate": round(sum(v > OPEN for v in nogate) / len(lv), 3)}
        if voiced:
            last = voiced[-1]
            tail = drv[last:]
            closed = next((k for k, v in enumerate(tail) if v < OPEN), None)
            rec["last_voiced_frame"] = last
            rec["frames_to_close_after_speech"] = closed
            rec["ms_to_close_after_speech"] = None if closed is None else round(closed * 1000 / FPS)
            rec["max_open_during_speech"] = round(max(drv[voiced[0]:last + 1]), 3)
        out[name] = rec
        print(f"  {name:13s} {len(lv):4d}f  rms max {rec['rms_max']:.3f} med {rec['rms_median']:.4f} | 열림 날것 {rec['open_ratio_raw']:.0%} · 네처리 {rec['open_ratio_driven']:.0%} · 게이트없음 {rec['open_ratio_no_gate']:.0%}"
              + (f" | 발화 끝→닫힘 {rec['frames_to_close_after_speech']}f({rec['ms_to_close_after_speech']}ms)" if voiced else ""))
    dd = {k: v for k, v in vars(MouthDriver()).items() if not k.startswith("_") and k != "value"}
    out["params"] = {"fps": FPS, "open_threshold": OPEN, "driver_defaults": dd}
    json.dump(out, open(os.path.join("_work", "measure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/measure.json")


if __name__ == "__main__":
    main()
