# -*- coding: utf-8 -*-
"""
Ch20 — 감정 태그 파서 + 제스처 함수

두 부분이 다 순수 함수라 브라우저 없이 검증된다.

  1) 태그 파서 — LLM 이 앞에 붙인 [감정][동작] 을 떼어낸다. **관대해야 한다.**
  2) 제스처   — (p, t) → 관절 채널. p=진행도(0~1), t=경과초.

설계의 핵심은 p 와 t 를 나눠 받는 것이다(Ch20 §5).
    반복 동작   → t 를 쓴다. 지속 시간과 무관하게 같은 속도로 떤다.
    한 번 왕복  → p 를 쓴다. sin(p*pi) 면 0→1→0 이라 저절로 돌아온다.

실행:  python gesture.py          (동작 13종을 표로)
       python test_gesture.py     (회귀 테스트)
"""
import math
import re

EMOS = ("greet", "happy", "excited", "think", "sad", "neutral")
ACTS = ("wave", "bow", "nod", "point", "clap", "cheer", "think", "shrug",
        "jumpingjack", "armcircle", "stretch", "twist", "squat", "none")

# 감정이 제스처의 크기와 빈도를 **동시에** 바꾼다 (Ch20 §6)
EMO = {
    "greet":   {"amp": 1.10, "gap": (0.5, 0.9)},
    "happy":   {"amp": 1.00, "gap": (0.5, 0.9)},
    "excited": {"amp": 1.35, "gap": (0.35, 0.6)},
    "neutral": {"amp": 0.80, "gap": (0.6, 1.1)},
    "think":   {"amp": 0.50, "gap": (1.0, 1.7)},
    "sad":     {"amp": 0.40, "gap": (1.2, 2.0)},
}

# 대화 제스처는 짧고, 운동은 반복을 보여줘야 하므로 길다 (Ch20 §6)
DUR = {"wave": 2.2, "bow": 1.7, "nod": 1.7, "point": 1.9, "clap": 2.0,
       "cheer": 1.9, "think": 2.3, "shrug": 1.5,
       "jumpingjack": 4.5, "armcircle": 4.5, "stretch": 4.0, "twist": 4.5, "squat": 4.5}

_sin, _cos, _pi = math.sin, math.cos, math.pi

ACT = {
    # 반복 → t
    "wave":  lambda p, t: {"ruz": 0.95, "rux": 0.10, "shz": 0.35,
                           "rly": 0.45 + _sin(t * 15) * 0.45, "tilt": 0.05},
    "nod":   lambda p, t: {"nod": 0.20 * _sin(t * 9)},
    "clap":  lambda p, t: {"ruz": 0.5, "rux": 0.35, "rly": 0.6 + _sin(t * 16) * 0.18,
                           "luz": 0.5, "lux": 0.35, "lly": 0.6 + _sin(t * 16 + _pi) * 0.18},
    # 한 번 왕복 → p (sin(p*pi) 는 양 끝이 0 이라 저절로 복귀한다)
    "bow":   lambda p, t: {"lean": 0.55 * _sin(p * _pi), "nod": 0.25 * _sin(p * _pi)},
    # 정지 자세
    "point": lambda p, t: {"rux": 0.85, "ruz": 0.15, "shz": 0.20, "rly": 0.05, "tilt": 0.04},
    "cheer": lambda p, t: {"ruz": 1.05, "rux": 0.05, "shz": 0.40,
                           "luz": 1.05, "lux": 0.05, "shzl": 0.40, "nod": -0.05},
    "think": lambda p, t: {"rux": 0.45, "ruz": 0.10, "rly": 1.20, "nod": 0.06, "tilt": 0.12},
    "shrug": lambda p, t: {"ruz": 0.45, "rux": 0.25, "shz": 0.25,
                           "luz": 0.45, "lux": 0.25, "shzl": 0.25, "tilt": 0.09, "nod": 0.03},
    # 운동 — 0~1 로 정규화한 s 를 전 관절에 곱한다
    "jumpingjack": lambda p, t: (lambda s: {"ruz": 1.45 * s, "rux": 0.05, "shz": 0.35 * s,
                                            "luz": 1.45 * s, "lux": 0.05, "shzl": 0.35 * s,
                                            "legL": 0.28 * s, "legR": 0.28 * s,
                                            "nod": 0.04 * s})((_sin(t * 6) + 1) / 2),
    "armcircle": lambda p, t: {"rux": 0.55 + 0.65 * _sin(t * 4.5),
                               "ruz": 0.80 + 0.55 * _cos(t * 4.5), "shz": 0.35,
                               "lux": 0.55 + 0.65 * _sin(t * 4.5 + _pi),
                               "luz": 0.80 + 0.55 * _cos(t * 4.5 + _pi), "shzl": 0.35},
    "stretch": lambda p, t: {"ruz": 1.5, "rux": 0.05, "shz": 0.45,
                             "luz": 1.5, "lux": 0.05, "shzl": 0.45,
                             "lean": 0.18 * _sin(t * 1.4), "twist": 0.12 * _sin(t * 1.4)},
    "twist": lambda p, t: {"twist": 0.45 * _sin(t * 3.5), "ruz": 0.5, "rux": 0.1,
                           "luz": 0.5, "lux": 0.1, "lean": 0.05},
    # 관절만으로는 안 된다 — drop 으로 루트를 실제로 내린다 (Ch20 §6+)
    "squat": lambda p, t: (lambda s: {"drop": 0.28 * s, "kneeL": 0.7 * s, "kneeR": 0.7 * s,
                                      "lean": 0.25 * s, "rux": 0.7 * s, "ruz": 0.25,
                                      "lux": 0.7 * s, "luz": 0.25})((1 - _cos(t * 3.2)) / 2),
}

FADE = 0.30          # 양 끝 페이드. 이 한 줄이 동작 13종의 시작·끝을 전부 처리한다


def envelope(elapsed, dur, fade=FADE):
    """시작 0.3초 동안 0→1, 끝 0.3초 동안 1→0. 모든 채널에 곱한다."""
    if dur <= 0:
        return 0.0
    return max(0.0, min(1.0, min(elapsed, dur - elapsed) / fade))


def pose(name, elapsed, amp=1.0):
    """동작 이름과 경과 시간 → 채널 딕셔너리(엔벨로프·감정 진폭 적용)."""
    if name not in ACT:
        return {}
    dur = DUR.get(name, 1.8)
    if elapsed >= dur:
        return {}
    env = envelope(elapsed, dur) * amp
    return {k: v * env for k, v in ACT[name](elapsed / dur, elapsed).items()}


_TAGS = re.compile(r"\s*\[(\w+)\]\s*")


def parse_tags(text, max_tags=2):
    """맨 앞 [감정][동작] 을 떼어낸다. **관대하게** (Ch20 §4).

    태그 없음 / 하나만 / 모르는 이름 / 셋 이상 / 문장 중간 — 전부 처리한다.
    최악의 경우에도 무표정으로 말은 하게 한다.
    """
    s, tags = (text or "").strip(), []
    while len(tags) < max_tags:
        m = _TAGS.match(s)
        if not m:
            break
        tags.append(m.group(1).lower())
        s = s[m.end():]
    emo = next((x for x in tags if x in EMOS), "neutral")
    act = next((x for x in tags if x in ACTS), "none")
    s = re.sub(r"\[[^\]]{1,20}\]", " ", s)          # 중간에 낀 것까지 제거
    return emo, act, re.sub(r"\s+", " ", s).strip()


def _demo():
    print(f"  {'동작':<12}{'지속':>5}  {'0.15초':>8}{'중간':>8}{'끝-0.15':>9}   특성")
    for n in ACT:
        d = DUR[n]
        a, b, c = (max(pose(n, x).values(), default=0, key=abs)
                   for x in (0.15, d / 2, d - 0.15))
        kind = "반복(t)" if n in ("wave", "nod", "clap", "jumpingjack", "armcircle",
                                 "twist", "squat", "stretch") else \
               "왕복(p)" if n == "bow" else "정지"
        print(f"  {n:<12}{d:>5.1f}  {a:>8.2f}{b:>8.2f}{c:>9.2f}   {kind}")
    print("\n  ▸ 양 끝(0.15초) 값이 중간보다 작습니다 — 엔벨로프가 접습니다")
    print("  ▸ 'bow' 는 p 를 쓰므로 별도 복귀 코드 없이 저절로 돌아옵니다\n")


if __name__ == "__main__":
    _demo()
