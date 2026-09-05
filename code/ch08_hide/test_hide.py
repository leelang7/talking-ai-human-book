# -*- coding: utf-8 -*-
"""
Ch08 회귀 테스트

"깜빡임이 사라졌다" 는 눈으로 하는 주장이다. 이 파일은 그것을
**빈 프레임 수** 로 바꾼다. 0 이면 참이고 아니면 거짓이다.

    python test_hide.py
"""
import sys
import wave
import io

sys.path.insert(0, __file__.rsplit("test_hide.py", 1)[0] or ".")

from hide import (ALLOWED, CROSSFADE_MS, IDLE_SECONDS, STATES,  # noqa: E402
                  DoubleBuffer, SingleBuffer, TIMEOUT_S, can, crossfade,
                  imperceptible, jump, resolve_turn, silent_wav, simulate,
                  visual)

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch08 지연 숨기기 ──")

    # ── §5 더블 버퍼 ───────────────────────────────────────────────
    srcs = ["a.mp4", "b.mp4", "c.mp4"]
    single = simulate(SingleBuffer(), srcs, load_frames=3)
    double = simulate(DoubleBuffer(), srcs, load_frames=3)

    ok(single["blank_frames"] > 0, "단일 버퍼는 실제로 화면이 빈다",
       f"{single['blank_frames']}프레임")
    ok(double["blank_frames"] == 0, "더블 버퍼는 빈 프레임이 0 이다",
       f"{double['blank_frames']}프레임 / {double['total']}")
    ok(double["last"] == "c.mp4", "그러면서 마지막 소스는 제대로 올라간다",
       double["last"])

    # 로드가 아무리 느려도 앞은 계속 보인다 — 그것이 요점
    slow = simulate(DoubleBuffer(), srcs, load_frames=30, hold_frames=1)
    ok(slow["blank_frames"] == 0, "로드가 30프레임 걸려도 화면은 안 빈다",
       "느릴수록 단일 버퍼와 차이가 벌어진다")

    # 준비 안 된 것을 앞으로 올리면 안 된다
    b = DoubleBuffer()
    b.stage("first.mp4", 0)
    b.tick()
    b.stage("next.mp4", 5)
    ok(b.promote() is False, "준비 안 된 슬롯은 promote 를 거부한다")
    ok(b.visible == "first.mp4", "거부되는 동안 이전 프레임이 계속 보인다", b.visible)

    # 콜드 스타트 — 더블 버퍼도 만능은 아니다
    cold = simulate(DoubleBuffer(), srcs, load_frames=3, initial=None)
    ok(cold["blank_frames"] > 0,
       "아이들 루프 없이 시작하면 첫 로드는 더블 버퍼여도 빈다",
       f"{cold['blank_frames']}프레임 — §2 가 §5 의 전제조건이다")
    ok(cold["blank_frames"] < single["blank_frames"],
       "그래도 매 교체마다 비는 단일 버퍼보다는 적다",
       f"{cold['blank_frames']} vs {single['blank_frames']}")
    ok(DoubleBuffer().visible is None, "아직 아무것도 안 올렸으면 비어 있다")

    # ── §4 크로스페이드 ────────────────────────────────────────────
    for t in (0, 40, 75, 150, 400):
        a, c = crossfade(t)
        ok(abs(a + c - 1.0) < 1e-9, f"불투명도 합이 1 이다 (t={t}ms)",
           f"{a:.2f} + {c:.2f}")
    ok(crossfade(0)[1] == 0.0 and crossfade(CROSSFADE_MS)[1] == 1.0,
       "시작은 완전히 이전 것, 끝은 완전히 새 것")
    ok(crossfade(9999)[1] == 1.0, "구간을 넘어가도 1 을 넘지 않는다")
    ok(crossfade(50, 0) == (0.0, 1.0), "duration 0 은 하드 컷이다")

    ok(imperceptible(CROSSFADE_MS), "기본값이 §4 의 100~200ms 안이다",
       f"{CROSSFADE_MS}ms")
    ok(not imperceptible(600), "600ms 는 전환이 눈에 보인다")
    ok(not imperceptible(30), "30ms 는 하드 컷과 다를 바 없다")

    hard, soft = jump(0, 1, 0), jump(0, 1, CROSSFADE_MS)
    ok(soft < hard / 4, "디졸브가 프레임당 변화를 4배 이상 줄인다",
       f"하드컷 {hard:.2f} → {soft:.2f}")

    # ── §1 스피너가 없다 ───────────────────────────────────────────
    ok("loading" not in STATES and "spinner" not in STATES,
       "상태 목록에 '로딩' 이 없다", " · ".join(STATES))
    ok(all(visual(s) != "spinner" for s in STATES),
       "어느 상태에서도 스피너를 그리지 않는다")
    ok(visual("thinking") == "idle_loop",
       "생각하는 동안에도 아이들 루프가 돈다 — 그것이 '듣고 있음' 이다")
    ok(visual("speaking") != visual("idle"), "말할 때만 다른 것이 돈다")

    # 전이 — 사용자가 끼어들 수 있어야 한다
    ok(can("speaking", "listening"), "말하는 중에 끼어들기(barge-in)가 가능하다")
    ok(not can("idle", "speaking"), "듣지도 않고 말하기 시작할 수는 없다")
    ok(all(d in STATES for ds in ALLOWED.values() for d in ds),
       "전이표의 목적지가 전부 알려진 상태다")
    reachable = {d for ds in ALLOWED.values() for d in ds}
    ok(set(STATES) - reachable == set(), "도달 불가능한 상태가 없다",
       str(set(STATES) - reachable) if set(STATES) - reachable else "전부 도달 가능")

    # ── §7 폴백 ────────────────────────────────────────────────────
    cases = [(1.2, True, None), (9.9, True, None), (None, True, None),
             (0.5, False, None), (9.9, True, "볼넷은 네 번 공을 골라 나가는 겁니다")]
    ok(all(resolve_turn(*c)["audio"] for c in cases),
       "어떤 경로로 끝나도 소리가 난다 (§7)", f"{len(cases)}가지 경로")
    ok(resolve_turn(9.9)["path"] == "fallback", "타임아웃은 폴백으로 간다")
    ok(resolve_turn(0.5, tts_ok=False)["log"] == "tts_failed",
       "실패 이유는 로그로만 남긴다 — 화면에는 안 띄운다")
    ok(resolve_turn(9.9, offline="답")["path"] == "offline",
       "오프라인 답이 있으면 폴백 문구보다 그것을 쓴다")
    ok(TIMEOUT_S <= 5.0, "타임아웃이 5초 이하다 (§7)", f"{TIMEOUT_S}초")

    # ── §3 무음 소스 ───────────────────────────────────────────────
    data = silent_wav(1.0, 16000)
    with wave.open(io.BytesIO(data), "rb") as w:
        ok(w.getnchannels() == 1 and w.getframerate() == 16000,
           "무음 wav 가 16kHz 모노다 (Ch03 §6 과 같은 규격)")
        frames = w.readframes(w.getnframes())
        ok(w.getnframes() == 16000, "1초 = 16000 프레임", str(w.getnframes()))
        ok(set(frames) == {0}, "전부 0 이다 — 진짜 무음이다")
    ok(len(silent_wav(IDLE_SECONDS)) > len(data) * 3,
       f"아이들 기본 길이가 {IDLE_SECONDS}초다 (§2)")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
