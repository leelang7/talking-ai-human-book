# -*- coding: utf-8 -*-
"""
Ch19 — 생명감 회귀 테스트

부록 F 의 실패 27~30 번을 못 박는다.
  27 깜빡임이 메트로놈 같다   → 난수 주기
  28 캐릭터가 취한 것처럼      → 진폭 상한
  29/30 시선·머리 따라가기     → gaze()

실행:  python test_alive.py     (종료 코드 0 = 통과)
"""
import math
import random
import sys

from alive import AMPS, PERIODS, Blink, breath, expr_level, gaze, micro

FAILS = []


def ok(cond, name, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"         {detail}")
        FAILS.append(name)


def blink_times(seed, secs=120.0, dt=1 / 60):
    b, t, prev, out = Blink(rng=random.Random(seed), double=0.0), 0.0, 0.0, []   # 이중 깜빡임은 아래서 따로 본다
    while t < secs:
        v = b.step(dt)
        if prev < 0.5 <= v:
            out.append(t)
        prev = v
        t += dt
    return out


def run():
    # 실패 27 — 간격이 일정하면 메트로놈이다
    ts = blink_times(1)
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    spread = max(gaps) - min(gaps)
    ok(spread > 1.0, "깜빡임 간격이 난수다(메트로놈 아님)",
       f"간격 폭 {spread:.2f}초 · n={len(gaps)}")
    ok(all(1.5 < g < 6.0 for g in gaps), "간격이 상식 범위(1.5~6초)를 벗어나지 않는다",
       f"min {min(gaps):.2f} max {max(gaps):.2f}")

    # 깜빡임 곡선 — 양 끝이 0 이어야 이음매가 없다
    b = Blink(rng=random.Random(2))
    vals = [b.step(1 / 120) for _ in range(120 * 12)]
    ok(max(vals) > 0.98, "완전히 감긴다", f"최대 {max(vals):.3f}")
    ok(min(vals) == 0.0, "완전히 뜬다(양 끝이 0)")

    # 실패 28 — 진폭이 크면 취한 것처럼 보인다. 전부 3도 이내여야 한다.
    worst = max(abs(v) for t in (0.3, 1.7, 4.1, 9.3) for v in micro(t).values())
    ok(worst <= 0.05, "미세 움직임 진폭이 0.05 라디안(약 3도) 이내",
       f"최대 {worst:.4f}")
    ok(abs(breath(1.3)) <= AMPS["spine_x"], "호흡이 상한을 넘지 않는다")

    # 주기가 서로 배수면 파형이 금방 반복된다
    ps = sorted(PERIODS.values())
    ratios = [round(b / a, 3) for a, b in zip(ps, ps[1:])]
    ok(all(abs(r - round(r)) > 0.05 for r in ratios),
       "주기들이 서로 정수배가 아니다", f"비율 {ratios}")

    # 표정 — 대기 중에도 0 으로 떨어지지 않는다
    lvl = 0.7
    for _ in range(200):
        lvl = expr_level(lvl, speaking=False, dt=1 / 60)
    ok(0.10 < lvl < 0.15, "대기 표정이 완전히 0 이 되지 않는다", f"{lvl:.3f}")

    # 실패 30 — 시선을 옮길 때 머리가 따라가야 한다
    moved = [gaze(t, speaking=True) for t in [i / 60 for i in range(600)]]
    active = [g for g in moved if abs(g["x"]) > 0.01]
    ok(active and all(abs(g["head_follow"]) > 0 for g in active),
       "시선이 움직일 때 머리도 따라간다", f"이동 프레임 {len(active)}")
    ok(all(abs(g["head_follow"]) < abs(g["x"]) * 2 for g in active),
       "머리는 눈보다 적게 움직인다(눈이 먼저)")


if __name__ == "__main__":
    print("생명감 회귀 테스트 (부록 F 27~30)")
    run()
    # ── 이중 깜빡임 — 본문(§3 "10~15%")이 약속했는데 코드에 없던 것 ─────────
    b = Blink(rng=random.Random(5)); prev = 0.0; times = []; tt = 0.0
    for _ in range(60 * 60 * 60):
        v = b.step(1 / 60); tt += 1 / 60
        if prev < 0.5 <= v:
            times.append(tt)
        prev = v
    gaps = [y - x for x, y in zip(times, times[1:])]
    share = sum(g < 1.0 for g in gaps) / len(gaps)
    ok(0.08 <= share <= 0.16, "★ 이중 깜빡임(1초 미만 간격)이 10~15% 근처다", f"{share:.1%}")
    ok(all(g >= 0.25 for g in gaps), "  이중이라도 0.25초보다 빠르지는 않다 — 감았다 뜰 시간은 있어야 한다")
    rate = len(times) / 60
    ok(15 <= rate <= 21, "  쉴 때 분당 15~21회 — 문헌 17회 근처", f"{rate:.1f}")

    print(f"\n  {'전부 통과' if not FAILS else str(len(FAILS)) + '건 실패: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)
