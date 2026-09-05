# -*- coding: utf-8 -*-
"""
Ch09 회귀 테스트

이 장의 주장은 *"잘못된 지표는 아무것도 측정하지 않는 것보다 나쁘다"* 다.
그러니 **이 장이 제안하는 지표부터 그 시험을 통과해야 한다.**

세 가지를 확인한다.

  ★ 적중률 하나만 보면 통과시키는 결과가 실제로 있는가 (있다 — 둘)
  ★ 세 지표를 같이 보면 그 둘이 걸리는가
  ★ 멀쩡한 결과를 잘못 떨어뜨리지 않는가 (오탐)

    python test_verify.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from metrics import (CHANCE_MARGIN, FPS, PASS_RATE, QUIET_MAX, _make,  # noqa: E402
                     evaluate, explain, hit_rate, in_speech,
                     quiet_activity_ratio, speech_ratio)

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


SPANS = ((1.0, 4.0), (5.5, 9.0))
DUR = 10.0


def main() -> int:
    print("\n  ── Ch09 싱크 검증 지표 ──")

    # ── ② 우연 기준선 ──────────────────────────────────────────────
    ok(abs(speech_ratio(SPANS, DUR) - 0.65) < 1e-9,
       "발화 3.0초 + 3.5초 ÷ 10초 = 65%", f"{speech_ratio(SPANS, DUR):.0%}")
    ok(speech_ratio([(0, 5), (2, 8)], 10.0) == 0.8,
       "★ 겹친 구간을 두 번 세지 않는다",
       "그냥 더하면 110% — 어떤 결과도 '우연 이하' 가 된다")
    ok(speech_ratio([(0, 20)], 10.0) == 1.0, "영상 밖으로 넘친 구간을 잘라 센다")
    ok(speech_ratio([], 10.0) == 0.0 and speech_ratio(SPANS, 0) == 0.0,
       "빈 입력에서 터지지 않는다")

    # ── ★ 적중률만 보면 통과하는 두 경우 ───────────────────────────
    good = _make("good")
    always = _make("always")
    lots = _make("good", speech=((0.2, 9.7),))
    wide = ((0.2, 9.7),)

    ok(hit_rate(always, FPS, SPANS, 15) >= PASS_RATE,
       "★ '조용할 때 안 닫히는 모델' 도 적중률은 통과한다",
       f"{hit_rate(always, FPS, SPANS, 15):.0%}")
    ok(hit_rate(lots, FPS, wide, 15) >= PASS_RATE,
       "★ '발화가 95% 인 파일' 도 적중률은 통과한다",
       f"{hit_rate(lots, FPS, wide, 15):.0%}")

    # ── 그런데 세 지표를 같이 보면 ─────────────────────────────────
    r_good = evaluate(good, FPS, SPANS, 15, DUR)
    r_always = evaluate(always, FPS, SPANS, 15, DUR)
    r_lots = evaluate(lots, FPS, wide, 15, DUR)

    ok(r_good["pass"], "잘 맞는 결과는 통과한다 (오탐 없음)",
       f"적중 {r_good['rate']:.0%} · 우연대비 {r_good['lift']:.2f}배")
    ok(not r_always["pass"], "★ 조용할 때 안 닫히는 모델은 걸린다")
    ok(any("조용한 구간" in x for x in r_always["reasons"]),
       "  걸린 이유가 조용한 구간이다 — 적중률이 아니다",
       r_always["reasons"][0][:38])
    ok(r_always["rate"] >= PASS_RATE and r_always["lift"] >= CHANCE_MARGIN,
       "  적중률과 우연 대비는 통과했는데도 걸렸다",
       "③ 이 없으면 이 결과는 합격이다")

    ok(not r_lots["pass"], "★ 발화가 95% 인 파일은 걸린다")
    ok(any("우연" in x for x in r_lots["reasons"]),
       "  걸린 이유가 우연 기준선이다", r_lots["reasons"][0][:38])
    ok(r_lots["rate"] == 1.0, "  적중률은 100% 였다", "그래서 ② 가 필요하다")

    # ── ③ 조용한 구간 활발도 ───────────────────────────────────────
    q_good = quiet_activity_ratio(good, FPS, SPANS)
    q_bad = quiet_activity_ratio(always, FPS, SPANS)
    ok(q_good < QUIET_MAX < q_bad, "제대로 닫히는 것과 아닌 것이 갈린다",
       f"{q_good:.0%} vs {q_bad:.0%}")
    ok(quiet_activity_ratio([1.0] * 30, FPS, ((0.0, 1.0),)) is None,
       "조용한 구간이 없으면 판단하지 않는다 — 모른다고 말한다")
    ok(quiet_activity_ratio([0.0] * 60, FPS, SPANS) is None,
       "전부 0 이면 나눌 수 없으니 판단하지 않는다")

    # ── 경계 ───────────────────────────────────────────────────────
    ok(hit_rate([], FPS, SPANS, 15) == 0.0, "빈 프레임 목록에서 터지지 않는다")
    ok(hit_rate([0.5] * 3, FPS, SPANS, 15) == hit_rate([0.5] * 3, FPS, SPANS, 3),
       "프레임보다 큰 N 을 주면 있는 만큼만 본다")
    ok(evaluate([0.5] * 3, FPS, SPANS, 15, DUR)["top"] == 3,
       "  그 사실이 결과에 드러난다")
    ok(in_speech(1.0, SPANS) and in_speech(4.0, SPANS) and not in_speech(4.5, SPANS),
       "구간 경계는 양 끝을 포함한다")

    # ── 입 영역은 얼굴 기준이어야 한다 (실측에서 잡힌 결함) ─────────
    #
    # 화면 비율(세로 55~90%)로만 잡은 ROI 가 1280×720 미디엄샷 드라이버에서
    # 가슴을 재서 우연보다 나쁜 값(0.55배)을 냈다. 얼굴을 찾아 그 안에서 잡자 1.11배.
    # 아래는 그 계약 — 얼굴이 없으면 화면 비율로 떨어지고, 어느 쪽인지 기록한다.
    try:
        import numpy as np
        import verify_sync as V
        blank = np.full((400, 600, 3), 40, dtype=np.uint8)          # 얼굴 없음
        box = V._mouth_box(blank)
        ok(V.LAST_ROI["mode"] == "frame", "★ 얼굴이 없으면 화면 비율로 떨어진다 (크롭 결과물 전제)")
        ok(box == (220, 360, 150, 450), "  그때의 영역이 세로 55~90% · 가로 25~75% 다", str(box))
        ok(V.LAST_ROI["box"] is None, "  얼굴 상자는 None 으로 남는다")
        ok(callable(getattr(V, "_mouth_box", None)) and "얼굴" in V._mouth_box.__doc__,
           "★ 얼굴 기준 모드가 코드에 있고 문서화돼 있다")
    except ImportError as e:
        ok(False, f"verify_sync 를 불러올 수 없다: {e}")

    # 기준값이 본문과 묶여 있는가
    ok(PASS_RATE == 0.80, "통과 기준이 §7 의 80% 다")
    ok(CHANCE_MARGIN > 1.0, "우연 대비 기준이 1배보다 크다 — 같으면 우연이다",
       f"{CHANCE_MARGIN}배")

    # 설명이 사람이 읽을 수 있는가
    txt = explain(r_lots)
    ok("우연 기준선" in txt and "판정" in txt, "설명에 기준선과 판정이 들어간다")
    ok(all(x in txt for x in r_lots["reasons"]), "실패 이유가 빠짐없이 들어간다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
