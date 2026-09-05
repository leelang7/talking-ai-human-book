# -*- coding: utf-8 -*-
"""
Ch14 — ffmpeg mux 명령 정적 검사기

Ch14 §4·§6 의 체크리스트를 **명령줄에서 기계적으로** 확인한다.
영상을 만들기 전에 돌린다 — 렌더가 4분 걸린 뒤에 `-r` 위치가 틀렸다는 것을
알게 되는 것보다 낫다.

    python mux_lint.py -- ffmpeg -r 30000/1001 -i v.mp4 -i a.wav ...
    python mux_lint.py --self          내장 예제로 시연

검사하는 것 — 전부 저자가 실제로 당한 것들이다.

  ① -r 이 -i 뒤에 있다        입력 재해석이 아니라 출력 재인코딩이 된다 (Ch14 §4)
  ② setpts 로 늘렸다          증상을 덮고 프레임 타이밍을 왜곡한다 (Ch14 §3)
  ③ -map 이 없다              소스에 딸린 원본 오디오가 섞인다 (Ch14 §6)
  ④ -pix_fmt 가 없다          브라우저에서만 재생 안 되는 영상이 나온다
  ⑤ 코덱이 암묵적이다          컨테이너에 따라 다른 코덱이 선택된다
  ⑥ -shortest 가 없다         길이 다른 두 입력이 뒤에서 어긋난다
  ⑦ fps 를 소수로 줬다        29.97 은 30000/1001 이다 (부록 F 15번)
"""
import re
import sys
from fractions import Fraction

ERROR, WARN = "ERROR", "WARN"


def _idx(argv, *names):
    """옵션이 처음 나오는 위치. 없으면 -1."""
    for i, a in enumerate(argv):
        if a in names:
            return i
    return -1


def _all_idx(argv, name):
    return [i for i, a in enumerate(argv) if a == name]


def lint(argv: list[str]) -> list[tuple[str, str, str]]:
    """(수준, 코드, 설명) 목록. 빈 목록이면 통과."""
    out = []
    if argv and argv[0].endswith(("ffmpeg", "ffmpeg.exe")):
        argv = argv[1:]

    inputs = _all_idx(argv, "-i")
    n_in = len(inputs)
    first_i = inputs[0] if inputs else len(argv)
    joined = " ".join(argv)

    # ① -r 위치 — 이 장의 핵심
    r_positions = [i for i, a in enumerate(argv) if a == "-r"]
    for i in r_positions:
        if i > first_i:
            out.append((ERROR, "r-after-i",
                        "-r 이 -i 뒤에 있다 — 입력을 재해석하는 것이 아니라 "
                        "출력을 그 fps 로 다시 만든다. 프레임이 버려지거나 복제된다."))
    if n_in and not r_positions:
        out.append((WARN, "no-r",
                    "-r 이 없다 — 소스 fps 를 그대로 믿는 것이다. "
                    "29.97 소스라면 여기서 어긋남이 시작된다."))

    # ⑦ fps 표기
    for i in r_positions:
        if i + 1 < len(argv):
            v = argv[i + 1]
            if "/" not in v:
                try:
                    f = float(v)
                except ValueError:
                    continue
                if abs(f - round(f)) > 1e-9:
                    out.append((WARN, "fps-float",
                                f"-r {v} — 소수 대신 분수로 주세요. "
                                f"29.97 은 {Fraction(30000, 1001)} 입니다."))

    # ② setpts
    if "setpts" in joined:
        out.append((ERROR, "setpts",
                    "setpts 로 길이를 맞추고 있다 — 증상을 덮는 해법이다. "
                    "프레임 타이밍이 왜곡되고 원인은 남는다 (Ch14 §3)."))

    # ⑧ 표시 메타데이터 — 2026 년부터 합성 영상은 표시가 법이다 (Ch29 §3)
    #    파일 단계에서 가장 싼 표시는 컨테이너 메타데이터 한 줄이다.
    out_is_mp4 = bool(argv) and argv[-1].lower().endswith((".mp4", ".mov", ".webm", ".mkv"))
    meta_vals = [argv[i + 1] for i in _all_idx(argv, "-metadata") if i + 1 < len(argv)]
    if out_is_mp4 and not any(re.search(r"(?i)ai|synth|generated|생성", v) for v in meta_vals):
        out.append((WARN, "no-label",
                    "AI 생성 표시 메타데이터가 없다 — "
                    "-metadata comment=\"AI-generated · 생성로그 …\" 한 줄이면 된다 (Ch29 §3)."))

    # ③ 스트림 매핑
    if n_in >= 2 and not _all_idx(argv, "-map"):
        out.append((ERROR, "no-map",
                    "입력이 둘인데 -map 이 없다 — 소스 영상에 딸린 "
                    "원본 오디오가 결과에 섞일 수 있다."))

    # ④ 픽셀 포맷
    if _idx(argv, "-pix_fmt") < 0:
        out.append((WARN, "no-pixfmt",
                    "-pix_fmt 가 없다 — yuv420p 가 아니면 일부 브라우저가 재생하지 못한다."))
    else:
        v = argv[_idx(argv, "-pix_fmt") + 1] if _idx(argv, "-pix_fmt") + 1 < len(argv) else ""
        if v and v != "yuv420p":
            out.append((WARN, "pixfmt",
                        f"-pix_fmt {v} — 호환성을 원하면 yuv420p."))

    # ⑤ 코덱
    if _idx(argv, "-c:v", "-vcodec") < 0 and _idx(argv, "-c", "-codec") < 0:
        out.append((WARN, "no-vcodec", "-c:v 가 없다 — H.264(libx264)를 명시하세요."))
    if n_in >= 2 and _idx(argv, "-c:a", "-acodec") < 0 and _idx(argv, "-c", "-codec") < 0:
        out.append((WARN, "no-acodec", "-c:a 가 없다 — AAC 를 명시하세요."))

    # ⑥ 길이
    if n_in >= 2 and "-shortest" not in argv and "-t" not in argv:
        out.append((WARN, "no-shortest",
                    "-shortest 가 없다 — 길이가 다른 두 입력이 뒤에서 어긋난다."))
    return out


GOOD = ["ffmpeg", "-y", "-r", "30000/1001", "-i", "lp_output.mp4", "-i", "voice.wav",
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        "-metadata", "comment=AI-generated · 생성 로그 ID 참조 (Ch29 §3)",   # 표시는 파일에도 남긴다
        "final.mp4"]

BAD = ["ffmpeg", "-y", "-i", "lp_output.mp4", "-i", "voice.wav",
       "-filter:v", "setpts=1.033*PTS", "-r", "29.97", "final.mp4"]


def _show(title, argv):
    print(f"\n  {title}")
    print(f"    $ {' '.join(argv)}")
    found = lint(argv)
    if not found:
        print("    통과 — 지적 없음")
    for lv, code, msg in found:
        print(f"    [{lv:5}] {code:12} {msg}")
    return found


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "--self":
        print("\n  ── Ch14 mux 명령 검사 ──")
        _show("책이 권하는 명령", GOOD)
        bad = _show("흔한 잘못된 명령", BAD)
        print(f"\n  같은 두 파일을 합치는 명령인데 하나는 지적 0건, "
              f"하나는 {len(bad)}건입니다.\n")
        return 0
    if args[0] == "--":
        args = args[1:]
    found = lint(args)
    for lv, code, msg in found:
        print(f"  [{lv:5}] {code:12} {msg}")
    if not found:
        print("  통과 — 지적 없음")
    return 1 if any(lv == ERROR for lv, _, _ in found) else 0


if __name__ == "__main__":
    sys.exit(main())
