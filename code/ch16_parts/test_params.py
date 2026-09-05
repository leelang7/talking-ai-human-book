# -*- coding: utf-8 -*-
"""
Ch16 회귀 테스트 — 네 손잡이

Ch16 본문이 `eyeOpen · mouthOpen · bodyLean · headY` 를 이름으로 부른다.
**본문이 부르는 이름이 코드에 있어야 한다.** 이 파일이 그 약속을 지킨다.

    python test_params.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from params import (DEFAULTS, EYE_MIN_SCALE, MOUTH_MIN_SCALE, RANGES,  # noqa: E402
                    apply, clamp)
from split_parts import SPEC  # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def scale_of(transform: str) -> float:
    return float(transform[transform.index("(") + 1:transform.index(")")])


def main() -> int:
    print("\n  ── Ch16 파츠 파라미터 ──")

    # ── 본문이 부르는 이름 넷이 전부 있다 ──────────────────────────
    for k in ("eyeOpen", "mouthOpen", "bodyLean", "headY"):
        ok(k in RANGES and k in DEFAULTS, f"★ 본문의 `{k}` 가 코드에 있다", f"{RANGES[k]}")

    # ── 기준점은 SPEC 에서 온다 (Ch16 §3 · 도판 F6) ─────────────────
    t = apply({})
    ok(t["eyeL"][0] == SPEC["eyeL"]["origin"] == "center center",
       "★ 눈의 기준점은 중앙 — SPEC 과 같다")
    ok(t["mouth"][0] == SPEC["mouth"]["origin"] == "center top",
       "★ 입의 기준점은 위 — 윗입술이 고정된다")
    ok(t["body"][0] == "center bottom", "★ 몸통의 기준점은 바닥 — 발이 안 뜬다")

    # ── 값이 뜻대로 움직인다 ───────────────────────────────────────
    ok(scale_of(apply({"eyeOpen": 1.0})["eyeL"][1]) == 1.0, "eyeOpen=1 이면 눈이 원래 크기")
    closed = scale_of(apply({"eyeOpen": 0.0})["eyeL"][1])
    ok(abs(closed - EYE_MIN_SCALE) < 1e-9 and closed > 0,
       "eyeOpen=0 이어도 0 이 아니다 — 눈이 사라지면 안 된다", f"{closed}")
    ok(scale_of(apply({"eyeOpen": 0.5})["eyeL"][1]) < scale_of(apply({"eyeOpen": 0.9})["eyeL"][1]),
       "eyeOpen 이 커지면 눈도 커진다 (단조)")
    ok(apply({"eyeOpen": 0.3})["eyeL"][1] == apply({"eyeOpen": 0.3})["eyeR"][1],
       "양쪽 눈이 같은 값을 받는다")

    shut = scale_of(apply({"mouthOpen": 0.0})["mouth"][1])
    ok(abs(shut - MOUTH_MIN_SCALE) < 1e-9, "다문 입도 두께가 있다", f"{shut}")
    ok(scale_of(apply({"mouthOpen": 1.0})["mouth"][1]) == 1.0, "mouthOpen=1 이면 최대")

    ok("rotate(6.00deg)" in apply({"bodyLean": 1.0})["body"][1], "bodyLean=1 → 오른쪽으로 기운다")
    ok("rotate(-6.00deg)" in apply({"bodyLean": -1.0})["body"][1], "bodyLean=-1 → 왼쪽")
    ok("translateY(-8.0px)" in apply({"headY": 1.0})["head"][1],
       "headY=1 → 위로 (화면 좌표는 아래가 +)")

    # ── 범위 밖 입력에 안전하다 (Ch17 음량이 1 을 넘길 수 있다) ─────
    c = clamp({"mouthOpen": 1.7, "eyeOpen": -0.4, "bodyLean": -3, "headY": 9})
    ok(c["mouthOpen"] == 1.0 and c["eyeOpen"] == 0.0, "★ 1 을 넘거나 0 아래면 잘라낸다")
    ok(c["bodyLean"] == -1.0 and c["headY"] == 1.0, "±1 범위도 잘라낸다")
    ok(clamp({"tail": 1.0}) == DEFAULTS, "모르는 이름은 무시한다")
    ok(clamp(None) == DEFAULTS, "None 을 줘도 기본값")
    ok(apply({"mouthOpen": 99})["mouth"][1] == apply({"mouthOpen": 1.0})["mouth"][1],
       "범위 밖 값은 최대와 같은 변형을 낸다 — 입이 찢어지지 않는다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
