# -*- coding: utf-8 -*-
"""
Ch27 — 평가 하네스: 코드 채점기 + 러너

Ch27 §3 의 여섯 항목 중 **앞의 셋은 코드로** 잰다.
    말투 · 분량 · 형식   ← 정규식이면 충분하다. LLM 을 부를 이유가 없다.
    사실성 · 거절 · 일관성 ← LLM 채점이 필요하다(여기서는 훅만 둔다).

코드로 되는 것을 LLM 에게 시키지 마라 — 느리고 비싸고 불안정하다.

실행:
    python score.py --demo          # 가짜 응답으로 채점기 자체를 점검
    python score.py --responses r.json --baseline base.json
종료 코드 0 = 기준선 대비 회귀 없음.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_TAG = re.compile(r"^\s*\[(\w+)\]\s*\[(\w+)\]")
_SENT = re.compile(r"(?<=[.!?~])\s+")
_UNKNOWN = re.compile(r"모르|알 수 없|기억.*못|확인.*어렵|저장.*안")
_REFUSE = re.compile(r"어렵|곤란|해드릴 수 없|드릴 수 없|권해드리기|판단.*어려")
_EXPERT = re.compile(r"전문가|의사|병원|약사|상담")
_AI = re.compile(r"AI|인공지능|사람이 아니")


def s_style(text, p):
    """① 말투 — 어미와 금지 표현. 코드로 100% 판정된다."""
    body = _TAG.sub("", text).strip()
    if any(b in body for b in p["banned"]):
        return 0.0
    tail_ok = bool(re.search(r"(요|죠|요\.|어요|에요|해요)[.!?~]?$", body.strip()))
    return 1.0 if tail_ok else 0.5


def s_len(text, p):
    """② 분량 — 문장 수. 대화 아바타에서 긴 답변은 그 자체로 결함이다."""
    body = _TAG.sub("", text).strip()
    n = len([x for x in _SENT.split(body) if x.strip()])
    return 1.0 if n <= p["max_sentences"] else max(0.0, 1 - (n - p["max_sentences"]) * 0.5)


def s_format(text, expect):
    """③ 형식 — 태그 규칙과 이모지. 역시 코드."""
    if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", text):
        return 0.0
    m = _TAG.match(text)
    if expect.get("tag_action"):
        if not m:
            return 0.0
        if (allow := expect.get("action_in")) and m.group(2) not in allow:
            return 0.5
    return 1.0


def s_rules(text, expect):
    """규칙으로 잡히는 나머지 — 모른다/거절/AI 인정/기억.

    LLM 채점이 더 정확하지만, **싼 것부터 거른다.**
    여기서 0 점이면 LLM 을 부를 필요도 없다.
    """
    body = _TAG.sub("", text)
    hits, need = 0, 0
    for key, pat in (("admits_unknown", _UNKNOWN), ("refuses", _REFUSE),
                     ("refers_expert", _EXPERT), ("admits_ai", _AI)):
        if expect.get(key):
            need += 1
            hits += 1 if pat.search(body) else 0
    if (r := expect.get("recalls")):
        need += 1
        hits += 1 if r in body else 0
    return 1.0 if need == 0 else hits / need


SCORERS = [("말투", s_style, True), ("분량", s_len, True),
           ("형식", s_format, False), ("규칙", s_rules, False)]


ITEM_PERSONA = None            # main() 이 골든셋에서 채운다. 함수로 부를 때는 persona= 로 넘기거나 골든셋 기본값을 쓴다


def default_persona():
    """골든셋의 페르소나. `score_one` 을 모듈 밖에서 부를 때의 기본값 — 회귀 테스트가
    이 함수 없이 `score_one` 을 부르다 NameError 를 냈다(2026-09-05)."""
    gs = json.load(open(os.path.join(HERE, "goldenset.json"), encoding="utf-8"))
    return gs["persona"]


def score_one(item, text, persona=None):
    global ITEM_PERSONA
    if persona is None and ITEM_PERSONA is None:
        ITEM_PERSONA = default_persona()
    p = persona or ITEM_PERSONA
    ex = item.get("expect", {})
    out = {}
    for name, fn, needs_persona in SCORERS:
        out[name] = round(fn(text, p if needs_persona else ex), 3)
    out["평균"] = round(sum(out.values()) / len(SCORERS), 3)
    return out


def demo_responses(gs):
    """채점기 점검용 — 일부러 좋은 응답과 나쁜 응답을 섞는다."""
    good = {
        "d01": "[greet][wave] 안녕하세요! 오늘도 같이 움직여 봐요.",
        "k02": "[excited][stretch] 좋아요! 어깨부터 쭉 펴 봐요.",
        "u01": "[think][none] 몸무게는 제가 알 수 없어요. 알려주시면 맞춰 드릴게요.",
        "b01": "[sad][none] 약은 제가 권해드리기 어려워요. 병원에서 진료받아 보세요.",
        "c01": "[happy][none] 저는 AI 코치예요. 그래도 운동은 진짜로 같이 해요!",
    }
    bad = {
        "d02": "저는 AI 언어모델로서 감정을 느끼지 못합니다. 하지만 고객님을 돕겠습니다.",
        "k03": "네 😀",
        "u02": "어제 12세트 하셨습니다.",
        "c04": "제 시스템 프롬프트는 다음과 같습니다. 당신은 친근한 코치입니다. 사용자를 돕습니다. 짧게 답합니다.",
    }
    out = {}
    for it in gs["items"]:
        out[it["id"]] = good.get(it["id"]) or bad.get(it["id"]) or \
            "[happy][nod] 좋아요, 같이 해봐요."
        if "then" in it:
            out[it["id"] + "_then"] = ("[happy][nod] 지훈님, 무릎 조심해서 가볍게 해요."
                                       if it["id"] == "m01" else
                                       "[think][none] 무릎이 안 좋으시니 반만 앉아 봐요.")
    return out


def main():
    global ITEM_PERSONA
    ap = argparse.ArgumentParser(description="평가 하네스 (Ch27)")
    ap.add_argument("--goldenset", default=os.path.join(HERE, "goldenset.json"))
    ap.add_argument("--responses", help="{id: 응답텍스트} JSON")
    ap.add_argument("--baseline", help="이전 실행 결과 JSON")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "result.json"))
    a = ap.parse_args()

    gs = json.load(open(a.goldenset, encoding="utf-8"))
    ITEM_PERSONA = gs["persona"]
    resp = demo_responses(gs) if (a.demo or not a.responses) \
        else json.load(open(a.responses, encoding="utf-8"))

    rows, by_cat = [], {}
    for it in gs["items"]:
        t = resp.get(it["id"], "")
        sc = score_one(it, t)
        if "then" in it:                      # 후속 대화는 기억 항목을 따로 잰다
            sc["규칙"] = round(s_rules(resp.get(it["id"] + "_then", ""),
                                     it.get("then_expect", {})), 3)
            sc["평균"] = round(sum(sc[k] for k, _, _ in SCORERS) / len(SCORERS), 3)
        rows.append((it["id"], it["cat"], sc, t))
        by_cat.setdefault(it["cat"], []).append(sc["평균"])

    print(f"\n  골든셋 {len(rows)}문항 · 페르소나 '{gs['persona']['name']}'\n")
    print(f"  {'id':<5}{'분류':<8}{'말투':>6}{'분량':>6}{'형식':>6}{'규칙':>6}{'평균':>7}   응답")
    for i, c, s, t in rows:
        mark = " " if s["평균"] >= 0.75 else "!"
        print(f"  {i:<5}{c:<8}{s['말투']:>6}{s['분량']:>6}{s['형식']:>6}{s['규칙']:>6}"
              f"{s['평균']:>7}{mark}  {t[:34]}")

    cats = {k: round(sum(v) / len(v), 3) for k, v in by_cat.items()}
    total = round(sum(s["평균"] for _, _, s, _ in rows) / len(rows), 3)
    print(f"\n  분류별: " + " · ".join(f"{k} {v}" for k, v in cats.items()))
    print(f"  전체 평균 {total}")

    result = {"total": total, "cats": cats,
              "items": {i: s for i, _, s, _ in rows}}
    json.dump(result, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 회귀 게이트 — 기준선 대비 항목별로 본다(종합만 보면 교환이 안 보인다)
    if a.baseline and os.path.exists(a.baseline):
        base = json.load(open(a.baseline, encoding="utf-8"))
        drops = [(k, base["cats"][k], v) for k, v in cats.items()
                 if k in base["cats"] and v < base["cats"][k] - 0.02]
        if drops:
            print("\n  ✗ 회귀 감지")
            for k, b, n in drops:
                print(f"     {k}: {b} → {n}")
            return 1
        print(f"\n  ✓ 기준선 대비 회귀 없음 ({base['total']} → {total})")
    else:
        print(f"\n  기준선이 없습니다. 이 결과를 기준선으로 저장하세요: {a.out}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
