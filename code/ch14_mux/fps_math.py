# -*- coding: utf-8 -*-
"""
Ch14 — fps 불일치가 만드는 어긋남 계산

이 파일은 **순수 함수만** 담는다. ffmpeg 도 파일도 필요 없다.
Ch14 §2 의 "3.3%" 와 "0.33초" 가 어디서 나온 숫자인지가 여기 전부다.

핵심은 어긋남이 **영상 길이에 비례해 쌓인다** 는 것이다. 전체가 균일하게
밀리는 것이 아니라 뒤로 갈수록 벌어진다 — 그것이 이 문제의 지문이다.

    python fps_math.py          표를 출력한다
"""
from fractions import Fraction

# 파이프라인의 단일 상수와 같은 값 (code/_lib/media.py 의 FPS)
NTSC = Fraction(30000, 1001)          # 29.97
NOTICEABLE = 0.100                    # 사람이 입-소리 어긋남을 인식하는 경계(초)


def drift_ratio(made, play) -> float:
    """`made` fps 로 뽑은 영상을 `play` fps 로 재생할 때의 어긋남 비율.

    부호는 빠르게/느리게의 방향일 뿐이고, 보이는 것은 크기다.
    """
    made, play = float(made), float(play)
    if made <= 0 or play <= 0:
        raise ValueError("fps 는 양수여야 한다")
    return abs(play / made - 1.0)


def drift_seconds(made, play, duration: float) -> float:
    """길이 `duration` 초 영상의 끝에서 벌어지는 어긋남(초)."""
    return drift_ratio(made, play) * float(duration)


def noticeable_after(made, play, threshold: float = NOTICEABLE) -> float:
    """어긋남이 `threshold` 를 넘기까지 걸리는 영상 길이(초).

    **이 함수가 이 파일의 요점이다.** 어긋남 비율만 보면 30fps 는 0.1% 라
    무해해 보이지만, 100초가 지나면 경계를 넘는다. 짧은 테스트 클립을
    통과하고 실전 길이에서 처음 터진다 — 29 보다 30 이 위험한 이유다.
    """
    r = drift_ratio(made, play)
    return float("inf") if r == 0 else threshold / r


# NTSC 계열의 표기값 → 진짜 값.
#
#   **29.97 은 30000/1001 이 아니다.** 30000/1001 = 29.97002997… 이고,
#   둘의 차이는 백만분의 1 이다. 실무에서 문제를 일으키는 크기는 아니지만,
#   float 29.97 에서 30000/1001 을 되찾을 방법은 없다 — 2997/100 이 훨씬 가깝다.
#   그래서 **되돌리지 않고 표로 안다.** 반올림된 표기값은 원본을 복원하지 못한다.
NTSC_FAMILY = {
    Fraction(2997, 100): Fraction(30000, 1001),      # 29.97
    Fraction(5994, 100): Fraction(60000, 1001),      # 59.94
    Fraction(23976, 1000): Fraction(24000, 1001),    # 23.976
    Fraction(11988, 1000): Fraction(12000, 1001),    # 11.988
}


def as_fraction(fps) -> Fraction:
    """fps 를 분수로. 정수를 그대로 넘기면 터지는 라이브러리가 있다(부록 F 15번).

    표기값(29.97)은 NTSC_FAMILY 표를 통해 진짜 값(30000/1001)으로 바꾼다.
    """
    if isinstance(fps, Fraction):
        return NTSC_FAMILY.get(fps, fps)
    if isinstance(fps, int):
        return Fraction(fps, 1)
    if isinstance(fps, str) and "/" in fps:
        return Fraction(fps)
    f = Fraction(float(fps)).limit_denominator(1001)
    return NTSC_FAMILY.get(f, f)


def ffmpeg_rate(fps) -> str:
    """ffmpeg 에 넘길 문자열. `29.97` 이 아니라 `30000/1001` 로 준다."""
    f = as_fraction(fps)
    return f"{f.numerator}/{f.denominator}"


def report(play=NTSC, candidates=(29, 30, 24, 25), lengths=(10, 60, 300)):
    """뽑은 fps 별로 어긋남을 표로. 도판 F10 이 이 함수의 값을 그린다."""
    rows = []
    for made in candidates:
        r = drift_ratio(made, play)
        rows.append({
            "made": made,
            "ratio_pct": r * 100,
            "noticeable_at": noticeable_after(made, play),
            "at": {L: drift_seconds(made, play, L) for L in lengths},
        })
    return rows


def _demo():
    print()
    print(f"  재생 fps = {ffmpeg_rate(NTSC)} ({float(NTSC):.3f})\n")
    L = (10, 60, 300)
    print("  뽑은fps   어긋남      " + "".join(f"{x}초 영상  ".rjust(12) for x in L)
          + "  100ms 넘는 시점")
    print("  " + "─" * 74)
    for row in report(lengths=L):
        cells = "".join(f"{row['at'][x]:>9.2f}초  " for x in L)
        print(f"  {row['made']:>6}   {row['ratio_pct']:>6.2f}%   {cells}"
              f"  {row['noticeable_at']:>7.0f}초")
    print()
    print("  어긋남은 길이에 비례해 쌓인다. 짧은 클립에서 멀쩡한 것은 검증이 아니다.")
    print()


if __name__ == "__main__":
    _demo()
