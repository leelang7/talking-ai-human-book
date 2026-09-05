# -*- coding: utf-8 -*-
"""
Ch22 — 페르소나 빌더 + 말투 검증기

두 층으로 나눈다(Ch22 §2).
    규칙 층  이 캐릭터가 **어떻게** 말하는가.  대화 내내 고정 → system
    상태 층  이 캐릭터가 **지금 무엇을 아는가**. 매번 조립 → user

이 분리가 주는 것 셋:
    · 규칙을 고칠 때 상태 조립 코드를 안 건드린다
    · 캐릭터가 여럿이어도 규칙 층의 공통부를 공유한다
    · **무엇이 새는지 추적할 때 상태 층만 보면 된다**(Ch26 §3)

그리고 이 장의 핵심 하나 — **아는 것과 말하는 것은 다르다.**
비밀은 주되(알아야 연기가 된다), 발화 금지를 따로 명시한다.

실행:  python persona.py          (캐릭터 둘을 조립해 비교)
       python test_persona.py     (회귀 테스트)
"""
import re

# 모든 캐릭터가 공유하는 규칙. 캐릭터별 파일에서 이걸 반복하지 않는다(Ch22 §6).
COMMON_RULES = [
    "한두 문장으로 짧게 답한다.",
    "메타발언 금지 — '제가 맡은 역할상', '주어진 정보에 따르면' 같은 말을 하지 않는다.",
    "이모지와 특수문자를 쓰지 않는다.",
    "따옴표로 감싸지 않는다.",
]

TAG_RULE = ("답변 맨 앞에 대괄호 태그 두 개를 붙인다: [감정][동작]. "
            "감정 {emos} · 동작 {acts}")


class Persona:
    """캐릭터 하나. **데이터로 관리한다** — 코드가 아니라 설정에 둔다."""

    def __init__(self, name, identity, ending, banned=(), address=None,
                 examples=(), forbidden_topics=(), unknown_style=None,
                 emos=(), acts=(), secret=None, stance=None):
        self.name, self.identity, self.ending = name, identity, ending
        self.banned = list(banned)
        self.address = address
        self.examples = list(examples)
        self.forbidden_topics = list(forbidden_topics)
        self.unknown_style = unknown_style
        self.emos, self.acts = list(emos), list(acts)
        self.secret, self.stance = secret, stance

    # ── 규칙 층 (고정) ───────────────────────────────────────────────
    def system_prompt(self):
        L = [self.identity, f"말투: {self.ending}"]
        if self.address:
            L.append(f"상대를 '{self.address}' 라고 부른다.")
        L += COMMON_RULES
        if self.banned:
            # 하라는 것보다 하지 말라는 것이 잘 지켜진다(Ch22 §3)
            L.append("다음 표현을 쓰지 않는다: " + " / ".join(self.banned))
        if self.forbidden_topics:
            L.append("다음은 답하지 않고 전문가를 안내한다: "
                     + " / ".join(self.forbidden_topics))
        if self.unknown_style:
            # 모르는 것을 '캐릭터의 말투로' 말하는 방식을 미리 정의한다(Ch22 §4)
            L.append(f"모르는 것은 이렇게 말한다: \"{self.unknown_style}\"")
        if self.examples:
            L.append("이런 식으로 말한다:")
            L += [f"  - {e}" for e in self.examples]
        if self.emos and self.acts:
            # 형식 지시는 **끝에** 둬야 준수율이 높다(Ch22 §2)
            L.append(TAG_RULE.format(emos="/".join(self.emos), acts="/".join(self.acts)))
        return "\n".join(L)

    # ── 상태 층 (매 호출 조립) ───────────────────────────────────────
    def state_prompt(self, situation=None, facts=(), history=(), turn=None):
        L = []
        if situation:
            L.append(f"[상황] {situation}")
        if self.secret:
            # ★ 비밀은 준다. 그리고 **말하지 말라고 따로 적는다**(Ch22 §3).
            #   정보를 주는 것과 발화를 허용하는 것은 다른 문제다.
            L.append(f"[너의 비밀] {self.secret}")
            L.append("[주의] 비밀은 절대 직접 밝히지 않는다. 아는 티도 내지 않는다.")
        if self.stance:
            L.append(f"[너의 입장] {self.stance}")
        if facts:
            L.append("[아는 것]\n" + "\n".join(f"- {f}" for f in facts))
        if history:
            L.append("[지금까지]\n" + "\n".join(history))
        if turn:
            L.append(turn)
        return "\n".join(L)

    def build(self, **kw):
        return {"system": self.system_prompt(), "user": self.state_prompt(**kw)}


# ── 말투 검증기 — 코드로 되는 것은 코드로 (Ch27 §3) ─────────────────
_TAG = re.compile(r"^\s*\[(\w+)\]\s*\[(\w+)\]\s*")
_META = re.compile(r"제가 맡은|주어진 정보|역할상|언어모델|어시스턴트로서")
_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
# ★ 어미는 **매칭이 아니라 분류** 로 판정해야 한다.
#
#   초판은 요체를 `(요|죠|…)$` 로 잡았는데, "함께 진행하시죠." 가 '죠' 에 걸려 통과했다.
#   그런데 '-시죠' 는 요체가 아니라 **합쇼체 권유형** 이다. 캐릭터가 말투를 바꿨는데
#   검증기가 못 잡은 것이다.
#
#   해법: 더 구체적인 것(합쇼체)을 먼저 보고, 남는 것을 요체로 본다.
#   한국어는 어미가 인격이므로(Ch22 §3) 이 구분이 곧 페르소나 검증이다.
_FORMAL = re.compile(r"(습니다|ㅂ니다|입니다|십시오|시지요|시죠|하죠)[.!?~]*$")
_POLITE = re.compile(r"(에요|예요|어요|아요|해요|세요|네요|죠|요)[.!?~]*$")
_CASUAL = re.compile(r"(아|어|야|지|해|다|자|numeric)[.!?~]*$")


def detect_ending(body):
    """문장의 말투를 분류한다. 구체적인 것부터 본다."""
    tail = (body.strip().splitlines() or [""])[-1]
    if _FORMAL.search(tail):
        return "합쇼체"
    if _POLITE.search(tail):
        return "요체"
    if _CASUAL.search(tail):
        return "반말"
    return "기타"


def validate(text, p):
    """반환: (통과여부, 위반 목록). 실패 이유를 사람이 읽을 수 있게 준다."""
    bad = []
    body = _TAG.sub("", text or "").strip()
    if not body:
        return False, ["빈 응답"]
    if _EMOJI.search(text):
        bad.append("이모지")
    if _META.search(body):
        bad.append("메타발언")
    if body.startswith(("\"", "'", "“")):
        bad.append("따옴표로 시작")
    for b in p.banned:
        if b in body:
            bad.append(f"금지어 '{b}'")
    # 이모지를 떼고 어미를 본다 — "…코치입니다! 😊" 는 합쇼체이지 '기타' 가 아니다.
    # 실험(_work/experiment.json)에서 이모지 응답 11개가 전부 '기타' 로 잡혀 이모지와 어미가 이중 계수됐다.
    got = detect_ending(_EMOJI.sub("", body).strip())
    if p.ending and got != p.ending:
        bad.append(f"어미 불일치({p.ending} 기대 · {got} 나옴)")
    n = len([s for s in re.split(r"(?<=[.!?~])\s+", body) if s.strip()])
    if n > 2:
        bad.append(f"{n}문장(2문장 초과)")
    if p.emos and p.acts:
        m = _TAG.match(text or "")
        if not m:
            bad.append("태그 없음")
        else:
            if m.group(1) not in p.emos:
                bad.append(f"모르는 감정 '{m.group(1)}'")
            if m.group(2) not in p.acts:
                bad.append(f"모르는 동작 '{m.group(2)}'")
    return (not bad), bad


COACH = Persona(
    name="코치", identity="너는 홈트레이닝 코치다. 친근하고 활기차다.",
    ending="요체", address=None,
    banned=["저는 AI 언어모델", "고객님", "인 것 같습니다"],
    examples=["자, 오늘도 가볍게 시작해 봐요!", "무릎 조심해서 반만 앉아 봐요."],
    forbidden_topics=["약 처방", "질병 진단"],
    unknown_style="그건 제가 알 수 없어요. 알려주시면 맞춰 드릴게요.",
    emos=["greet", "happy", "excited", "think", "sad", "neutral"],
    acts=["wave", "nod", "stretch", "squat", "jumpingjack", "none"],
)

SUSPECT = Persona(
    name="집사", identity="너는 추리극의 저택 집사다. 격식 있고 과묵하다.",
    ending="합쇼체",
    banned=["제가 범인"],
    secret="사건 당일 밤 서재에 있었다.",
    stance="너는 범인이 아니다. 다만 비밀이 드러나면 곤란하다. 단서로 진범을 추리하라.",
)


def _demo():
    for p, kw in ((COACH, dict(situation="첫 인사", facts=["사용자는 무릎이 안 좋음"],
                               turn="사용자: 스쿼트 알려줘")),
                  (SUSPECT, dict(situation="심문 중. 피해자는 저택 주인.",
                                 history=["형사: 그날 밤 어디 계셨습니까?"],
                                 turn="네 차례다."))):
        b = p.build(**kw)
        print(f"\n  ══ {p.name} ══")
        print("  [규칙 층]"); print("\n".join("   " + l for l in b["system"].split("\n")))
        print("  [상태 층]"); print("\n".join("   " + l for l in b["user"].split("\n")))

    print("\n  ══ 말투 검증 ══")
    for t in ["[happy][nod] 좋아요, 같이 해봐요.",
              "저는 AI 언어모델로서 감정을 느끼지 못합니다.",
              "[happy][fly] 날아갈게요 😀",
              "네. 좋습니다. 그럼 시작하겠습니다. 준비되셨나요?"]:
        okk, bad = validate(t, COACH)
        print(f"   [{'OK ' if okk else 'NG '}] {t[:38]:<40}{'· '.join(bad)}")
    print()


if __name__ == "__main__":
    _demo()
