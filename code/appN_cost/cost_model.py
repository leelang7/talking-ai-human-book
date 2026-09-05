# -*- coding: utf-8 -*-
"""
원가 모형 계산기 (부록 N)

세 트랙의 원가 구조가 근본적으로 다르다.
  Track A(품질) : 영상 길이에 비례하는 **가변비**. GPU 시간을 산다.
  Track B(실시간): 사용자 수에 비례하는 **가변비**. 렌더는 브라우저가 하므로 GPU 0.
  실사 실시간    : 동시 사용자에 비례하는 **고정비**. GPU 대수가 곧 정원.

요율(GPU 시급·API 단가)은 6개월이면 바뀐다. **숫자는 인자로 받고 구조만 코드에 둔다.**
부록 K 와 같은 원칙 — 바뀌는 것은 밖으로, 남는 것은 안으로.

실행:
    python cost_model.py                 # 기본 시나리오 3종
    python cost_model.py --help
"""
import argparse
import math

# ── 실측 상수 (부록 C) ────────────────────────────────────────────────
RT_FACTOR = 21.0      # Track A: 영상 1초당 GPU 21초 (RTX 4070 SUPER, 512x512, 30fps)
OPT_FACTOR = 3.0      # Ch06 최적화 상한 — 캐시·배치·반정밀도·fps 조정으로 2~3배


def track_a_unit_cost(video_sec, gpu_hourly, rt_factor=RT_FACTOR, optimized=False):
    """영상 1편의 GPU 원가. optimized=True면 Ch06 최적화 적용."""
    f = rt_factor / (OPT_FACTOR if optimized else 1.0)
    gpu_sec = video_sec * f
    return {"gpu_sec": round(gpu_sec), "gpu_min": round(gpu_sec / 60, 1),
            "cost": gpu_sec / 3600 * gpu_hourly}


def break_even(api_unit_price, gpu_hourly, video_sec, fixed_monthly=0.0,
               rt_factor=RT_FACTOR, optimized=False):
    """API 대행 vs 직접 구축의 손익분기 건수/월.

    직접 구축은 고정비(엔지니어 시간·유지보수·상시 인스턴스)가 먼저 들어간다.
    처리량이 적으면 API 가 싸고, 어느 지점을 넘으면 직접이 싸진다.
    그 교차점을 넘지 못할 서비스는 **직접 구축이 손해** 다.
    """
    unit = track_a_unit_cost(video_sec, gpu_hourly, rt_factor, optimized)["cost"]
    margin = api_unit_price - unit
    if margin <= 0:
        return {"unit_self": unit, "unit_api": api_unit_price, "n": None,
                "verdict": "직접 구축이 건당 원가에서 이미 진다 — API 를 쓰세요"}
    n = fixed_monthly / margin if fixed_monthly else 0.0
    return {"unit_self": unit, "unit_api": api_unit_price, "margin": margin,
            "n": math.ceil(n), "verdict": f"월 {math.ceil(n):,}건을 넘으면 직접 구축이 싸다"}


def track_b_monthly(mau, turns_per_user, llm_per_turn, tts_per_turn, server_monthly=0.0):
    """Track B 월 원가. GPU 0 — 렌더는 사용자 브라우저에서 일어난다(Ch05).

    서버가 만드는 것은 텍스트와 오디오뿐이므로 비용이 **사용자 수에 선형** 이다.
    """
    turns = mau * turns_per_user
    variable = turns * (llm_per_turn + tts_per_turn)
    total = variable + server_monthly
    return {"turns": turns, "variable": variable, "fixed": server_monthly,
            "total": total, "per_user": total / mau if mau else 0.0}


def realtime_gpu_count(concurrent_users, users_per_gpu=1.0):
    """실사 실시간(Ch11 §5)의 GPU 대수. **GPU 대수가 곧 동시 접속 정원이다.**

    users_per_gpu 는 실측으로 채워야 한다. 저자 환경 기준 약 1.
    스트리밍 우선 모델(부록 K §4)을 쓰면 이 값이 올라간다 — 그래도 무한하지 않다.
    """
    n = math.ceil(concurrent_users / users_per_gpu)
    return {"gpus": n, "users_per_gpu": users_per_gpu,
            "note": "이 값이 원가의 전부다. 브라우저 렌더 트랙은 여기가 0이다."}


def _fmt(v, cur):
    return f"{v:,.0f}{cur}"


def main():
    p = argparse.ArgumentParser(description="AI 휴먼 원가 모형 (부록 N)")
    p.add_argument("--gpu-hourly", type=float, default=1000, help="GPU 시급 (기본: 임의값 1000)")
    p.add_argument("--api-unit", type=float, default=500, help="API 영상 1편 단가")
    p.add_argument("--fixed-monthly", type=float, default=2_000_000, help="직접 구축 월 고정비")
    p.add_argument("--video-sec", type=float, default=60, help="영상 길이(초)")
    p.add_argument("--mau", type=int, default=1000)
    p.add_argument("--turns", type=int, default=20, help="사용자당 월 대화 턴")
    p.add_argument("--llm-turn", type=float, default=3, help="턴당 LLM 비용")
    p.add_argument("--tts-turn", type=float, default=2, help="턴당 TTS 비용")
    p.add_argument("--concurrent", type=int, default=50)
    p.add_argument("--cur", default="원")
    a = p.parse_args()
    cur = a.cur

    print("\n※ 요율은 전부 인자입니다. 실제 견적 시 현재 단가를 넣으세요.\n")

    print(f"[Track A] {a.video_sec:.0f}초 영상 1편")
    for label, opt in (("기본", False), ("최적화(Ch06)", True)):
        r = track_a_unit_cost(a.video_sec, a.gpu_hourly, optimized=opt)
        print(f"  {label:<14} GPU {r['gpu_min']:>6}분  →  {_fmt(r['cost'], cur)}")

    print(f"\n[손익분기] API {_fmt(a.api_unit, cur)}/편  vs  직접(고정비 {_fmt(a.fixed_monthly, cur)}/월)")
    b = break_even(a.api_unit, a.gpu_hourly, a.video_sec, a.fixed_monthly)
    print(f"  직접 건당 {_fmt(b['unit_self'], cur)} · API 건당 {_fmt(b['unit_api'], cur)}")
    print(f"  → {b['verdict']}")

    print(f"\n[Track B] MAU {a.mau:,} · 사용자당 {a.turns}턴  (GPU 0)")
    t = track_b_monthly(a.mau, a.turns, a.llm_turn, a.tts_turn)
    print(f"  총 {t['turns']:,}턴 · 월 {_fmt(t['total'], cur)} · 사용자당 {_fmt(t['per_user'], cur)}")

    print(f"\n[실사 실시간] 동시 {a.concurrent}명")
    g = realtime_gpu_count(a.concurrent)
    print(f"  필요 GPU {g['gpus']}장 — {g['note']}")

    print("\n한 줄: Track B 는 사용자에 비례하고, 실사 실시간은 **정원에 묶입니다.**\n")


if __name__ == "__main__":
    main()
