# -*- coding: utf-8 -*-
"""
Ch17 — 음량 구동 회귀 테스트

부록 F 의 실패 21~24 번을 코드로 못 박는다.
  21 입이 덜덜 떨린다      → 평활화
  22 조용한데 달싹인다      → 바닥 자르기
  23 파일마다 벌림이 다르다  → 동적 천장
  24 끝나고 반쯤 굳는다     → close()

실행:  python test_mouth.py     (종료 코드 0 = 통과)
"""
import sys

from mouth import MouthDriver, mouth_shape

FAILS = []


def ok(cond, name, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"         {detail}")
        FAILS.append(name)


def run():
    # 실패 22 — 무음 구간의 미세 잡음에서 입이 열리면 안 된다
    d = MouthDriver()
    for _ in range(30):
        d.feed(0.004)
    ok(d.value < 0.02, "무음 잡음에서 입이 닫혀 있다", f"value={d.value:.4f}")

    # 실패 21 — 프레임마다 요동쳐도 출력이 떨지 않아야 한다
    d = MouthDriver()
    seq = [0.5, 0.05, 0.5, 0.05, 0.5, 0.05, 0.5, 0.05]
    out = [d.feed(v) for v in seq]
    swing = max(abs(b - a) for a, b in zip(out, out[1:]))
    ok(swing < 0.62, "요동치는 입력에도 출력이 급변하지 않는다", f"최대 변화 {swing:.2f}")

    # ① 비대칭 — 여는 속도가 닫는 속도보다 빨라야 한다
    a = MouthDriver(); [a.feed(0.9) for _ in range(3)]
    b = MouthDriver(); b.value = 1.0; [b.feed(0.0) for _ in range(3)]
    ok(a.value > (1.0 - b.value), "여는 쪽이 닫는 쪽보다 빠르다",
       f"3프레임 후 열림 {a.value:.2f} vs 닫힘량 {1-b.value:.2f}")

    # 실패 23 — 작은 소리 파일에서도 입이 끝까지 열려야 한다
    quiet, loud = MouthDriver(), MouthDriver()
    for _ in range(40):
        quiet.feed(0.08); loud.feed(0.80)
    ok(abs(quiet.value - loud.value) < 0.2,
       "음량이 달라도 최대 벌림이 비슷하다(동적 천장)",
       f"작은소리 {quiet.value:.2f} vs 큰소리 {loud.value:.2f}")

    # 실패 24 — 재생 종료 시 확실히 닫혀야 한다
    d = MouthDriver(); [d.feed(0.7) for _ in range(10)]
    ok(d.value > 0.3 and d.close() == 0.0, "close() 가 입을 완전히 닫는다")

    # ④ 곡선 — 작은 소리를 들어 올린다.
    #    주의: **일정한 입력으로는 검증되지 않는다.** 동적 천장이 그 값에 붙어
    #    x=1.0 이 되어 곡선과 선형이 같아진다. 초판 테스트가 여기서 틀렸다.
    #    큰 소리로 천장을 세운 뒤, 작은 소리를 넣어 비교해야 한다.
    lin, crv = MouthDriver(curve=1.0), MouthDriver(curve=0.5)
    for _ in range(6):                      # 천장 세우기
        lin.feed(1.0); crv.feed(1.0)
    for _ in range(25):                     # 그 아래 작은 소리
        lin.feed(0.30); crv.feed(0.30)
    ok(crv.value > lin.value + 0.05, "곡선이 작은 소리를 들어 올린다",
       f"곡선 {crv.value:.2f} vs 선형 {lin.value:.2f}")

    # 입 모양 인덱스 경계
    ok([mouth_shape(v) for v in (0.0, 0.4, 0.9, 1.0)] == [0, 1, 2, 2],
       "입 모양 인덱스가 범위를 넘지 않는다")


if __name__ == "__main__":
    print("음량 구동 회귀 테스트 (부록 F 21~24)")
    run()
    print(f"\n  {'전부 통과' if not FAILS else str(len(FAILS)) + '건 실패: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)
