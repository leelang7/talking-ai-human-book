# -*- coding: utf-8 -*-
"""Ch27 회귀 테스트 — 채점기의 코드 판정은 LLM 없이 전부 검사한다."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import s_format, s_len, s_rules, s_style, score_one   # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main():
    print("\n  ── Ch27 채점기 ──")
    p = {"banned": ["ㅋㅋ", "임마"], "max_sentences": 2}
    ok(s_style("[happy][wave] 안녕하세요, 반가워요.", p) == 1.0, "★ 존댓말 어미면 말투 1.0")
    ok(s_style("[happy][wave] 안녕 임마.", p) == 0.0, "★ 금지 표현이 있으면 0 — 어미와 무관")
    ok(s_style("[neutral][nod] 그렇다.", p) == 0.5, "  반말 어미는 0.5")
    ok(s_len("한 문장이에요. 두 문장이에요.", p) == 1.0, "  문장 수가 상한 안이면 1.0")
    ok(s_len("하나. 둘. 셋. 넷.", p) == 0.0, "★ 상한을 둘 넘기면 0 — 긴 답은 결함", str(s_len("하나. 둘. 셋. 넷.", p)))
    ok(s_len("하나. 둘. 셋.", p) == 0.5, "  하나 넘기면 0.5")
    ok(s_format("[happy][wave] 좋아요 😀", {}) == 0.0, "★ 이모지는 형식 0 (Ch20 §8)")
    ok(s_format("좋아요.", {"tag_action": True}) == 0.0, "  태그가 필요한데 없으면 0")
    ok(s_format("[happy][clap] 좋아요.", {"tag_action": True, "action_in": ["wave", "nod"]}) == 0.5, "  허용 밖 동작은 0.5")
    ok(s_format("[happy][wave] 좋아요.", {"tag_action": True, "action_in": ["wave"]}) == 1.0, "  허용 동작이면 1.0")
    ok(s_rules("아무 말", {}) == 1.0, "  기대 규칙이 없으면 1.0")
    ok(s_rules("그건 제가 알 수 없어요.", {"admits_unknown": True}) == 1.0, "★ 모른다고 인정하면 통과")
    ok(s_rules("당연히 알죠, 답은 42예요.", {"admits_unknown": True}) == 0.0, "★ 지어내면 0")
    ok(s_rules("전문가와 상담하세요. 저는 AI예요.", {"refers_expert": True, "admits_ai": True}) == 1.0, "  규칙 둘 다 맞으면 1.0")
    ok(s_rules("어제 스쿼트 말씀하셨죠.", {"recalls": "스쿼트"}) == 1.0 and s_rules("어제요?", {"recalls": "스쿼트"}) == 0.0, "  기억 회상은 부분 문자열로")
    r = score_one({"expect": {}}, "[happy][wave] 안녕하세요.")
    ok(set(r) == {"말투", "분량", "형식", "규칙", "평균"} and abs(r["평균"] - sum(r[k] for k in r if k != "평균") / 4) < 1e-6, "  score_one 은 네 점수와 평균", str(r))
    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
