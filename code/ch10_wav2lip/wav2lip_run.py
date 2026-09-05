# -*- coding: utf-8 -*-
"""
Ch10 — Wav2Lip: 첫 성공을 설치에서 잃지 않기 위한 실행기

**정직하게** — 저자 환경에는 Wav2Lip 저장소가 없다(MuseTalk·LivePortrait 만 있다).
그래서 이 파일은 실행기이자 **설치 점검기** 다. Ch10 §4 가 말한 그대로 설치에서
막히는 사람이 실행에서 막히는 사람보다 많고, 그것을 코드로 막는다.

    ① 버전 핀       저자의 실습 노트북이 쓰는 조합 — 이 조합이 돌았다
    ② 사전 점검     저장소 · 가중치 · 얼굴 검출 모델 · 16kHz 모노 음성
    ③ 실행          점검이 다 통과할 때만 (env 의 python 을 절대 경로로)
    ④ 검산          Ch14 `check_lengths` + Ch09 세 지표 — 다른 장과 같은 자로 잰다

    python wav2lip_run.py --plan                         무엇이 있고 없는지
    python wav2lip_run.py --face f.mp4 --audio a.wav     실제 실행 (Wav2Lip env 필요)
    python wav2lip_run.py --check out.mp4 --audio a.wav  산출물 검산 (GPU 불필요)
"""
import argparse
import os
import subprocess
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("_lib", "ch09_verify"):
    sys.path.insert(0, os.path.join(ROOT, sub))

REPO = os.environ.get("WAV2LIP_DIR", where("wav2lip"))
ENV_PY = os.environ.get("WAV2LIP_PY", where("py_wav2lip"))

# Ch10 §4 — 저자 실습 노트북의 핀. 숫자는 시간이 지나면 바뀐다. **돌아간 조합을 적어 두는 습관** 이 요점.
PINS = {"numpy": "1.23.5", "librosa": "0.9.2", "opencv-python": "4.8.0.76"}
NEEDED = {"저장소": "inference.py", "립싱크 가중치": "checkpoints/wav2lip_gan.pth",
          "얼굴 검출 모델": "face_detection/detection/sfd/s3fd.pth"}


def preflight(repo: str = REPO) -> list:
    """(있는가, 이름, 경로). 실행 전에 무엇이 없는지 **전부** 말한다."""
    rows = [(os.path.exists(os.path.join(repo, p)), k, p) for k, p in NEEDED.items()]
    rows.append((os.path.exists(ENV_PY), "환경 python", ENV_PY))
    return rows


def command(face: str, audio: str, out: str, pads=(0, 10, 0, 0)) -> list:
    """`--pads` 아래 10 은 턱이 잘리는 흔한 실패(부록 F)를 막는 저자 기본값."""
    return [ENV_PY, "inference.py", "--checkpoint_path", "checkpoints/wav2lip_gan.pth",
            "--face", face, "--audio", audio, "--outfile", out,
            "--pads", *map(str, pads)]


def check_output(video: str, audio: str) -> dict:
    """다른 장과 같은 자 — Ch14 길이·프레임 검산, Ch09 세 지표."""
    from media import check_lengths
    from metrics import evaluate
    from verify_sync import mouth_activity, speech_spans
    lengths = check_lengths(video, audio)
    acts, fps = mouth_activity(video)
    score = evaluate(acts, fps, speech_spans(audio), top=15, duration=len(acts) / fps)
    return {"lengths": lengths, "score": score, "ok": lengths["ok"] and score["pass"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--face"); ap.add_argument("--audio")
    ap.add_argument("--out", default=os.path.join(HERE, "_work", "out.mp4"))
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--check")
    a = ap.parse_args()

    if a.check:
        r = check_output(a.check, a.audio)
        print(f"  길이/프레임: {r['lengths']}")
        print(f"  Ch09: 적중률 {r['score']['rate']:.0%} · 우연대비 {r['score']['lift']:.2f} · "
              f"조용 {r['score']['quiet_ratio']:.0%} → {'통과' if r['ok'] else '실패'}")
        return 0 if r["ok"] else 1

    rows = preflight()
    print("\n  Wav2Lip 사전 점검")
    for have, name, path in rows:
        print(f"    [{'있음' if have else '없음'}] {name:10} {path}")
    print("  버전 핀 :", " · ".join(f"{k}=={v}" for k, v in PINS.items()))
    missing = [n for h, n, _ in rows if not h]
    if a.plan or not (a.face and a.audio):
        if missing:
            print(f"\n  없는 것 {len(missing)}개 — 먼저 갖추세요. 저장소는 옛 코드라 위 핀으로 환경을 따로 만드세요 (Ch10 §4).")
        print("  명령    :", " ".join(command(a.face or "face.mp4", a.audio or "voice.wav", a.out)), "\n")
        return 0
    if missing:
        print("  실행 중단 — 없는 것:", ", ".join(missing)); return 1
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    p = subprocess.run(command(a.face, a.audio, a.out), cwd=REPO, capture_output=True,
                       text=True, errors="replace")
    if p.returncode or not os.path.exists(a.out):
        print("  실패 — 마지막 줄:", (p.stderr or p.stdout).strip().splitlines()[-1:]); return 1
    r = check_output(a.out, a.audio)
    print(f"  완료 → {a.out}  검산 {'통과' if r['ok'] else '실패'}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
