# -*- coding: utf-8 -*-
"""
Ch23 §2 실측 — 실제 녹음 넷에 VAD 를 돌려 종료 판정 침묵 길이를 비교한다.

  침묵 길이(silence_ms)를 300·500·800·1000 으로 바꿔 가며
    발화 조각 수(START 이벤트)   ← 짧으면 한 문장이 여러 조각으로 갈라진다
    마지막 END 까지의 지연        ← 길면 말 끝나고 답이 늦다
  를 센다. 임계값은 첫 1초로 보정한다(§2 — 환경을 코드에 박지 말고 시작할 때 재라).

    python measure.py    → _work/measure.json
"""
import json, os, struct, wave
from vad import Vad, FRAME_MS, START, END
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402

AUDIO = os.path.join(where("musetalk"), "data", "audio")
FILES = ("_script.wav", "_chat.wav", "_stt.wav", "_live.wav")
SIL = (300, 500, 800, 1000)


def levels(path, frame_ms=FRAME_MS):
    with wave.open(path, "rb") as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        s = struct.unpack(f"<{n*ch}h", w.readframes(n))[::ch]
    s = [x / 32768.0 for x in s]; hop = int(sr * frame_ms / 1000)
    return [(sum(x * x for x in s[i:i + hop]) / hop) ** 0.5 for i in range(0, len(s) - hop + 1, hop)]


def main():
    out = {}
    print(f"  {'파일':12s} {'임계':>6s} | " + " | ".join(f"{s}ms: 조각·끝지연" for s in SIL))
    for name in FILES:
        lv = levels(os.path.join(AUDIO, name)); last_loud = max(i for i, v in enumerate(lv) if v >= 0.02) * FRAME_MS
        v0 = Vad(); thr = v0.calibrate(lv[:1000 // FRAME_MS])
        row = {"threshold": round(thr, 4), "frames": len(lv), "last_loud_ms": last_loud, "by_silence_ms": {}}
        cells = []
        for s in SIL:
            v = Vad(silence_ms=s, threshold=thr); starts = ends = 0; end_ms = None
            for i, x in enumerate(lv):
                e = v.feed(x)
                if e and e[0] == START: starts += 1
                if e and e[0] == END: ends += 1; end_ms = i * FRAME_MS
            e = v.finish()                                     # 파일 끝 — 침묵을 기다리지 않고 닫는다
            if e:
                ends += 1; end_ms = len(lv) * FRAME_MS; row.setdefault("flushed_at_eof", []).append(s)
            delay = None if end_ms is None else end_ms - last_loud
            row["by_silence_ms"][str(s)] = {"segments": starts, "end_delay_ms": delay}
            cells.append(f"{starts:2d}·{'없음' if delay is None else str(delay)+'ms':>6s}")
        out[name] = row
        print(f"  {name:12s} {thr:6.3f} | " + " | ".join(f"{c:14s}" for c in cells))
    json.dump({"measured": "2026-09-03", "frame_ms": FRAME_MS, "files": out}, open(os.path.join("_work", "measure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/measure.json")


if __name__ == "__main__":
    main()
