# -*- coding: utf-8 -*-
"""
Ch05 회귀 테스트

이 파일의 값은 **본문 §4 의 답 여덟 개** 를 코드에 묶어 두는 것이다.
4단이 생겼을 때 §1 만 고치고 §4 를 안 고치는 일이 실제로 일어난다.
그러면 여기서 터진다.

그리고 하나 더 — **결정 트리가 자기 결정표를 어기지 않는가.**
고른 칸이 그 요구를 만족하지 못하면 둘 중 하나가 틀린 것이다.

    python test_ladder.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ladder import (R1, R15, R2, R3, R3R, R4, REALTIME_BUDGET,  # noqa: E402
                    SCENARIOS, TABLE, Need, choose, feasible, gpu_count)
from render_2d import ANCHOR, _squash, composite, make_parts, measure  # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch05 사다리 결정 ──")

    # ── §4 본문의 답 여덟 개 ───────────────────────────────────────
    for label, need, expected in SCENARIOS:
        got = choose(need)["rung"]
        ok(got == expected, f"§4 — {label}", got if got == expected
           else f"기대 {expected} · 실제 {got}")

    # ── ★ 결정 트리가 자기 결정표를 어기지 않는가 ──────────────────
    for label, need, _ in SCENARIOS:
        rung = choose(need)["rung"]
        bad = feasible(rung, need)
        ok(bad == [], f"★ 고른 칸이 요구를 만족한다 — {label}",
           "; ".join(bad) if bad else rung)

    # 이유를 반드시 낸다 — 말 못 하는 결정은 나중에 못 뒤집는다
    ok(all(choose(n)["why"] for _, n, _ in SCENARIOS),
       "★ 모든 결정이 이유를 같이 낸다")

    # ── §2 질문 1 — 지연이 가장 강력한 필터 ────────────────────────
    realtime = Need(latency_budget=REALTIME_BUDGET)
    batch = Need(latency_budget=600)
    ok(not TABLE[choose(realtime)["rung"]]["gpu"],
       "실시간 예산이면 GPU 없는 칸으로 간다")
    ok(TABLE[choose(batch)["rung"]]["gpu"], "배치 예산이면 GPU 칸으로 간다")
    ok(choose(Need(latency_budget=2.1))["rung"] != choose(realtime)["rung"],
       "2.0초와 2.1초가 서로 다른 칸으로 갈린다 — 예산이 아키텍처를 정한다")

    # ── §2 질문 2 — 그림체 ─────────────────────────────────────────
    ok(choose(Need(2.0, art_style_is_product=True))["rung"] == R1,
       "그림체가 상품이면 2D 파츠")
    ok(choose(Need(2.0, art_style_is_product=True,
                   needs_head_turn=True))["rung"] == R15,
       "거기에 고개 돌리기가 필요하면 2.5D")
    ok(choose(Need(2.0))["rung"] == R2, "그림체 제약이 없으면 3D VRM")

    # ── §2 질문 3 — 사람 얼굴 ──────────────────────────────────────
    ok(choose(Need(600, face_is_human=False))["rung"] == R3R,
       "사람 얼굴이 아니면 리타게팅을 경유한다")
    ok(TABLE[R3]["human_only"] and not TABLE[R3R]["human_only"],
       "결정표가 그 차이를 담고 있다")
    ok(feasible(R3, Need(600, face_is_human=False)) != [],
       "동물 얼굴에 3단을 직접 쓰면 걸린다",
       feasible(R3, Need(600, face_is_human=False))[0][:30])

    # ── §3 동시 사용자 = GPU 대수 ──────────────────────────────────
    ok(gpu_count(R2, 200) == 0, "브라우저 렌더는 사용자가 200명이어도 GPU 0장")
    ok(gpu_count(R1, 1000) == 0 and gpu_count(R15, 1000) == 0,
       "1·1.5단도 마찬가지다")
    ok(gpu_count(R3, 50) == 50,
       "★ 3단은 동시 50명이면 GPU 50장 — 원가 구조가 다르다 (§3)")
    ok(gpu_count(R3, 1) == 1, "한 명이어도 한 장은 있어야 한다")
    ok(gpu_count(R4, 10) == 10, "4단도 대수가 사용자에 비례한다")

    # ── 사실감은 결정에 안 들어간다 (§2 의 요점) ────────────────────
    ok(not any("사실" in f for f in Need.__dataclass_fields__),
       "★ Need 에 '사실감' 항목이 없다 — 사실감은 마지막에 고려한다",
       " · ".join(Need.__dataclass_fields__))

    # 결정표에 빠진 칸이 없는가
    for r in (R1, R15, R2, R3, R3R, R4):
        ok(r in TABLE, f"결정표에 {r} 가 있다")
    ok(all(set(v) == set(TABLE[R1]) for v in TABLE.values()),
       "모든 칸이 같은 항목을 채우고 있다 — 비교가 성립한다")

    # ── §3 'GPU 불필요' 를 재 본다 ─────────────────────────────────
    m = measure(frames=60)
    ok(m["ms_per_frame"] < 1000 / 60,
       "★ 1단 합성이 CPU 만으로 60fps 예산 안에 든다 (§3 'GPU 불필요')",
       f"{m['ms_per_frame']:.2f}ms / 16.7ms")
    ok(m["fps"] > 60, "여유가 실제로 있다", f"{m['fps']:.0f}fps")

    # 기준점 (Ch16 §3) — 눌린 뒤 어느 자리가 남는가
    parts = make_parts()
    rows = {}
    for name in ANCHOR:
        import numpy as np
        sq = _squash(parts[name]["img"], 0.3, ANCHOR[name])
        r = np.where(sq[..., 3].sum(axis=1) > 0)[0]
        rows[name] = (int(r[0]), int(r[-1]), sq.shape[0])
    ok(rows["mouth"][0] == 0, "입은 위가 고정된다 — 윗입술이 안 올라간다",
       f"{rows['mouth'][0]}~{rows['mouth'][1]}")
    ok(rows["body"][1] == rows["body"][2] - 1, "몸통은 바닥이 고정된다 — 발이 안 뜬다",
       f"{rows['body'][0]}~{rows['body'][1]} / {rows['body'][2]}")
    lo, hi, tot = rows["eye_l"]
    ok(abs(lo - (tot - 1 - hi)) <= 1, "눈은 위아래가 같이 오므라든다",
       f"위 여백 {lo} · 아래 여백 {tot - 1 - hi}")

    frame = composite(parts, blink=1.0, mouth=1.0)
    ok(frame.shape == (512, 512, 3), "합성 결과가 한 장의 프레임이다")
    ok(float(frame.max()) > 0, "빈 화면이 아니다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
