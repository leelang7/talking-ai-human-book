# -*- coding: utf-8 -*-
"""
Ch11 — MuseTalk v1.5 실행기 · 설정 생성 · 산출물 검산

이 파일은 이 책의 저자 환경에서 **실제로 돌아 결과를 냈다.**

    드라이버  driver_therapist.mp4 (사람 · 클로즈업 · 차분함 — Ch04 §3)
    음성      6.072초 한국어 wav
    결과      176프레임 · 1280×720 · 30000/1001fps · 108초 (모델 로드 포함)

돌리기 전에 세 번 죽었다. 셋 다 Ch10 §4 의 "낡은 연구 코드" 였다 —
diffusers · transformers 가 요구 버전 위로 밀려 있었고, requirements.txt 에 **없는**
peft 가 accelerate 와 안 맞았다. 저장소가 못박은 버전으로 되돌리자 돌았다.
그 과정을 `_work/env_fix.log` 에 그대로 남겼다.

    python musetalk_run.py --plan                       설정만 만들고 명령을 보여준다
    python musetalk_run.py --driver d.mp4 --audio a.wav 실제로 돌린다 (MuseTalk env 필요)
    python musetalk_run.py --check out.mp4 --audio a.wav 산출물 검산만 (GPU 불필요)
"""
import argparse
import os
import subprocess
import sys
import time
from fractions import Fraction
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# Ch15 §4 ① — 환경은 활성화가 아니라 **절대 경로** 로 부른다
ENV_PY = os.environ.get("MUSETALK_PY", where("py_musetalk"))
REPO = os.environ.get("MUSETALK_DIR", where("musetalk"))
UNET = "./models/musetalkV15/unet.pth"
UNET_CFG = "./models/musetalkV15/musetalk.json"

# 저장소가 못박은 버전 — 이것과 다르면 import 단계에서 죽는다 (실측: 3회)
PINS = {"diffusers": "0.30.2", "transformers": "4.39.2", "accelerate": "0.28.0",
        "peft": "0.12.0"}          # peft 는 requirements.txt 에 없지만 accelerate 0.28 과 맞아야 한다


def write_config(driver: str, audio: str, path: str) -> str:
    """MuseTalk 은 YAML 한 장으로 잡을 받는다. 경로는 슬래시로, 따옴표로 감싼다."""
    driver, audio = driver.replace("\\", "/"), audio.replace("\\", "/")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f'task_0:\n video_path: "{driver}"\n audio_path: "{audio}"\n')
    return path


def command(cfg: str, out_dir: str) -> list:
    return [ENV_PY, "-m", "scripts.inference", "--inference_config", cfg,
            "--result_dir", out_dir, "--unet_model_path", UNET,
            "--unet_config", UNET_CFG, "--version", "v15"]


def check_env() -> list:
    """버전이 핀과 다른 것을 알려준다. 돌리기 전에 6초짜리 실패를 미리 막는다."""
    try:
        out = subprocess.run([ENV_PY, "-m", "pip", "list"], capture_output=True, text=True,
                             timeout=60).stdout
    except Exception as e:
        return [f"env 확인 실패: {e}"]
    have = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            have[parts[0].lower()] = parts[1]
    return [f"{k} {have.get(k, '없음')} ≠ {v}" for k, v in PINS.items() if have.get(k) != v]


def check_output(video: str, audio: str) -> dict:
    """산출물 검산 — 길이만이 아니라 **프레임 수** 를 본다 (Ch14 · `_lib/media.check_lengths`).

    실측: 6.072초 음성에 176프레임. 29.97fps 면 182 이어야 한다. 6프레임(0.2초) 모자란다.
    이 부족분이 하류에서 '29fps 로 길이만 맞는' 드리프트로 둔갑한다.
    """
    from media import check_lengths
    return check_lengths(video, audio)


def run(driver: str, audio: str, out_dir: str, log=print) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    bad = check_env()
    if bad:
        log("[env] 핀과 다름: " + " · ".join(bad))
        log("[env] 고치는 법: " + ENV_PY + " -m pip install " +
            " ".join(f"{k}=={v}" for k, v in PINS.items()))
        return {"ok": False, "why": "env"}
    cfg = write_config(driver, audio, os.path.join(out_dir, "mt_cfg.yaml"))
    t0 = time.time()
    p = subprocess.run(command(cfg, out_dir), cwd=REPO, capture_output=True, text=True,
                       errors="replace")
    dt = time.time() - t0
    with open(os.path.join(out_dir, "run.log"), "w", encoding="utf-8") as f:
        f.write(p.stdout + "\n" + p.stderr)
    outs = []
    for dp, _, fs in os.walk(out_dir):
        outs += [os.path.join(dp, x) for x in fs if x.endswith(".mp4")]
    if p.returncode or not outs:
        log(f"[mt] 실패 exit={p.returncode} {dt:.0f}s — run.log 의 마지막 줄을 보라")
        return {"ok": False, "why": "run", "seconds": dt}
    out = max(outs, key=os.path.getmtime)
    r = check_output(out, audio)
    log(f"[mt] 완료 {dt:.0f}s → {out}")
    log(f"[mt] 검산 {r}")
    return {"ok": True, "seconds": dt, "output": out, "check": r}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver"); ap.add_argument("--audio")
    ap.add_argument("--out", default=os.path.join(HERE, "_work", "out"))
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--check", help="이 산출물만 검산 (GPU 불필요)")
    a = ap.parse_args()

    if a.check:
        r = check_output(a.check, a.audio)
        print(f"  {r}")
        return 0 if r["ok"] else 1

    d = a.driver or os.path.join(REPO, "data/video/driver_therapist.mp4")
    w = a.audio or os.path.join(REPO, "data/audio/_script.wav")
    if a.plan or not (a.driver and a.audio):
        cfg = write_config(d, w, os.path.join(a.out, "mt_cfg.yaml")) if os.path.isdir(a.out) \
            else "(out 폴더 없음 — 실제 실행 시 생성)"
        print("\n  실행 환경 :", ENV_PY)
        print("  버전 핀   :", " · ".join(f"{k}=={v}" for k, v in PINS.items()))
        print("  명령      :", " ".join(command("mt_cfg.yaml", a.out)))
        print("\n  실측(저자 환경): 6.072초 음성 → 176프레임 · 1280×720 · 30000/1001 · 108초\n")
        return 0
    r = run(d, w, a.out)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
