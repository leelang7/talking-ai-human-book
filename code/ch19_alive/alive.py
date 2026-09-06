# -*- coding: utf-8 -*-
"""
Ch19 — 생명감의 계산부 (깜빡임 · 호흡 · 미세 움직임 · 시선)

3D 렌더는 눈으로 봐야 하지만, **언제 얼마나 움직일지 정하는 계산은 순수 함수**다.
그 부분만 떼어내면 테스트할 수 있고, 브라우저 없이 값을 검증할 수 있다.

이 모듈이 지키는 것:
    · 규칙적인 것은 죽어 보인다 — 깜빡임 주기는 난수(2~5초)
    · 진폭은 믿기 어려울 만큼 작다 — 호흡 0.012 라디안(약 0.7도)
    · 진동수(rad/s) 여섯의 공통 주기가 길어야 한다 — 0.4·0.45·0.6·0.7·0.9·1.2 → 약 126초

실행:  python alive.py            (10초치 값을 뽑아 본다)
       python test_alive.py       (회귀 테스트)
"""
import math
import random

# 미세 움직임의 여섯 진동수(rad/s). 최대공약수 0.05 → 공통 주기 2π/0.05 ≈ 126초라 겹친 파형이 오래 반복되지 않는다.
PERIODS = {"hips_y": 0.40, "neck_x": 0.45, "head_x": 0.60,
           "neck_y": 0.70, "head_y": 0.90, "spine_x": 1.20}
AMPS = {"hips_y": 0.05, "neck_x": 0.04, "head_x": 0.02,
        "neck_y": 0.05, "head_y": 0.03, "spine_x": 0.012}   # 라디안


class Blink:
    """깜빡임 — 난수 주기 + 0.3초 사인 반파장.

    사인 반파장을 쓰는 이유는 **양 끝이 정확히 0** 이라 이음매가 없기 때문이다.
    선형으로 오르내리면 시작과 끝에서 각이 지고, 그것이 눈에 띈다.
    """

    WIDTH = 0.30                      # 감았다 뜨는 데 걸리는 시간

    # 문헌: 쉴 때 약 17회/분, 대화 중 약 26회/분 (Bentivoglio 1997 등 — _work/measure.json).
    # 2~5초 균등이면 쉴 때 16회/분으로 맞는데, 말할 때 0.8배는 20회/분에 그쳤다 → 0.65배.
    # 이중 깜빡임(§2 "10~15%")은 본문에만 있고 코드에 없었다 → double 확률 추가.
    SPEAK_FACTOR = 0.65
    def __init__(self, lo=2.0, hi=5.0, rng=None, double=0.12):
        self.lo, self.hi = lo, hi
        self.rng = rng or random.Random()
        self.t = 0.0
        self.double = double
        self.next = self.rng.uniform(lo, hi)

    def step(self, dt, speaking=False):
        """반환: 0(뜸) ~ 1(감음)."""
        self.t += dt
        half = self.WIDTH / 2
        v = 0.0
        if self.next - half <= self.t <= self.next + half:
            p = (self.t - (self.next - half)) / self.WIDTH
            v = math.sin(p * math.pi)
        if self.t > self.next + half:
            if self.rng.random() < self.double:
                gap = self.rng.uniform(0.25, 0.45)   # 이중 깜빡임 — 바로 한 번 더
            else:
                gap = self.rng.uniform(self.lo, self.hi)
                if speaking:
                    gap *= self.SPEAK_FACTOR          # 말할 때는 더 자주 깜빡인다
            self.next = self.t + gap
        return v


def breath(t, amp=AMPS["spine_x"], period=PERIODS["spine_x"]):
    """호흡 — 느린 사인 한 줄. 진폭이 0.012 라디안(약 0.7도)이다."""
    return math.sin(t * period) * amp


def micro(t):
    """미세 움직임 — 여섯 채널을 한 번에. 각 채널은 (진동수, 진폭)이 다르다."""
    return {k: math.sin(t * PERIODS[k]) * AMPS[k] for k in PERIODS}


def expr_level(cur, speaking, dt, k=3.0):
    """감정 표정 강도 — 말할 때 0.7, 대기 0.12. 완전히 0으로 내리지 않는다.

    대기 중에도 표정이 남아 있어야 '감정이 남아 있는 얼굴'이 된다.
    """
    target = 0.7 if speaking else 0.12
    return cur + (target - cur) * min(1.0, dt * k)


def gaze(t, speaking, rng=None):
    """시선 — 기본은 카메라, 가끔 짧게 돌린다. 말할 때 더 자주 돌린다."""
    period = 4.0 if speaking else 7.0
    phase = (t % period) / period
    if phase < 0.12:                                  # 짧게 곁눈질
        off = math.sin(phase / 0.12 * math.pi)
        return {"x": 0.25 * off, "head_follow": 0.35 * off}
    return {"x": 0.0, "head_follow": 0.0}


def _demo():
    rng = random.Random(3)
    b = Blink(rng=rng)
    t, dt, lvl = 0.0, 1 / 30, 0.0
    print("   t(초)  깜빡임  호흡(rad)  목x(rad)   표정")
    # ★ 프레임을 세면 안 된다 — 0.3초 폭이라 한 번의 깜빡임이 여러 프레임에 걸린다.
    #   상승 엣지(닫힘 → 열림 전환)만 센다.
    times, prev = [], 0.0
    while t < 10:
        v = b.step(dt)
        lvl = expr_level(lvl, speaking=(3 < t < 7), dt=dt)
        if prev < 0.5 <= v:
            times.append(round(t, 1))
        prev = v
        if abs(t * 10 - round(t * 10)) < 1e-6 and round(t * 10) % 10 == 0:
            m = micro(t)
            print(f"  {t:>5.1f}  {v:>6.2f}  {breath(t):>9.4f}  {m['neck_x']:>8.4f}  {lvl:>5.2f}")
        t += dt
    print()
    print(f"  10초 동안 깜빡임 {len(times)}회 — {times}")
    gaps = [round(b - a, 1) for a, b in zip(times, times[1:])]
    print(f"  간격 {gaps} 초 — 규칙적이지 않다는 것이 핵심입니다")
    print("  ▸ 호흡 진폭이 0.012 라디안(0.7도)입니다. 안 보이지만 끄면 압니다.\n")


if __name__ == "__main__":
    _demo()
