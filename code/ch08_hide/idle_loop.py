# -*- coding: utf-8 -*-
"""
Ch08 — 아이들 루프 만들기

    python idle_loop.py --plan                 명령만 출력 (ffmpeg 없어도 됨)
    python idle_loop.py --silence idle.wav     무음 wav 만 만든다
    python idle_loop.py --loop src.mp4 out.mp4 원본+역재생 루프를 만든다

절차는 셋이다.

  ① 무음 wav 를 만든다                       (§3 — 안 그러면 대기 중에 혼자 떠든다)
  ② 그 무음으로 립싱크를 한 번 돌린다          ← GPU 가 필요한 유일한 단계
  ③ 결과를 원본 + 역재생으로 이어붙인다        (§2 — 이음매를 없앤다)

②는 이 책의 Track A 파이프라인(Ch10~12)이 하는 일이므로 여기서는
명령만 출력한다. ①과 ③은 여기서 실제로 만든다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "_lib"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hide import IDLE_SECONDS, silent_wav  # noqa: E402

LOOP_FILTER = "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[v]"


def plan(src="source.mp4", wav="idle_silence.wav", raw="idle_raw.mp4",
         out="idle_loop.mp4"):
    return [
        ("① 무음",
         f"python idle_loop.py --silence {wav}          # {IDLE_SECONDS}초 · 16kHz 모노"),
        ("② 립싱크",
         f"python ../ch15_pipeline/run.py --image {src} --audio {wav} --out {raw}"),
        ("③ 루프",
         f"python idle_loop.py --loop {raw} {out}"),
    ]


def make_loop(src: str, out: str) -> str:
    """원본 + 역재생. 시작과 끝이 같은 프레임이라 무한 반복해도 안 보인다."""
    from media import make_idle_loop           # code/_lib/media.py
    return make_idle_loop(src, out)


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "--plan":
        print("\n  ── 아이들 루프 만들기 ──\n")
        for label, cmd in plan():
            print(f"  {label}\n     $ {cmd}\n")
        print(f"  ③ 이 쓰는 ffmpeg 필터\n     -filter_complex \"{LOOP_FILTER}\"\n")
        print("  ②만 GPU 가 필요하고, 서버가 뜰 때 한 번만 돌린다.\n")
        return 0

    if args[0] == "--silence":
        dst = args[1] if len(args) > 1 else "idle_silence.wav"
        secs = float(args[2]) if len(args) > 2 else IDLE_SECONDS
        with open(dst, "wb") as f:
            f.write(silent_wav(secs))
        print(f"  {dst} — {secs}초 무음 ({os.path.getsize(dst):,} bytes)")
        return 0

    if args[0] == "--loop":
        if len(args) < 3:
            print("  사용법: idle_loop.py --loop <src.mp4> <out.mp4>")
            return 2
        try:
            p = make_loop(args[1], args[2])
        except Exception as e:                  # ffmpeg 가 없거나 입력이 없을 때
            print(f"  실패: {e}")
            return 1
        print(f"  {p} — 원본 + 역재생, 이음매 없음")
        return 0

    print(f"  모르는 옵션: {args[0]}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
