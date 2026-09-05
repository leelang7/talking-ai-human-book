# -*- coding: utf-8 -*-
"""
Ch23 §4·§6 — 끼어들기와 상태 기계

**끼어들 수 없는 대화는 대화가 아니라 안내방송이다.**

이 파일이 지키는 것 넷 (§4):

    ① 마이크 상시 개방      말하는 동안 마이크를 끄면 끼어들 수 없다
    ② 자기 목소리 차단      스피커 소리가 마이크로 들어오면 자기 말에 끼어든다
    ③ 진행 중 작업 취소     LLM 스트림 · TTS · **립싱크 층** 을 함께 멈춘다
    ④ 부드러운 멈춤        100ms 페이드아웃. 뚝 끊지 않는다

③ 의 **립싱크 층** 이 아바타 특유의 요구다. 소리만 멈추고 입을 그대로 두면
*아무 소리도 안 나면서 혼자 떠드는 얼굴* 이 된다. 소리만 멈추는 것보다 나쁘다.

    python bargein.py
"""
BACKCHANNEL_MS = 500        # §4 — 이보다 짧으면 맞장구로 본다
FADE_MS = 100               # §4 — 뚝 끊지 않는다
ECHO_CEILING = 0.35         # 스피커 되울림은 대개 이보다 작다

# 끼어들기 한 번에 함께 취소되어야 하는 것들.
# **lipsync 가 빠지면 입만 계속 움직인다.** 그래서 목록으로 두고 테스트한다.
CANCEL_ON_BARGEIN = ("tts_playback", "lipsync", "llm_stream", "pending_render")

# §6 — 상태 기계. 말하는 중 → 듣는 중 이 끼어들기다.
STATES = ("idle", "listening", "thinking", "speaking")
ALLOWED = {
    "idle": ("listening",),
    "listening": ("thinking", "idle"),
    "thinking": ("speaking", "listening", "idle"),   # listening = 생각 중 끼어들기
    "speaking": ("listening", "idle"),               # listening = 발화 중 끼어들기
}
BARGE_IN = (("speaking", "listening"), ("thinking", "listening"))


def is_backchannel(utter_ms: float) -> bool:
    """맞장구인가. "네", "음—", "아하" 는 끼어들기가 아니다 (§4).

    목록으로 걸러도 되지만, **0.5초 미만을 빼는 것만으로 상당히 개선된다.**
    """
    return utter_ms < BACKCHANNEL_MS


def is_self_echo(level: float, speaking: bool) -> bool:
    """내 스피커 소리가 마이크로 돌아온 것인가 (§4 ②).

    아바타가 말하는 중이고 소리가 작으면 되울림으로 본다. 이게 없으면
    **아바타가 자기 말에 끼어들어 첫 문장에서 멈춘다.**
    """
    return speaking and level < ECHO_CEILING


def should_interrupt(state: str, utter_ms: float, level: float = 1.0) -> bool:
    """지금 이 발화가 끼어들기인가."""
    if (state, "listening") not in BARGE_IN:
        return False
    if is_self_echo(level, state == "speaking"):
        return False
    return not is_backchannel(utter_ms)


def can(src: str, dst: str) -> bool:
    return dst in ALLOWED.get(src, ())


class Session:
    """한 대화의 상태와 진행 중 작업. 끼어들기가 오면 전부 취소한다."""

    def __init__(self):
        self.state = "idle"
        self.running = set()
        self.cancelled = []
        self.mic_open = True            # ① 항상 열려 있다
        self.fade_ms = 0

    def to(self, dst):
        if not can(self.state, dst):
            raise ValueError(f"{self.state} → {dst} 는 허용되지 않는 전이다")
        self.state = dst
        return self

    def start_speaking(self):
        self.to("speaking")
        self.running = set(CANCEL_ON_BARGEIN)
        self.fade_ms = 0
        return self

    def heard(self, utter_ms, level=1.0):
        """사용자 발화 하나를 처리한다. 반환값은 무엇을 했는가."""
        if not should_interrupt(self.state, utter_ms, level):
            reason = ("echo" if is_self_echo(level, self.state == "speaking")
                      else "backchannel" if is_backchannel(utter_ms)
                      else "not_speaking")
            return {"interrupted": False, "reason": reason,
                    "cancelled": (), "state": self.state}

        self.cancelled = sorted(self.running)
        self.running = set()
        self.fade_ms = FADE_MS          # ④ 뚝 끊지 않는다
        self.to("listening")
        return {"interrupted": True, "reason": "barge_in",
                "cancelled": tuple(self.cancelled), "state": self.state}


def _demo():
    print()
    print("  끼어들기 한 번에 함께 멈추는 것:", " · ".join(CANCEL_ON_BARGEIN))
    print()
    for label, utter, level in (("맞장구 \"음—\"", 300, 1.0),
                                ("자기 목소리 되울림", 900, 0.2),
                                ("진짜 끼어들기", 900, 1.0)):
        s = Session().to("listening").to("thinking").start_speaking()
        r = s.heard(utter, level)
        mark = "멈춤" if r["interrupted"] else "무시"
        print(f"  {label:18} {utter:>4}ms lv={level:<4} → {mark:4} ({r['reason']})")
        if r["interrupted"]:
            print(f"    취소: {' · '.join(r['cancelled'])} · 페이드 {s.fade_ms}ms")
    print()
    print("  마이크는 세 경우 모두 열려 있다 — 닫으면 끼어들 수가 없다.")
    print()


if __name__ == "__main__":
    _demo()
