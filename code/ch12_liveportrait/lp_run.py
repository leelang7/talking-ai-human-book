# -*- coding: utf-8 -*-
"""
Ch12 — LivePortrait 실행기 (사람 · 동물) · 파라미터 스윕 · 산출물 검산

저자 환경에서 **실제로 돌아 결과를 냈다.**

    소스      s39.jpg (고양이)          드라이버  MuseTalk 이 만든 '말하는 상담사' (Ch11)
    설정      --animation-region lip · --driving-multiplier 3.0
              --flag-crop-driving-video · --no_flag_stitching      ← Ch12 §6 의 출하 조합
    결과      176프레임 · 512×512 · 28초 · 그리고 **r_frame_rate = 29/1**

마지막 줄이 Ch14 §2 다. 드라이버는 30000/1001 인데 결과는 29 로 나온다.
이 파일의 `check_output()` 이 그것을 잡는다.

    python lp_run.py --plan                                 명령만
    python lp_run.py --source cat.jpg --driver talking.mp4  실제 실행 (LivePortrait env)
    python lp_run.py --sweep 1.5 2.0 3.0 ...                배율 스윕 (Ch13 §5 의 혀 딜레마를 눈으로)
    python lp_run.py --check out.mp4                        산출물 검산만 (GPU 불필요)
"""
import argparse
import os
import subprocess
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

ENV_PY = os.environ.get("LIVEPORTRAIT_PY", where("py_liveportrait"))
REPO = os.environ.get("LIVEPORTRAIT_DIR", where("liveportrait"))

# Ch12 §6 — 실제로 출하한 조합. 배율 3.0 은 `lip` 이라서 가능한 값이다 (사람 얼굴엔 쓰지 마라).
ANIMAL_FLAGS = ["--animation-region", "lip", "--driving-multiplier", "3.0",
                "--flag-crop-driving-video", "--no_flag_stitching"]
# 동물 모드는 --driving-option 을 **읽지 않는다** (Ch12 §5 ①). 넘겨도 무해하지만 넣지 않는다.


def command(source: str, driver: str, out_dir: str, animal: bool = True,
            multiplier: float = 3.0, region: str = "lip") -> list:
    script = "inference_animals.py" if animal else "inference.py"
    flags = ["--animation-region", region, "--driving-multiplier", str(multiplier),
             "--flag-crop-driving-video", "--no_flag_stitching"]
    return [ENV_PY, script, "-s", source, "-d", driver, "--output-dir", out_dir] + flags


def check_output(video: str) -> dict:
    """Ch14 의 지문 — 결과 fps 가 드라이버와 다른가."""
    from media import probe
    v = probe(video)
    fps_raw = v.get("fps_raw", "")
    return {"frames": v.get("frames"), "fps": fps_raw, "duration": v.get("duration"),
            "size": f"{v.get('width')}x{v.get('height')}",
            "warn": ("결과가 정수 fps 다 — 드라이버가 29.97 이었다면 Ch14 §2 의 드리프트다"
                     if fps_raw and "/1" in fps_raw and fps_raw != "30/1" else None)}


def run(source: str, driver: str, out_dir: str, animal=True, multiplier=3.0,
        region="lip", log=print) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    p = subprocess.run(command(source, driver, out_dir, animal, multiplier, region),
                       cwd=REPO, capture_output=True, text=True, errors="replace")
    dt = time.time() - t0
    with open(os.path.join(out_dir, "run.log"), "w", encoding="utf-8") as f:
        f.write(p.stdout + "\n" + p.stderr)
    outs = [os.path.join(out_dir, x) for x in os.listdir(out_dir)
            if x.endswith(".mp4") and "concat" not in x]
    if p.returncode or not outs:
        log(f"[lp] 실패 exit={p.returncode} {dt:.0f}s — run.log 를 보라")
        return {"ok": False, "seconds": dt}
    out = max(outs, key=os.path.getmtime)
    concat = out.replace(".mp4", "_concat.mp4")           # 드라이버·소스·결과 비교 영상 (Ch09 §6)
    r = check_output(out)
    log(f"[lp] 완료 {dt:.0f}s · 배율 {multiplier} · {r['size']} · {r['frames']}프레임 @ {r['fps']}")
    if r["warn"]:
        log("[lp] ⚠ " + r["warn"])
    return {"ok": True, "seconds": dt, "output": out,
            "concat": concat if os.path.exists(concat) else None, "check": r}


def sweep(source, driver, out_root, values, log=print) -> list:
    """배율만 바꿔 여러 번. Ch13 §5 의 '3.0 을 넘으면 혀' 를 눈으로 확인하는 용도."""
    rows = []
    for m in values:
        r = run(source, driver, os.path.join(out_root, f"m{m}"), True, m, "lip", log)
        rows.append({"multiplier": m, **r})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source"); ap.add_argument("--driver")
    ap.add_argument("--out", default=os.path.join(HERE, "_work", "out"))
    ap.add_argument("--human", action="store_true", help="사람 모드 (기본은 동물)")
    ap.add_argument("--multiplier", type=float, default=3.0)
    ap.add_argument("--region", default="lip", choices=["lip", "eyes", "exp", "pose", "all"])
    ap.add_argument("--sweep", nargs="+", type=float)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--check")
    a = ap.parse_args()

    if a.check:
        r = check_output(a.check); print(f"  {r}"); return 0
    s = a.source or os.path.join(REPO, "assets/examples/source/s39.jpg")
    d = a.driver or os.path.join(os.path.dirname(HERE), "ch11_musetalk", "_work", "out",
                                 "v15", "driver_therapist__script.mp4")
    if a.plan or not (a.source and a.driver):
        print("\n  실행 환경 :", ENV_PY)
        print("  명령      :", " ".join(command(s, d, a.out, not a.human, a.multiplier, a.region)))
        print("  동물 모드는 --driving-option 을 읽지 않는다 (Ch12 §5)")
        print("  실측(저자 환경): 176프레임 · 512×512 · 28초 · r_frame_rate=29/1 ← Ch14 §2\n")
        return 0
    if a.sweep:
        for row in sweep(s, d, os.path.join(HERE, "_work", "sweep"), a.sweep):
            print(f"  배율 {row['multiplier']}: {'OK' if row['ok'] else '실패'} "
                  f"{row.get('seconds', 0):.0f}s {row.get('output', '')}")
        return 0
    r = run(s, d, a.out, not a.human, a.multiplier, a.region)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
