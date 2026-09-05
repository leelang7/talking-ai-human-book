# -*- coding: utf-8 -*-
"""
Ch20 — 태그 파서 · 제스처 회귀 테스트

부록 F 의 실패 31~34 번을 못 박는다.
  31 말과 동작이 안 맞는다     → 태그 파싱
  32 태그를 소리 내어 읽는다    → 남은 텍스트에 대괄호 없음
  33 팔이 이상한 곳으로        → 채널 범위
  34 팔을 든 채 굳는다         → 지속 후 빈 포즈 · 엔벨로프

실행:  python test_gesture.py     (종료 코드 0 = 통과)
"""
import sys

from gesture import ACT, DUR, EMO, envelope, parse_tags, pose

FAILS = []


def ok(cond, name, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"         {detail}")
        FAILS.append(name)


def run():
    # ── 태그 파서: 관대해야 한다 (Ch20 §4) ──
    cases = [
        ("[excited][jumpingjack] 자 같이 운동해요!", "excited", "jumpingjack", "자 같이 운동해요!"),
        ("[happy] 반가워요",                          "happy",   "none",        "반가워요"),
        ("그냥 문장입니다",                            "neutral", "none",        "그냥 문장입니다"),
        ("[unknown][wave] 안녕",                      "neutral", "wave",        "안녕"),
        ("[sad][bow][extra] 죄송합니다",               "sad",     "bow",         "죄송합니다"),
        ("[wave][happy] 순서가 바뀌어도",              "happy",   "wave",        "순서가 바뀌어도"),
    ]
    for text, e, a, rest in cases:
        ge, ga, gr = parse_tags(text)
        ok((ge, ga, gr) == (e, a, rest), f"파싱: {text[:26]}",
           f"기대 {(e,a,rest)} · 실제 {(ge,ga,gr)}")

    # 실패 32 — 남은 텍스트에 대괄호가 있으면 TTS 가 읽는다
    _, _, rest = parse_tags("[happy] 중간에 [oops] 낀 것도 [x] 제거")
    ok("[" not in rest and "]" not in rest, "남은 텍스트에 대괄호가 없다", rest)

    ok(parse_tags("")[:2] == ("neutral", "none"), "빈 입력도 안전한 기본값")
    ok(parse_tags("[excited]")[2] == "", "태그만 있으면 텍스트는 빈 문자열")

    # ── 엔벨로프 ──
    ok(envelope(0.0, 2.0) == 0.0 and envelope(2.0, 2.0) == 0.0,
       "엔벨로프 양 끝이 0 이다(튐 방지)")
    ok(envelope(1.0, 2.0) == 1.0, "중간에서 1 이다")

    # 실패 34 — 지속 시간이 지나면 반드시 빈 포즈여야 한다
    stuck = [n for n in ACT if pose(n, DUR[n] + 0.01)]
    ok(not stuck, "지속 후에는 포즈가 비어 기본 자세로 돌아온다", f"굳은 동작 {stuck}")

    # 실패 33 — 채널 값이 상식 범위를 벗어나면 팔이 이상한 곳으로 간다
    worst = {}
    for n in ACT:
        for i in range(41):
            for k, v in pose(n, DUR[n] * i / 40).items():
                if abs(v) > abs(worst.get(k, 0)):
                    worst[k] = v
    over = {k: round(v, 2) for k, v in worst.items() if abs(v) > 2.0}
    ok(not over, "모든 채널이 2.0 라디안 이내", f"초과 {over}")

    # 양 끝이 중간보다 작아야 엔벨로프가 실제로 작동한 것
    bad = []
    for n in ACT:
        d = DUR[n]
        mid = max((abs(v) for v in pose(n, d / 2).values()), default=0)
        edge = max((abs(v) for v in pose(n, 0.05).values()), default=0)
        if mid and edge >= mid:
            bad.append(n)
    ok(not bad, "시작 0.05초 값이 중간보다 작다", f"{bad}")

    # ── 감정 → 진폭·주기 (Ch20 §6) ──
    ok(EMO["excited"]["amp"] > EMO["neutral"]["amp"] > EMO["sad"]["amp"],
       "신남 > 평상 > 슬픔 순으로 진폭이 크다")
    ok(EMO["excited"]["gap"][1] < EMO["sad"]["gap"][0],
       "신남이 슬픔보다 확실히 빠르게 전환한다")

    # 운동 동작은 대화 제스처보다 길어야 반복이 보인다
    talk = max(DUR[n] for n in ("wave", "bow", "nod", "shrug"))
    ex = min(DUR[n] for n in ("jumpingjack", "squat", "twist"))
    ok(ex > talk, "운동 동작이 대화 제스처보다 길다", f"운동 {ex} vs 대화 {talk}")

    # squat 은 관절만으로 안 되므로 drop 채널이 있어야 한다
    ok(any("drop" in pose("squat", DUR["squat"] * i / 10) for i in range(1, 10)),
       "스쿼트에 루트를 내리는 drop 채널이 있다")


if __name__ == "__main__":
    print("제스처·태그 회귀 테스트 (부록 F 31~34)")
    run()
    print(f"\n  {'전부 통과' if not FAILS else str(len(FAILS)) + '건 실패: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)
