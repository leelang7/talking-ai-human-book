# -*- coding: utf-8 -*-
"""
Ch14 회귀 테스트 — 본문의 숫자와 코드가 같은지 확인한다

이 파일이 하는 일은 **책이 인쇄한 값을 코드로 다시 계산** 하는 것이다.
3.3% · 0.33초 · 3초 · 100초 — 넷 다 본문에 활자로 박혀 있는 숫자다.
값이 바뀌면 여기서 먼저 터진다.

    python test_mux.py
"""
import sys
from fractions import Fraction

sys.path.insert(0, __file__.rsplit("test_mux.py", 1)[0] or ".")

from fps_math import (NTSC, NTSC_FAMILY, as_fraction, drift_ratio,  # noqa: E402
                      drift_seconds, ffmpeg_rate, noticeable_after)
from mux_lint import BAD, ERROR, GOOD, lint  # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    if cond:
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        _f += 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    print("\n  ── Ch14 fps · mux ──")

    # ── 본문 §2 의 숫자 ────────────────────────────────────────────
    r29 = drift_ratio(29, NTSC)
    ok(abs(r29 * 100 - 3.3) < 0.05, "29 vs 29.97 은 3.3% 다 (본문 §2)",
       f"{r29 * 100:.2f}%")

    d10 = drift_seconds(29, NTSC, 10)
    ok(abs(d10 - 0.33) < 0.005, "10초 영상 끝에서 0.33초가 밀린다 (본문 §2)",
       f"{d10:.3f}초")

    t29 = noticeable_after(29, NTSC)
    ok(abs(t29 - 3.0) < 0.1, "29 는 3초에서 100ms 를 넘는다 (본문 §2 표)",
       f"{t29:.1f}초")

    t30 = noticeable_after(30, NTSC)
    ok(abs(t30 - 100) < 2, "30 은 100초에서야 100ms 를 넘는다 (본문 §2 표)",
       f"{t30:.0f}초")

    # 30 이 29 보다 '더 위험' 하다는 주장의 근거 — 짧은 클립을 통과한다
    ok(drift_seconds(30, NTSC, 10) < 0.02 and drift_seconds(30, NTSC, 120) > 0.1,
       "30 은 10초 클립을 통과하고 120초에서 터진다",
       f"10초 {drift_seconds(30, NTSC, 10):.3f}초 → 120초 {drift_seconds(30, NTSC, 120):.3f}초")

    # 어긋남이 '누적' 이라는 지문 — 길이에 정확히 비례해야 한다
    a, b = drift_seconds(29, NTSC, 10), drift_seconds(29, NTSC, 100)
    ok(abs(b - a * 10) < 1e-9, "어긋남은 길이에 비례해 쌓인다 (균일 지연이 아니다)",
       f"10초 {a:.3f} · 100초 {b:.3f}")

    # 같은 fps 면 어긋나지 않는다
    ok(noticeable_after(NTSC, NTSC) == float("inf"), "fps 가 같으면 영원히 안 어긋난다")

    # ── 부록 F 15번 — 정수/분수 ─────────────────────────────────────
    ok(as_fraction(30) == Fraction(30, 1), "정수 fps 도 분수로 다룬다")
    ok(as_fraction("30000/1001") == NTSC, "분수 문자열을 그대로 받는다")
    ok(as_fraction(29.97) == NTSC, "표기값 29.97 을 진짜 값 30000/1001 로 바꾼다",
       str(as_fraction(29.97)))
    ok(float(NTSC) != 29.97, "29.97 과 30000/1001 은 애초에 같은 수가 아니다",
       f"{float(NTSC):.8f} vs 29.97000000")
    ok(as_fraction(23.976) == Fraction(24000, 1001), "23.976 도 같은 표로 처리된다")
    ok(as_fraction(30) == Fraction(30, 1), "NTSC 가 아닌 값은 건드리지 않는다")
    ok(ffmpeg_rate(NTSC) == "30000/1001", "ffmpeg 에는 분수 문자열로 넘긴다")

    # ── §4 -r 위치 ─────────────────────────────────────────────────
    ok(lint(GOOD) == [], "책이 권하는 명령은 지적 0건")

    # GOOD 에서 -r 짝만 마지막 입력 뒤로 옮긴다. 다른 것은 하나도 안 건드린다.
    rest = [a for a in GOOD if a not in ("-r", "30000/1001")]
    j = len(rest) - 1 - rest[::-1].index("voice.wav")
    after = rest[:j + 1] + ["-r", "30000/1001"] + rest[j + 1:]
    codes = [c for _, c, _ in lint(after)]
    ok("r-after-i" in codes, "-r 을 -i 뒤로 옮기면 잡힌다 (§4 의 그 한 칸)")

    # 두 명령은 **같은 토큰을 같은 개수로** 갖는다. 순서 하나만 다르다.
    ok(sorted(after) == sorted(GOOD),
       "두 명령은 토큰 집합이 완전히 같고 순서만 다르다", "그래서 눈으로는 안 보인다")

    # ── §3 setpts ──────────────────────────────────────────────────
    codes = [c for _, c, _ in lint(BAD)]
    ok("setpts" in codes, "setpts 로 늘리는 것을 잡는다 (§3)")
    ok("fps-float" in codes, "-r 29.97 을 소수로 준 것을 잡는다")
    ok("no-map" in codes, "입력 둘에 -map 없는 것을 잡는다 (§6)")
    ok("no-pixfmt" in codes, "-pix_fmt 없는 것을 잡는다 (§6)")

    # ERROR 와 WARN 을 구분한다 — 전부 빨간불이면 아무도 안 본다
    lv = {c: l for l, c, _ in lint(BAD)}
    ok(lv.get("setpts") == ERROR and lv.get("no-pixfmt") == "WARN",
       "고쳐야 하는 것과 권고를 구분한다")

    # 입력이 하나면 -map·-shortest 를 요구하지 않는다 (오탐 방지)
    one = ["ffmpeg", "-r", "30000/1001", "-i", "v.mp4", "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "o.mp4"]
    codes = [c for _, c, _ in lint(one)]
    ok("no-map" not in codes and "no-shortest" not in codes,
       "입력이 하나면 매핑·길이를 지적하지 않는다")

    print(f"\n  {_n - _f}/{_n} 통과\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
