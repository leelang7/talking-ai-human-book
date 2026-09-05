# -*- coding: utf-8 -*-
"""
Ch10 실측 — 격리 환경에서 Wav2Lip 을 돌리고, Ch11 과 같은 잣대로 잰다.

    같은 드라이버(driver_therapist.mp4) · 같은 음성(_script.wav 6.07초)
    벽시계 · 출력 해상도/fps/프레임 수 · Ch09 검증(적중률 · 우연 대비 · 조용한 구간)

    WAV2LIP_DIR=... WAV2LIP_PY=... python measure.py    → _work/probe.json
"""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "ch09_verify"))
import wav2lip_run as W
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402

FACE = os.path.join(where("musetalk"), "data", "video", "driver_therapist.mp4")
AUDIO = os.path.join(where("musetalk"), "data", "audio", "_script.wav")
OUT = os.path.join(HERE, "_work", "out.mp4")


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                        "stream=width,height,r_frame_rate,nb_frames", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    w, h, fps, n = r.stdout.strip().split(",")
    return {"size": f"{w}x{h}", "fps": fps, "frames": int(n)}


def main():
    os.makedirs(os.path.join(HERE, "_work"), exist_ok=True)
    cmd = W.command(FACE, AUDIO, OUT)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=W.REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    wall = round(time.time() - t0, 1)
    tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
    rec = {"measured": time.strftime("%Y-%m-%d"), "env_python": W.ENV_PY, "repo": W.REPO, "face": FACE, "audio": AUDIO,
           "returncode": p.returncode, "wall_s": wall, "tail": tail}
    print(f"  종료 {p.returncode} · 벽시계 {wall}s")
    if p.returncode == 0 and os.path.exists(OUT):
        rec["output"] = probe(OUT)
        print("  출력:", rec["output"])
        import verify_sync as V, metrics as M
        acts, fps = V.mouth_activity(OUT)                 # (프레임별 입 활동, 영상 fps)
        spans = V.speech_spans(AUDIO)
        r = M.evaluate(acts, fps, spans, 15, len(acts) / fps if fps else None)
        rec["ch09"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k != "reasons"}
        rec["ch09"]["roi_mode"] = V.LAST_ROI.get("mode")
        rec["ch09"]["reasons"] = r.get("reasons", [])
        print("  Ch09:", {k: rec["ch09"][k] for k in rec["ch09"] if k != "reasons"})
    else:
        print("  실패 — 마지막 줄:", tail)
    json.dump(rec, open(os.path.join(HERE, "_work", "probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/probe.json")


if __name__ == "__main__":
    main()
