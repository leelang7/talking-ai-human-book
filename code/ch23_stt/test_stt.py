# -*- coding: utf-8 -*-
"""
Ch23 회귀 테스트

가장 중요한 것은 **끼어들기가 립싱크 층까지 멈추는가** 다.
소리만 멈추고 입이 계속 움직이면, 소리만 멈추는 것보다 나쁘다 (§4).
이 한 줄은 눈으로 보면 금방 알지만 코드에서는 조용히 빠진다.

    python test_stt.py
"""
import sys

sys.path.insert(0, __file__.rsplit("test_stt.py", 1)[0] or ".")

from bargein import (ALLOWED, BACKCHANNEL_MS, BARGE_IN,  # noqa: E402
                     CANCEL_ON_BARGEIN, ECHO_CEILING, FADE_MS, STATES,
                     Session, can, is_backchannel, is_self_echo,
                     should_interrupt)
from vad import (START, END, CALIBRATE_MS, FLOOR, MIN_UTTER_MS, SILENCE_MS,  # noqa: E402
                 Vad, frames, run)

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch23 STT · 끼어들기 ──")

    # ── §2 발화 종료 판정 ──────────────────────────────────────────
    ok(700 <= SILENCE_MS <= 1000, "침묵 임계가 700ms~1초 안이다 (§2)", f"{SILENCE_MS}ms")

    seq = [("quiet", 200), ("loud", 900), ("quiet", 900)]
    ev = run(frames(seq), threshold=0.1)
    ok([e[1] for e in ev] == ["start", "end"], "말하고 멈추면 start·end 가 한 번씩",
       str([e[1] for e in ev]))
    ok(ev[1][0] - ev[0][0] >= SILENCE_MS, "끝 판정은 침묵이 다 찬 뒤에 난다",
       f"{ev[1][0] - ev[0][0]}ms")

    # 짧은 침묵은 발화를 끊지 않는다 — 문장 사이의 숨
    mid = run(frames([("loud", 400), ("quiet", 400), ("loud", 400), ("quiet", 900)]),
              threshold=0.1)
    ok(len([e for e in mid if e[1] == "end"]) == 1,
       "400ms 침묵은 발화를 끊지 않는다 (문장 사이의 숨)",
       f"end {len([e for e in mid if e[1] == 'end'])}회")

    # 최소 발화 길이 — 기침으로 STT 를 돌리지 않는다
    cough = run(frames([("quiet", 200), ("loud", 120), ("quiet", 900)]), threshold=0.1)
    ok(cough == [], "120ms 기침은 발화로 치지 않는다 (§2)", f"{MIN_UTTER_MS}ms 미만")
    real = run(frames([("quiet", 200), ("loud", 260), ("quiet", 900)]), threshold=0.1)
    ok(len(real) == 2, "260ms 는 발화로 친다 — 문턱이 실제로 200ms 근처다")

    # ── §2 주변 소음 보정 ──────────────────────────────────────────
    quiet_room = [0.002, 0.003, 0.002, 0.004, 0.003]
    hall = [0.05, 0.07, 0.04, 0.09, 0.06]
    tq, th = Vad().calibrate(quiet_room), Vad().calibrate(hall)
    ok(th > tq * 3, "시끄러운 곳에서 임계값이 크게 올라간다",
       f"{tq:.3f} → {th:.3f}")

    # 같은 소리가 환경에 따라 다르게 판정되어야 한다 — 보정의 의미
    noise = frames([("quiet", 200), ("noise", 900), ("quiet", 900)])
    ok(len(run(noise, threshold=tq)) > 0 and run(noise, threshold=th) == [],
       "전시장 소음(0.05)은 조용한 방 기준에선 말소리, 전시장 기준에선 배경음")

    ok(Vad().calibrate([]) == FLOOR, "보정할 소리가 없으면 바닥값을 쓴다")
    ok(Vad().calibrate([0.0] * 50) == FLOOR, "완전 무음실에서도 0 으로 내려가지 않는다",
       "0 이면 모든 프레임이 말소리가 된다")
    ok(CALIBRATE_MS >= 500, "보정에 최소 0.5초는 듣는다", f"{CALIBRATE_MS}ms")

    # ── §4 끼어들기 ────────────────────────────────────────────────
    ok("lipsync" in CANCEL_ON_BARGEIN,
       "★ 끼어들기가 립싱크 층까지 멈춘다 (§4)",
       "빠지면 소리 없이 혼자 떠드는 얼굴이 된다")
    ok("tts_playback" in CANCEL_ON_BARGEIN and "llm_stream" in CANCEL_ON_BARGEIN,
       "TTS 재생과 LLM 스트림도 함께 멈춘다")

    s = Session().to("listening").to("thinking").start_speaking()
    r = s.heard(900, level=1.0)
    ok(r["interrupted"], "말하는 중 900ms 발화는 끼어들기다")
    ok(set(r["cancelled"]) == set(CANCEL_ON_BARGEIN),
       "끼어들면 목록의 것이 하나도 빠짐없이 취소된다",
       f"{len(r['cancelled'])}개")
    ok(s.running == set(), "취소 후 진행 중 작업이 남아 있지 않다")
    ok(s.fade_ms == FADE_MS, "멈춤은 페이드아웃이다 (§4)", f"{FADE_MS}ms")
    ok(FADE_MS <= 200, "페이드가 너무 길면 끼어든 느낌이 안 난다")
    ok(s.state == "listening", "끼어들기 후 상태는 듣는 중")
    ok(s.mic_open, "마이크는 내내 열려 있다 (§4 ①)")

    # 맞장구는 끼어들기가 아니다
    s2 = Session().to("listening").to("thinking").start_speaking()
    r2 = s2.heard(300, level=1.0)
    ok(not r2["interrupted"] and r2["reason"] == "backchannel",
       "300ms \"음—\" 은 맞장구다 — 멈추지 않는다")
    ok(s2.state == "speaking", "맞장구 뒤에도 계속 말한다")
    ok(s2.running == set(CANCEL_ON_BARGEIN), "맞장구는 아무것도 취소하지 않는다")
    ok(is_backchannel(BACKCHANNEL_MS - 1) and not is_backchannel(BACKCHANNEL_MS),
       f"경계가 {BACKCHANNEL_MS}ms 다")

    # 자기 목소리 차단
    s3 = Session().to("listening").to("thinking").start_speaking()
    r3 = s3.heard(900, level=0.2)
    ok(not r3["interrupted"] and r3["reason"] == "echo",
       "★ 스피커 되울림에 자기가 끼어들지 않는다 (§4 ②)",
       "없으면 첫 문장에서 스스로 멈춘다")
    ok(is_self_echo(0.2, True) and not is_self_echo(0.2, False),
       "말하고 있지 않을 때는 같은 소리를 되울림으로 보지 않는다")
    ok(not is_self_echo(0.9, True), "큰 소리는 되울림이 아니다",
       f"천장 {ECHO_CEILING}")

    # 듣는 중에는 끼어들 것이 없다
    ok(not should_interrupt("listening", 900), "듣는 중에는 끼어들기가 성립하지 않는다")
    ok(should_interrupt("thinking", 900), "생각하는 중에도 끼어들 수 있다")

    # ── §6 상태 기계 ───────────────────────────────────────────────
    ok(all(d in STATES for ds in ALLOWED.values() for d in ds),
       "전이표의 목적지가 전부 알려진 상태다")
    ok(all(can(a, b) for a, b in BARGE_IN),
       "끼어들기 전이가 전이표에 실제로 있다")
    try:
        Session().to("speaking")
        bad = True
    except ValueError:
        bad = False
    ok(not bad, "허용되지 않는 전이는 예외를 낸다 (idle → speaking)")

    # ── 보정 창에 말이 섞여도 임계가 말소리 위로 올라가지 않는다 (실측에서 잡힘) ──
    v = Vad(); thr = v.calibrate([0.0] * 20 + [0.4] * 30)          # 창의 60% 가 말
    ok(thr < 0.4, "★ 보정 창에 말이 섞여도 임계는 말소리 아래", f"{thr:.3f}")
    ok(any(e[1] == START for e in run([0.4] * 20, threshold=thr)), "  그 임계로 말이 잡힌다")

    # ── 스트림이 끝나면 침묵을 기다리지 않는다 ──────────────────────────────
    ev = run([0.5] * 30, threshold=0.1)                       # 말하다가 파일이 끝남
    ok(ev and ev[-1][1] == END, "★ 스트림 끝에서 발화 중이면 END 를 낸다 (finish)", f"{ev[-1] if ev else ev}")
    ok(Vad(threshold=0.1).finish() is None, "  발화 중이 아니면 finish 는 조용하다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
