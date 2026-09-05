# -*- coding: utf-8 -*-
"""
Ch24 실험 — 세 주장을 숫자로.

  ① "턴이 아니라 토큰으로 자르라"   턴 수 창(최근 8턴) vs 토큰 예산(1200) 에서 컨텍스트 크기의 최대·평균
  ② "요약도 다시 요약된다"          300턴 뒤 요약 길이가 예산(400) 안에 머무는가 · 압축비
  ③ "잊는 것도 설계다"              반감기 30일 사실의 점수가 며칠 뒤 회상 문턱(0.05) 아래로 내려가는가

    python experiment.py    → _work/experiment.json
"""
import json, math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memory import ShortTerm, Summary, LongTerm, toklen

random.seed(3)
SHORT = ["네", "좋아요", "오늘 스쿼트 했어요", "무릎이 조금 아파요", "내일도 할게요", "고마워요", "몇 세트가 좋아요?"]
LONG = ("어제는 회사에서 야근을 하고 집에 늦게 들어와서 운동을 못 했는데 오늘은 꼭 하려고 해요 그런데 "
        "지난주에 무릎을 다쳐서 스쿼트 대신 할 수 있는 운동이 있을지 궁금하고 식단도 같이 봐 주시면 좋겠어요 ") * 6
BOT = ["[happy][nod] 좋아요, 같이 해봐요.", "[think][none] 무릎은 조심해요. 반만 앉아 봐요.", "[excited][stretch] 어깨부터 쭉 펴 봐요!"]


def conversation(n=300, long_every=25, long=None):
    long = LONG if long is None else long
    for i in range(n):
        yield ("user", long if i % long_every == 12 else random.choice(SHORT))
        yield ("bot", random.choice(BOT))


def main():
    out = {}
    # ① 턴 창 vs 토큰 예산
    turns_window, st, sm = [], ShortTerm(budget=1200), Summary(budget=400)
    win_sizes, tok_sizes, dropped_total = [], [], 0
    for role, text in conversation():
        turns_window.append(text); turns_window = turns_window[-8:]
        win_sizes.append(sum(toklen(t) for t in turns_window))
        dropped = st.add(role, text); dropped_total += sum(toklen(d["text"]) for d in dropped)
        sm.absorb(dropped)
        tok_sizes.append(sum(toklen(t["text"]) for t in st.turns))
    # 같은 실험을 세 배 긴 발화(2,016자)로 — 창은 상한이 없고, 토큰 예산도 한 턴이 예산보다 크면 못 막는다
    win2, tok2, st2 = [], [], ShortTerm(budget=1200); tw2 = []
    for role, text in conversation(long=LONG * 3):
        tw2.append(text); tw2 = tw2[-8:]; win2.append(sum(toklen(x) for x in tw2))
        st2.add(role, text); tok2.append(sum(toklen(x["text"]) for x in st2.turns))
    out["short_term_long3x"] = {"long_message_chars": toklen(LONG * 3), "window_8_turns_max": max(win2), "token_budget_1200_max": max(tok2)}
    print(f"     긴 발화 {toklen(LONG*3):,}자일 때: 8턴 창 최대 {max(win2):,}자 · 토큰 예산 최대 {max(tok2):,}자 " + ("(예산 안 — max_turn 이 턴을 먼저 자른다)" if max(tok2) <= 1200 else "(예산 초과 — 최소 2턴 보장 때문)"))
    out["window_spike_ratio"] = round(max(win2) / (sum(win_sizes) / len(win_sizes)), 1)   # 긴 발화 때 창이 평균의 몇 배로 튀나
    out["short_term"] = {"turns": 600, "window_8_turns": {"max": max(win_sizes), "mean": round(sum(win_sizes) / len(win_sizes))},
                         "token_budget_1200": {"max": max(tok_sizes), "mean": round(sum(tok_sizes) / len(tok_sizes))},
                         "long_message_chars": toklen(LONG)}
    print(f"  ① 8턴 창: 최대 {max(win_sizes):,}자 · 평균 {round(sum(win_sizes)/len(win_sizes)):,}자   |  토큰 예산 1200: 최대 {max(tok_sizes):,} · 평균 {round(sum(tok_sizes)/len(tok_sizes)):,}   (긴 발화 {toklen(LONG)}자)")
    # ② 요약
    out["summary"] = {"dropped_chars": dropped_total, "summary_chars": toklen(sm.text), "budget": 400,
                      "compression": round(dropped_total / max(1, toklen(sm.text)), 1)}
    print(f"  ② 버려진 {dropped_total:,}자 → 요약 {toklen(sm.text)}자 (예산 400 안, 압축 {dropped_total/max(1,toklen(sm.text)):.0f}:1)")
    # ③ 감쇠
    lt = LongTerm(half_life_days=30); now = 1_000_000.0
    lt.remember("knee", "무릎을 다쳤다", now=now)
    lt.remember("name", "이름은 민수", now=now); lt.remember("name", "이름은 민수", now=now + 1); lt.remember("name", "이름은 민수", now=now + 2)
    curve = {d: round(lt.score("knee", now + d * 86400), 3) for d in (0, 30, 60, 90, 120, 150)}
    gone = next(d for d in range(0, 400) if lt.score("knee", now + d * 86400) < 0.05)
    gone_name = next(d for d in range(0, 800) if lt.score("name", now + d * 86400) < 0.05)
    out["decay"] = {"half_life_days": 30, "score_by_day": curve, "forgotten_after_days_once": gone,
                    "forgotten_after_days_said_3x": gone_name, "threshold": 0.05}
    print(f"  ③ 한 번 말한 사실: {curve} → {gone}일째 회상 문턱 아래  |  세 번 말한 사실(가중 2.0): {gone_name}일")
    json.dump(out, open(os.path.join("_work", "experiment.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/experiment.json")


if __name__ == "__main__":
    main()
