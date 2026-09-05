# -*- coding: utf-8 -*-
"""
Ch17 — 음량 구동 립싱크의 신호 처리부

브라우저 코드는 눈으로 봐야 하지만, **입을 여는 계산 자체는 순수 함수**라
테스트할 수 있다. 이 모듈이 그 부분만 떼어낸 것이다.

날것의 음량은 못 쓴다. 네 처리를 거친다(Ch17 §4).

    ① 비대칭 평활화   여는 쪽 빠르게, 닫는 쪽 느리게 — 실제 입의 물리와 같다
    ② 바닥 자르기     무음의 미세 잡음을 0 으로. 없으면 조용할 때 입이 달싹인다
    ③ 동적 천장       최근 구간 최대값으로 정규화. 파일마다 음량이 다르다
    ④ 곡선            제곱근. 작은 소리에서도 입이 조금 열려 생동감이 생긴다

실행:  python mouth.py            (합성 신호로 동작 시연)
       python test_mouth.py       (회귀 테스트)
"""
import math


class MouthDriver:
    """음량 → 입 벌림(0~1). 프레임마다 feed() 를 부른다."""

    # release 0.15 → 0.35: 실제 TTS 파일 넷에서 0.15 는 조용한 프레임의 50% 에 입이 열려
    # 있었다(Ch09 의 상한 35% 초과). 0.35 가 33% · 발화 끝→닫힘 7.5프레임(250ms).
    # 근거: _work/release_sweep.json
    def __init__(self, attack=0.6, release=0.35, floor=0.06,
                 ceil_decay=0.995, ceil_min=0.05, curve=0.5, noise_gate=0.02):
        self.attack, self.release = attack, release   # ① 여는/닫는 속도(비대칭)
        self.floor = floor                            # ② 상대 바닥(천장 대비)
        self.noise_gate = noise_gate                  # ②' **절대** 바닥 ← 아래 설명
        self.ceil_decay, self.ceil_min = ceil_decay, ceil_min   # ③ 동적 천장
        self.curve = curve                            # ④ 지수(0.5 = 제곱근)
        self.value = 0.0
        self._ceil = ceil_min

    @staticmethod
    def rms(samples):
        """파형 조각의 실효값. 정밀할 필요 없다 — 리듬만 맞으면 된다(Ch17 §2)."""
        if not samples:
            return 0.0
        return math.sqrt(sum(x * x for x in samples) / len(samples))

    def feed(self, level):
        """level: 0~1 정규화 전의 원시 음량(RMS 등)."""
        # ②' 절대 노이즈 게이트 — **정규화 전에** 먼저 건다.
        #
        #   동적 천장(③)만 두면 무음을 못 막는다. 조용한 구간에서는 천장도 함께
        #   내려가므로, 0.004 짜리 잡음이 천장 대비로는 '큰 소리'가 되어 버린다.
        #   회귀 테스트가 이 결함을 잡았다(무음 30프레임 후 입이 0.15 로 열림).
        #
        #   상대 기준과 절대 기준은 서로를 대신하지 못한다. 둘 다 필요하다.
        if level < self.noise_gate:
            k = self.release
            self.value += (0.0 - self.value) * k
            return max(0.0, self.value)

        # ③ 동적 천장 — 서서히 내려가며 새 최대값에 즉시 올라붙는다
        self._ceil = max(self.ceil_min, self._ceil * self.ceil_decay, level)
        x = level / self._ceil if self._ceil > 0 else 0.0

        # ② 바닥 자르기 — 임계 아래는 확실히 닫는다
        x = 0.0 if x < self.floor else (x - self.floor) / (1 - self.floor)

        # ④ 곡선 — 작은 소리에서도 입이 조금 열린다
        x = x ** self.curve if x > 0 else 0.0

        # ① 비대칭 평활화 — 열 때는 빠르게, 닫을 때는 느리게
        k = self.attack if x > self.value else self.release
        self.value += (x - self.value) * k
        return max(0.0, min(1.0, self.value))

    def close(self):
        """재생이 끝나면 반드시 닫는다. 반쯤 벌어진 채 굳는 것이 실패 24번."""
        self.value = 0.0
        return self.value


def mouth_shape(v, n=3):
    """입 벌림 값을 이미지 인덱스로. 늘리는 것보다 이미지 전환이 낫다(Ch17 §5)."""
    return min(n - 1, int(v * n))


def _demo():
    """무음 → 발화 → 무음 구간을 합성해 네 처리의 효과를 보여준다."""
    import random
    random.seed(7)
    frames = ([0.004] * 12                                   # 무음(잡음만)
              + [0.15 + 0.25 * abs(math.sin(i * 0.7)) for i in range(30)]   # 발화
              + [0.003] * 12)                                # 다시 무음
    raw_only, driven = MouthDriver(attack=1.0, release=1.0, floor=0.0, curve=1.0), MouthDriver()
    print("  프레임  원시음량   날것그대로   네처리적용   입모양")
    for i, lv in enumerate(frames):
        a, b = raw_only.feed(lv), driven.feed(lv)
        if i % 3:
            continue
        bar = "█" * int(b * 22)
        print(f"  {i:>5}  {lv:>7.3f}   {a:>9.2f}   {b:>9.2f}   {bar}")
    print("\n  ▸ 무음 구간에서 '네처리'는 0 으로 닫힙니다 — 바닥 자르기(②)")
    print("  ▸ 발화 시작에서 빠르게 열리고 끝에서 천천히 닫힙니다 — 비대칭(①)")
    print("  ▸ 원시 음량이 0.4 를 안 넘어도 입은 끝까지 열립니다 — 동적 천장(③)\n")


if __name__ == "__main__":
    _demo()
