# -*- coding: utf-8 -*-
"""
Ch16 §5 — 파츠를 움직이는 네 개의 손잡이

`split_parts.py` 는 그림을 파츠로 **쪼개는** 쪽이다. 이 파일은 쪼갠 파츠를
**움직이는** 쪽이다. Ch16 본문이 부르는 이름 그대로 넷이다.

    eyeOpen    0~1   눈. 0 이면 감고 1 이면 뜬다
    mouthOpen  0~1   입. 0 이면 다물고 1 이면 최대로 벌린다
    bodyLean  -1~1   몸의 기울기
    headY     -1~1   고개의 위아래

값 넷을 받아 파츠별 변형(CSS transform 에 그대로 넣을 수 있는 형태)을 돌려준다.
**기준점(transform-origin)은 SPEC 에서 가져온다** — 눈은 중앙, 입은 위,
몸통은 바닥. 그 이유는 Ch16 §3 과 도판 F6 에 있다.

    python params.py       값 몇 개를 넣어 변형을 찍어 본다
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split_parts import SPEC  # noqa: E402

RANGES = {"eyeOpen": (0.0, 1.0), "mouthOpen": (0.0, 1.0),
          "bodyLean": (-1.0, 1.0), "headY": (-1.0, 1.0)}
DEFAULTS = {"eyeOpen": 1.0, "mouthOpen": 0.0, "bodyLean": 0.0, "headY": 0.0}

EYE_MIN_SCALE = 0.06        # 완전히 감아도 0 이 아니다 — 0 이면 눈이 '사라진다'
MOUTH_MIN_SCALE = 0.25      # 다문 입도 두께가 있다
LEAN_DEG = 6.0              # bodyLean = ±1 일 때 몸통이 기우는 각
HEAD_PX = 8.0               # headY = ±1 일 때 머리가 오르내리는 픽셀 (512 기준)


def clamp(params: dict) -> dict:
    """범위 밖 값을 잘라낸다. 음량 구동(Ch17)이 1 을 넘겨도 입이 찢어지지 않는다."""
    out = dict(DEFAULTS)
    for k, v in (params or {}).items():
        if k not in RANGES:
            continue
        lo, hi = RANGES[k]
        out[k] = min(hi, max(lo, float(v)))
    return out


def apply(params: dict) -> dict:
    """파츠별 변형. 각 항목은 (transform-origin, transform) 이다.

    **기준점이 파츠마다 다르다는 것이 Ch16 의 핵심이고, 여기서 SPEC 이 그것을 준다.**
    같은 세로 축소를 눈은 중앙 기준으로, 입은 위 기준으로 한다.
    """
    p = clamp(params)
    eye_s = EYE_MIN_SCALE + (1.0 - EYE_MIN_SCALE) * p["eyeOpen"]
    mouth_s = MOUTH_MIN_SCALE + (1.0 - MOUTH_MIN_SCALE) * p["mouthOpen"]
    return {
        "eyeL":  (SPEC["eyeL"]["origin"],  f"scaleY({eye_s:.3f})"),
        "eyeR":  (SPEC["eyeR"]["origin"],  f"scaleY({eye_s:.3f})"),
        "mouth": (SPEC["mouth"]["origin"], f"scaleY({mouth_s:.3f})"),
        "body":  ("center bottom",         f"rotate({p['bodyLean'] * LEAN_DEG:.2f}deg)"),
        "head":  ("center center",         f"translateY({-p['headY'] * HEAD_PX:.1f}px)"),
    }


def _demo():
    print()
    for label, prm in (("기본", {}),
                       ("깜빡임 중간", {"eyeOpen": 0.3}),
                       ("입 벌림", {"mouthOpen": 0.8}),
                       ("범위 밖 입력", {"mouthOpen": 1.7, "bodyLean": -3})):
        t = apply(prm)
        print(f"  {label:8}", "  ".join(f"{k}={v[1]}" for k, v in t.items()
                                       if k in ("eyeL", "mouth", "body")))
    print()
    print("  기준점:", {k: v[0] for k, v in apply({}).items()})
    print("  눈은 중앙 · 입은 위 · 몸통은 바닥 — SPEC 에서 온 값이다 (Ch16 §3 · 도판 F6)")
    print()


if __name__ == "__main__":
    _demo()
