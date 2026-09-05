# -*- coding: utf-8 -*-
"""
Ch15 §5 — 원격 GPU 로 보내기 전에 하는 두 가지

실제 잡 제출은 GPU 와 컨테이너 이미지가 있어야 한다. 그 앞에 GPU 없이 할 수 있는
판단이 둘 있고, 둘 다 틀리면 비싸다.

    ① 이 입력을 남의 GPU 로 보내도 되는가      — Ch28 §6. 고인·미성년·의료는 안 된다
    ② 보내면 무엇이 돌 것인가                  — Ch15 §4 ⑤. 이미 된 단계를 또 돌리지 않는다

둘 다 `--plan` 으로 끝난다. 실제 제출은 `atl run avatar_job.py --gpu …` 이고,
그 스크립트는 Ch28 §4 의 컨테이너 안에서 돈다.

    python run_remote.py --plan --script 대본.txt --photo 사진.jpg --driver drv.mp4 [--tag deceased]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "ch28_deploy"))

from pipeline import ORDER, Pipeline  # noqa: E402

try:
    from jobqueue import LOCAL_ONLY, placement_for  # noqa: E402  (Ch28 §6 의 규칙 그대로)
except Exception:                                   # ch28 폴더가 없어도 이 파일은 돈다
    LOCAL_ONLY = "local_only"

    def placement_for(tags):
        return LOCAL_ONLY if any(t in ("deceased", "minor", "medical", "legal") for t in tags) else "anywhere"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--photo", required=True)
    ap.add_argument("--driver", required=True)
    ap.add_argument("--tag", action="append", default=[], help="deceased · minor · medical …")
    ap.add_argument("--work", default=os.path.join(HERE, "_work"))
    ap.add_argument("--plan", action="store_true", help="판단과 계획만 출력한다 (기본)")
    a = ap.parse_args()

    # ① 어디서 돌릴 것인가 — 태그 하나가 결정한다. 사람이 기억할 일이 아니다.
    where = placement_for(a.tag)
    print(f"\n  배치: {where}" + ("  ← 남의 GPU 로 나가지 않는다 (Ch28 §6)" if where == LOCAL_ONLY else ""))

    # ② 무엇이 돌 것인가 — 실행기는 넣지 않는다. 계획만 낸다.
    p = Pipeline(a.work, runners={n: None for n in ORDER}, log=lambda s: None)
    files = p.stage_inputs(a.script, a.photo, a.driver)
    print("  계획:")
    for name, action, why in p.plan(files):
        print(f"    {name:8} {action:4}  {why}")
    # 원격 잡은 **사진 + 음성 wav** 를 받는다 — 대본이 아니다. TTS(①)는 GPU 가 필요 없으니
    # 로컬에서 먼저 돌리고, 그 산출물 voice.wav 만 보낸다. Ch15 §5 의 "입력이 파일 두 개" 가 이것이다.
    voice = os.path.join(a.work, "voice.wav")
    print("\n  실제 제출 (TTS 는 로컬에서 먼저):")
    print(f"    python pipeline.py --only tts  → {voice}")
    print("    atl run avatar_job.py --gpu --image atl-avatar:1 "
          f"--data {os.path.basename(a.photo)} --data voice.wav\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
