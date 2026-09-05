# -*- coding: utf-8 -*-
"""
Ch26 — 멀티 아바타 엔진의 뼈대

마피아 · 추리극 · 방탈출은 규칙이 완전히 다른데 **뼈대는 거의 같다.**
진행자가 순서를 정하고, 각자에게 보여줄 것을 분배하고, 페이즈를 넘긴다.

이 파일에서 가장 중요한 것은 `brief()` **하나뿐이라는 사실** 이다.
컨텍스트 조립이 여러 군데로 흩어지면 어느 한 곳에서 비밀이 새고,
그것을 찾을 수 없다. **누출은 항상 "한 군데를 빠뜨려서" 생긴다** (§3).

    python engine.py      정상 브리핑과 새는 브리핑을 나란히 검사
"""
from dataclasses import dataclass, field

LOG_LINES = 16          # §3 ⑤ — 전부 넣으면 토큰이 폭발하고 적으면 맥락이 끊긴다

STANCE = {
    "culprit": "너는 범인이다. 들키지 않는 것이 목표다. 알리바이를 지키되 과하게 우기지 마라.",
    "innocent": "너는 결백하다. 범인을 찾는 것이 목표다. 아는 것을 성실히 말하라.",
    "narrator": "너는 진행자다. 아직 공개되지 않은 것을 절대 먼저 말하지 마라.",
}


@dataclass
class Character:
    name: str
    job: str
    secret: str                      # 이 캐릭터만 아는 것
    alibi: str
    role: str = "innocent"


@dataclass
class Scene:
    outline: str                                     # ① 모두가 아는 공개 정보
    clues: list = field(default_factory=list)        # (단서, 공개됐는가)
    log: list = field(default_factory=list)          # 발언 로그


def brief(scene: Scene, cast: list, who: str, lines: int = LOG_LINES) -> str:
    """`who` 가 볼 컨텍스트를 조립한다. **이 함수 하나만 쓴다.**

    다섯 조각 (§3) —
      ① 사건 개요   ② 본인 정보   ③ 입장   ④ 공개된 단서   ⑤ 최근 발언
    """
    me = next(c for c in cast if c.name == who)
    others = [c for c in cast if c.name != who]

    parts = [
        f"[사건] {scene.outline}",
        f"[너] {me.name} · {me.job}",
        f"[너만 아는 것] {me.secret}",
        f"[알리바이] {me.alibi}",
        f"[입장] {STANCE[me.role]}",
        # ④ **공개된 것만.** 아직 안 나온 단서는 넣지 않는다.
        "[드러난 단서] " + (" / ".join(c for c, shown in scene.clues if shown) or "아직 없음"),
        # 다른 인물은 이름과 직업까지만. 비밀도 역할도 넘기지 않는다.
        "[같이 있는 사람] " + ", ".join(f"{c.name}({c.job})" for c in others),
        "[최근 발언]\n" + "\n".join(scene.log[-lines:]),
    ]
    return "\n".join(parts)


def brief_leaky(scene: Scene, cast: list, who: str, lines: int = LOG_LINES) -> str:
    """**일부러 한 군데를 빠뜨린 버전.** 무엇이 새는지 보여주기 위한 것이다.

    다른 인물 소개에 역할과 비밀을 같이 넣었다. 딱 한 줄 차이이고,
    실제로 이렇게 새는 경우가 대부분이다 — 편하니까 통째로 넘긴 것이다.
    """
    base = brief(scene, cast, who, lines)
    others = [c for c in cast if c.name != who]
    return base.replace(
        "[같이 있는 사람] " + ", ".join(f"{c.name}({c.job})" for c in others),
        "[같이 있는 사람] " + ", ".join(
            f"{c.name}({c.job}, {c.role}, {c.secret})" for c in others))


def leak_scan(scene: Scene, cast: list, builder=brief) -> list:
    """모든 캐릭터의 브리핑을 만들어 **남의 비밀이 섞였는지** 훑는다 (§3).

    §3 은 "시민에게 마피아가 누구냐고 반복해 물어 정답률을 보라" 고 한다.
    그건 LLM 호출이 필요하고 통계가 필요하다. **문자열 검사가 먼저다** —
    컨텍스트에 아예 없으면 물어볼 필요도 없다.
    """
    found = []
    for viewer in cast:
        text = builder(scene, cast, viewer.name)
        for other in cast:
            if other.name == viewer.name:
                continue
            if other.secret and other.secret in text:
                found.append((viewer.name, other.name, "비밀"))
            if other.role != "innocent" and other.role in text:
                found.append((viewer.name, other.name, "역할"))
    return found


def hidden_clue_leak(scene: Scene, cast: list, builder=brief) -> list:
    """아직 공개되지 않은 단서가 브리핑에 들어갔는가 (§3 ④)."""
    out = []
    for viewer in cast:
        text = builder(scene, cast, viewer.name)
        for clue, shown in scene.clues:
            if not shown and clue in text:
                out.append((viewer.name, clue))
    return out


# ── 진행자 — LLM 이 아니라 코드다 (§2) ────────────────────────────────
PHASES = ("brief", "discuss", "vote", "reveal")


class Orchestrator:
    """순서 · 분배 · 페이즈. **규칙 진행은 결정론적이어야 한다** (§2)."""

    def __init__(self, cast, phases=PHASES, max_silence=8):
        self.cast = cast
        self.phases = phases
        self.phase = phases[0]
        self.turn = 0
        self.calls = []                 # 누구를 LLM 으로 불렀는가
        self.max_silence = max_silence
        self.last_spoke = {c.name: -1 for c in cast}

    # 굶주림 방지 — turns.py 실험에서 '이름 지목 우선' 만 두면 여섯 중 한 명이 54턴을
    # 침묵했다(점유율 31% vs 8%). §4 가 말한 "아직 말하지 않은 캐릭터" 규칙이 코드에 없었다.
    MAX_SILENCE = 8

    def next_speaker(self, mentioned=None, user_pick=None):
        """실용적인 조합 — 사용자 지목 > 굶주린 사람 > 이름 불린 사람 > 순서 (§4)."""
        names = [c.name for c in self.cast]
        if user_pick in names:
            return self._pick(user_pick)
        if self.max_silence is not None:
            starving = [n for n in names if self.turn - self.last_spoke[n] > self.max_silence]
            if starving:
                return self._pick(starving[0])
        if mentioned in names:          # 직전에 이름이 불린 사람이 답한다
            return self._pick(mentioned)
        return self._pick(names[self.turn % len(names)])

    def _pick(self, who):
        self.last_spoke[who] = self.turn
        return who

    def advance(self):
        i = self.phases.index(self.phase)
        self.phase = self.phases[min(i + 1, len(self.phases) - 1)]
        return self.phase

    def speakers_this_turn(self, speaker):
        """**말하지 않는 캐릭터는 부르지 않는다** (§5).

        토론 페이즈에서는 한 명만 말한다. 투표에서는 전원이 낸다.
        """
        if self.phase == "vote":
            return [c.name for c in self.cast]
        if self.phase in ("brief", "reveal"):
            return []                   # 정형 멘트는 템플릿이다 — LLM 을 안 쓴다
        return [speaker]


# ── 작업별 모델·온도·토큰 (§5) ───────────────────────────────────────
JOBS = {
    "line":     {"model": "light", "temp": 0.8, "max_tokens": 150},
    "reason":   {"model": "strong", "temp": 0.4, "max_tokens": 150},
    "vote":     {"model": "strong", "temp": 0.2, "max_tokens": 100},
    "scenario": {"model": "strong", "temp": 1.0, "max_tokens": 850},
}
TEMPLATED = ("clue_notice", "pick_notice", "phase_banner")


def route(job: str) -> dict:
    """LLM 을 안 쓰는 자리를 먼저 거른다 (§5)."""
    if job in TEMPLATED:
        return {"model": None, "why": "정형 멘트 — 매번 생성하면 느리고 틀릴 수 있다"}
    return JOBS[job]


def _demo():
    cast = [Character("민서", "조카", "유언장을 미리 봤다", "서재에 있었다", "culprit"),
            Character("도윤", "집사", "금고 비밀번호를 안다", "주방에 있었다"),
            Character("하린", "주치의", "약을 바꿔 처방했다", "정원에 있었다")]
    scene = Scene("저택 서재에서 회장이 숨진 채 발견됐다",
                  [("깨진 유리잔", True), ("찢긴 유언장 사본", False)],
                  ["민서: 저는 계속 서재 밖에 있었어요.", "도윤: 소리를 들었습니다."])

    print()
    print("  ── 도윤이 보는 컨텍스트 ──")
    for line in brief(scene, cast, "도윤").split("\n"):
        print("   ", line)
    print()
    for name, fn in (("정상 brief()", brief), ("한 줄 빠뜨린 brief_leaky()", brief_leaky)):
        leaks = leak_scan(scene, cast, fn)
        hidden = hidden_clue_leak(scene, cast, fn)
        print(f"  {name:26} 비밀 누출 {len(leaks):>2}건 · 미공개 단서 누출 {len(hidden)}건")
        for v, o, what in leaks[:3]:
            print(f"      {v} 가 {o} 의 {what}을 알고 있다")
    print()


if __name__ == "__main__":
    _demo()
