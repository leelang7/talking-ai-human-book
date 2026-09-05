# -*- coding: utf-8 -*-
"""
Ch23 §2 — 발화 종료 판정

타이핑에는 엔터가 있지만 음성에는 없다. **언제 말이 끝났는지를 정해야 한다.**

여기 있는 것은 에너지 기반 VAD 다. 조용한 사무실이면 이걸로 충분하고,
전시장·매장처럼 배경 소음이 있는 곳이면 신경망 VAD 로 가야 한다(§2).
**임계값 튜닝으로 버티려다 실패하는 것이 전형적인 경우다.**

세 상수가 이 파일의 전부다.

    침묵 800ms      이보다 짧으면 오작동, 길면 지연 예산을 먹는다
    최소 발화 200ms  기침·문 닫는 소리로 STT 를 돌리지 않는다
    보정 1초        시작할 때 주변 소음을 재서 기준을 잡는다

    python vad.py     조용한 방과 시끄러운 전시장을 나란히 돌린다
"""
FRAME_MS = 20
SILENCE_MS = 800            # §2 — 700ms~1초 사이가 무난하다
MIN_UTTER_MS = 200          # §2 — 이하는 발화로 치지 않는다
CALIBRATE_MS = 1000
NOISE_MARGIN = 3.0          # 주변 소음의 몇 배를 말소리로 볼 것인가
FLOOR = 0.01                # 완전한 무음실에서도 이 아래로는 안 내린다

START, END = "start", "end"


class Vad:
    """프레임마다 음량을 넣으면 발화 시작·끝 이벤트를 돌려준다."""

    def __init__(self, frame_ms=FRAME_MS, silence_ms=SILENCE_MS,
                 min_utter_ms=MIN_UTTER_MS, threshold=None):
        self.frame_ms = frame_ms
        self.silence_frames = max(1, round(silence_ms / frame_ms))
        self.min_utter_frames = max(1, round(min_utter_ms / frame_ms))
        self.threshold = FLOOR if threshold is None else threshold
        self.calibrated = threshold is not None
        self._voiced = 0
        self._quiet = 0
        self._in_speech = False

    # ── 보정 ────────────────────────────────────────────────────────
    def calibrate(self, ambient_levels):
        """주변 소음 몇 초를 듣고 임계값을 정한다 (§2).

        고정 임계값은 조용한 방과 시끄러운 전시장 중 한쪽에서 반드시 틀린다.
        **환경을 코드에 박지 말고 시작할 때 재라.**
        """
        if not ambient_levels:
            return self.threshold
        # 보정 창에 말이 섞이면 임계가 말소리보다 높아져 **아무것도 안 잡힌다** —
        # 실제 녹음 넷(measure.py)이 전부 첫 1초부터 말이라 임계 0.23~0.54 가 나왔고,
        # 네 파일 모두 발화 0개였다. 그래서 창에서 가장 조용한 30% 만 주변 소음으로 본다.
        quiet = sorted(ambient_levels)[:max(1, len(ambient_levels) * 3 // 10)]
        n = len(quiet)
        mean = sum(quiet) / n
        var = sum((x - mean) ** 2 for x in quiet) / n
        self.threshold = max(FLOOR, mean * NOISE_MARGIN + var ** 0.5)
        self.calibrated = True
        return self.threshold

    # ── 판정 ────────────────────────────────────────────────────────
    def feed(self, level):
        """한 프레임. 이벤트가 생기면 (이벤트, 발화길이ms) 를 반환한다."""
        loud = level >= self.threshold

        if not self._in_speech:
            self._voiced = self._voiced + 1 if loud else 0
            if self._voiced >= self.min_utter_frames:
                self._in_speech = True
                self._quiet = 0
                return (START, self._voiced * self.frame_ms)
            return None

        if loud:
            self._voiced += 1
            self._quiet = 0
            return None

        self._quiet += 1
        if self._quiet >= self.silence_frames:
            # 침묵 구간은 발화 길이에서 뺀다 — 말한 시간만 센다
            dur = self._voiced * self.frame_ms
            self._in_speech, self._voiced, self._quiet = False, 0, 0
            return (END, dur)
        return None

    def finish(self):
        """스트림이 끝났다 — 발화 중이면 침묵을 기다리지 않고 END 를 낸다.

        실측(measure.py)에서 침묵 1000ms 설정일 때 마지막 발화가 파일 끝에서 닫히지
        않았다. 마이크가 꺼지거나 연결이 끊기면 같은 일이 난다. 끝은 끝이다.
        """
        if not self._in_speech:
            return None
        dur = self._voiced * self.frame_ms
        self._in_speech, self._voiced, self._quiet = False, 0, 0
        return (END, dur)

    def reset(self):
        self._voiced = self._quiet = 0
        self._in_speech = False


def run(levels, **kw):
    """음량 배열을 통째로 넣고 이벤트 목록을 받는다. 테스트용."""
    v = Vad(**kw)
    out = []
    for i, lv in enumerate(levels):
        e = v.feed(lv)
        if e:
            out.append((i * v.frame_ms, *e))
    e = v.finish()
    if e:
        out.append((len(levels) * v.frame_ms, *e))
    return out


def frames(pattern, frame_ms=FRAME_MS):
    """('loud', 300), ('quiet', 900) 같은 구간 목록을 프레임 음량으로 편다."""
    LEVEL = {"loud": 0.5, "quiet": 0.002, "noise": 0.05}
    out = []
    for kind, ms in pattern:
        out += [LEVEL[kind]] * round(ms / frame_ms)
    return out


def _demo():
    print()
    quiet_room = [0.002, 0.003, 0.002, 0.004, 0.003]
    hall = [0.05, 0.07, 0.04, 0.09, 0.06]
    for name, amb in (("조용한 사무실", quiet_room), ("시끄러운 전시장", hall)):
        v = Vad()
        t = v.calibrate(amb)
        print(f"  {name:12} 주변 소음 평균 {sum(amb)/len(amb):.3f} → 임계값 {t:.3f}")
    print()

    seq = [("quiet", 200), ("loud", 120), ("quiet", 300),      # 기침 — 무시돼야 한다
           ("loud", 900), ("quiet", 900),                       # 진짜 발화
           ("loud", 400), ("quiet", 400), ("loud", 300), ("quiet", 900)]
    print("  구간:", " · ".join(f"{k}{ms}" for k, ms in seq))
    for ms, ev, dur in run(frames(seq), threshold=0.1):
        print(f"    {ms:>5}ms  {ev:5}  발화 {dur}ms")
    print()
    print("  120ms 기침은 이벤트를 만들지 않았고, 400ms 침묵은 발화를 끊지 않았다.")
    print()


if __name__ == "__main__":
    _demo()
