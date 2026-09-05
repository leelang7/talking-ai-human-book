# -*- coding: utf-8 -*-
"""
Ch22 — 페르소나 회귀 테스트

부록 F 실패 38~40 을 못 박는다.
  38 대화가 길어지면 말투가 풀린다 → 규칙 층은 상태와 무관하게 고정
  39 "저는 AI 언어모델로서" 가 나온다 → 금지어 + 모르는 것의 말투 정의
  40 감정적 주제에서 존댓말이 바뀐다 → 어미 검증

실행:  python test_persona.py     (종료 코드 0 = 통과)
"""
import sys

from persona import detect_ending, COACH, COMMON_RULES, SUSPECT, Persona, validate

FAILS = []


def ok(cond, name, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"         {detail}")
        FAILS.append(name)


def run():
    # ── 두 층 분리 (Ch22 §2) ──
    s1 = COACH.system_prompt()
    a = COACH.state_prompt(situation="첫 인사", turn="안녕")
    b = COACH.state_prompt(situation="30턴 뒤", facts=["무릎이 안 좋음"], turn="또 안녕")
    ok(COACH.system_prompt() == s1, "규칙 층은 상태가 바뀌어도 동일하다(실패 38)")
    ok(a != b, "상태 층은 매번 달라진다")
    ok("[상황]" in a and "[상황]" not in s1, "상황은 상태 층에만 있다")

    # 형식 지시는 끝에 둬야 준수율이 높다
    ok(s1.strip().split("\n")[-1].startswith("답변 맨 앞에"),
       "태그 규칙이 규칙 층 맨 끝에 온다")

    # 공통 규칙은 캐릭터마다 반복하지 않는다
    ok(all(r in COACH.system_prompt() and r in SUSPECT.system_prompt()
           for r in COMMON_RULES), "공통 규칙이 모든 캐릭터에 들어간다")

    # ── 아는 것과 말하는 것의 분리 (Ch22 §3) ──
    st = SUSPECT.state_prompt(situation="심문", turn="네 차례")
    ok("[너의 비밀]" in st, "비밀은 컨텍스트에 **준다**(알아야 연기가 된다)")
    ok("절대 직접 밝히지 않는다" in st,
       "그리고 발화 금지를 **따로** 명시한다")
    ok("[너의 비밀]" not in SUSPECT.system_prompt(),
       "비밀은 규칙 층이 아니라 상태 층에 있다(누출 추적이 쉬워진다)")

    # 비밀 없는 캐릭터는 그 블록 자체가 없어야 한다
    ok("[너의 비밀]" not in COACH.state_prompt(turn="x"),
       "비밀이 없으면 빈 블록을 넣지 않는다")

    # ── 말투 검증 ──
    good = "[happy][nod] 좋아요, 같이 해봐요."
    okk, bad = validate(good, COACH)
    ok(okk, "정상 응답은 통과", f"{bad}")

    cases = [
        ("저는 AI 언어모델로서 답변드립니다.", "금지어", "실패 39 — AI 언어모델"),
        ("[happy][nod] 좋습니다. 함께 진행하시죠.", "어미", "실패 40 — 요체 이탈"),
        ("[happy][fly] 좋아요.", "모르는 동작", "목록에 없는 동작"),
        ("[happy][nod] 좋아요 😀", "이모지", "이모지 누출"),
        ("좋아요, 같이 해봐요.", "태그 없음", "태그 누락"),
        ("[happy][nod] 하나요. 둘이요. 셋이요.", "문장", "분량 초과"),
        ("[happy][nod] 제가 맡은 역할상 그렇습니다.", "메타발언", "메타발언"),
    ]
    for text, needle, label in cases:
        okk, bad = validate(text, COACH)
        ok((not okk) and any(needle in b for b in bad), f"검출: {label}", f"{bad}")

    # 합쇼체 캐릭터는 반대로 요체가 위반이다
    okk, bad = validate("그날 밤 서재에 있었습니다.", SUSPECT)
    ok(okk, "합쇼체 캐릭터의 합쇼체 응답은 통과", f"{bad}")
    okk, bad = validate("그날 밤 서재에 있었어요.", SUSPECT)
    ok(not okk and any("어미" in b for b in bad),
       "같은 문장도 캐릭터가 다르면 위반이 된다", f"{bad}")

    # 빈 응답
    ok(validate("", COACH) == (False, ["빈 응답"]), "빈 응답은 즉시 실패")
    ok(validate("[happy][nod]", COACH)[0] is False, "태그만 있고 본문이 없으면 실패")


if __name__ == "__main__":
    print("페르소나 회귀 테스트 (부록 F 38~40)")
    run()
    # ── 이모지가 뒤에 붙어도 어미는 분류된다 (실험에서 잡힌 이중 계수) ─────
    #   "…코치입니다! 😊" 를 '기타' 로 읽으면 이모지 1건이 어미 위반 1건을 더 만든다.
    _, bad = validate("안녕하세요! 오늘도 같이 해요! 😊", COACH)
    ok(any("이모지" in b for b in bad), "★ 이모지는 따로 잡힌다")
    ok(not any(b.startswith("어미") for b in bad), "★ 이모지 때문에 어미를 '기타' 로 오판하지 않는다", f"{bad}")
    ok(detect_ending("반갑습니다! 😊".replace("😊", "").strip()) == "합쇼체", "  이모지를 떼면 합쇼체로 읽힌다")

    print(f"\n  {'전부 통과' if not FAILS else str(len(FAILS)) + '건 실패: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)
