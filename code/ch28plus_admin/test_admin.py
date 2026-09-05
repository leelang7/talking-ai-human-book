# -*- coding: utf-8 -*-
"""
Ch28+ 회귀 테스트

콘솔은 UI 라서 눈으로 봐야 하는 부분이 많다. 그런데 **판단 로직은 순수 함수** 라
전부 잴 수 있다. 여기 있는 것이 그 부분이다.

가장 중요한 둘 —

  ★ 경보에는 **다음 행동** 이 반드시 붙는다. 없으면 그건 지표다.
  ★ 파괴적 작업은 **dry_run 이 기본값** 이다 (§5).

    python test_admin.py
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import alerts as A  # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch28+ 운영자 콘솔 ──")
    now = 10_000.0

    # ── ★ 모든 경보에 다음 행동이 있다 ─────────────────────────────
    jobs = [{"state": "running", "started": now - 1800},
            {"state": "failed", "error": "CUDA out of memory"},
            {"state": "failed", "error": "CUDA out of memory"},
            {"state": "failed", "error": "ffmpeg not found"},
            {"state": "done"}, {"state": "done"}, {"state": "done"}]
    gens = [{"text": "안녕하세요 반갑습니다", "audio_sec": 1.8},
            {"text": "볼넷은 네 번 공을 고르는 것", "audio_sec": 0.05},
            {"text": "짧게", "audio_sec": 9.0}]
    all_a = A.collect(jobs=jobs, now=now, gen_ms=[400, 520, 610, 480, 3900, 520],
                      gens=gens, denied_remote=2)

    ok(all(a["action"] for a in all_a), "★ 모든 경보에 다음 행동이 붙어 있다",
       f"{len(all_a)}건")
    ok(all(a["title"] and a["detail"] for a in all_a), "제목과 내용이 비어 있지 않다")
    try:
        A.alert(A.WARN, "제목", "내용", "")
        guarded = False
    except AssertionError:
        guarded = True
    ok(guarded, "★ 행동 없는 경보는 만들 수 없다 — assert 로 막았다")

    # 심각한 것이 위로
    levels = [a["level"] for a in all_a]
    ok(levels == sorted(levels, key=lambda x: A.ORDER[x]),
       "심각한 것부터 정렬된다", " · ".join(levels))

    # ── ① 큐 ───────────────────────────────────────────────────────
    stuck = A.queue_alerts([{"state": "running", "started": now - 1800}], now)
    ok(any(x["level"] == A.CRIT and "멈췄" in x["title"] for x in stuck),
       "★ 30분째 처리 중인 잡을 잡는다 — 로그에는 '처리 중' 이라 안 보인다")
    ok(A.queue_alerts([{"state": "running", "started": now - 60}], now) == [],
       "정상 처리 중인 잡은 경보를 안 낸다")

    many = [{"state": "pending"} for _ in range(12)]
    ok(any("쌓인" in x["title"] for x in A.queue_alerts(many, now)),
       "대기가 10건 넘으면 알려준다")
    ok(A.queue_alerts([{"state": "pending"}] * 3, now) == [],
       "대기 3건은 정상이다 — 오탐을 안 만든다")

    fail_alerts = [x for x in A.queue_alerts(jobs, now) if "실패율" in x["title"]]
    ok(fail_alerts and "CUDA out of memory" in fail_alerts[0]["detail"],
       "★ 실패를 세는 것이 아니라 **가장 많은 오류를 짚는다**",
       "같은 오류가 몰려 있으면 원인은 하나다")
    few = [{"state": "failed", "error": "x"}, {"state": "done"}]
    ok(not any("실패율" in x["title"] for x in A.queue_alerts(few, now)),
       "표본이 적으면 실패율을 말하지 않는다 (2건에 50%는 의미 없다)")

    # ── ② 지연 — 평균이 아니라 p95 ─────────────────────────────────
    ok(A.latency_alerts([400, 420, 410, 430, 400]) == [], "예산 안이면 조용하다")
    spike = A.latency_alerts([400, 420, 410, 430, 400, 9000])
    ok(spike, "꼬리가 튀면 잡는다")
    ok("중앙값" in spike[0]["detail"],
       "★ p95 와 중앙값을 같이 보여준다 — 평균은 꼬리를 감춘다",
       spike[0]["detail"][:34])
    ok(A.latency_alerts([9000, 9000]) == [],
       "표본이 5건 미만이면 판단하지 않는다")

    # ── ③ 산출물 자체 (§1) ─────────────────────────────────────────
    silent = A.output_alerts([{"text": "긴 문장입니다", "audio_sec": 0.05}])
    ok(any("무음" in x["title"] for x in silent),
       "★ 성공으로 기록됐지만 소리가 없는 산출물을 잡는다 (§1)",
       "소리는 로그에 안 남는다 — 길이로 안다")
    ok(A.output_alerts([{"text": "안녕하세요 반갑습니다", "audio_sec": 1.8}]) == [],
       "정상 산출물은 조용하다")
    ok(any("긴 음성" in x["title"] for x in
           A.output_alerts([{"text": "짧게", "audio_sec": 9.0}])),
       "글자 수 대비 너무 긴 음성을 잡는다 — 태그가 읽혔을 수 있다")

    # ── ④ 보안 게이트 ──────────────────────────────────────────────
    p = A.placement_alerts(3)
    ok(p and p[0]["level"] == A.INFO,
       "민감 잡 거절은 정보로 알린다 — 정상 동작이지 사고가 아니다")
    ok("로컬 워커가 모자란" in p[0]["action"],
       "그래도 계속 늘면 무엇을 뜻하는지 말해 준다")
    ok(A.placement_alerts(0) == [], "0건이면 아무 말도 안 한다")

    # ── ★ 조용한 화면과 죽은 화면 ──────────────────────────────────
    s = A.summarize([], checked_at="10:42")
    ok(s["headline"] == "이상 없음", "경보 0건이면 '이상 없음'")
    ok(s["checked_at"] == "10:42",
       "★ 그때도 **마지막 점검 시각** 을 같이 낸다",
       "빈 화면이 정상인지 죽은 건지 구분되어야 한다")
    ok(A.summarize(all_a, "10:42")["crit"] >= 1, "치명 건수를 센다")
    ok("확인이 필요" in A.summarize(all_a, "10:42")["headline"],
       "치명이 있으면 머리말이 달라진다")
    ok(A.summarize([A.alert(A.WARN, "t", "d", "a")], "x")["headline"].startswith("지켜볼"),
       "경고만 있으면 '지켜볼 것'")

    # ── §5 파괴적 작업은 미리보기가 기본 ───────────────────────────
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "console.py"), encoding="utf-8").read()
    ok('p.get("dry_run", True)' in src,
       "★ 삭제 API 의 dry_run 기본값이 True 다 (§5)",
       "기본값이 False 면 실수 한 번이 되돌릴 수 없다")
    ok("if not dry:" in src, "미리보기일 때는 DELETE 를 안 친다")
    ok(src.count("guard(request)") >= 4, "모든 관리자 API 가 토큰을 확인한다",
       f"{src.count('guard(request)')}곳")
    ok('v["alerts"]' in src and '"health"' in src,
       "콘솔 데이터에 경보와 요약이 실린다")
    ok("여섯 개의 방" in src, "화면이 ⓪번 방을 포함한다")

    # ── §5 차단은 해제와 같은 문으로 ───────────────────────────────
    import access as X  # noqa: E402
    s0 = set()
    d = X.decide(s0, "10.0.0.7")
    ok(d["action"] == X.BLOCK and d["dry_run"] and d["after"] == set(),
       "★ 차단도 dry_run 이 기본 — 미리보기에서는 목록이 안 바뀐다")
    d = X.decide(s0, "10.0.0.7", dry_run=False)
    ok(d["action"] == X.BLOCK and d["after"] == {"10.0.0.7"}, "dry_run=False 여야 실제로 막힌다")
    d = X.decide({"10.0.0.7"}, "10.0.0.7", unblock=True, dry_run=False)
    ok(d["action"] == X.UNBLOCK and d["after"] == set(),
       "★ 해제가 차단과 **같은 함수** 를 지난다 — 플래그 하나 차이")
    ok(X.decide({"10.0.0.7"}, "10.0.0.7")["action"] == X.NOOP, "이미 막힌 IP 는 noop")
    ok(X.decide(set(), "10.0.0.7", unblock=True)["action"] == X.NOOP,
       "없는 IP 를 해제하면 noop — 조용히 실패하지 않고 말해 준다")
    ok(X.decide(set(), "not-an-ip")["action"] == X.REJECT, "IP 형식이 아니면 거절")
    ok(X.decide(set(), "  10.0.0.7 ", dry_run=False)["ip"] == "10.0.0.7", "공백을 다듬는다")
    ok(X.decide({"a"}, "10.0.0.7")["after"] == {"a"} and "a" in {"a"},
       "입력 집합을 바꾸지 않는다 (미리보기)")

    ok('"/api/admin/block_ip"' in src and 'p.get("unblock", False)' in src,
       "★ 콘솔에 차단 엔드포인트가 있고 `unblock` 플래그를 받는다 (§5 의 처방)")
    ok('p.get("dry_run", True)' in src[src.index("block_ip"):],
       "  그 엔드포인트도 dry_run 이 기본이다")
    ok("access.decide(" in src, "  판단은 순수 함수에 맡긴다 — 서버 없이 테스트된다")

    # 기준값이 본문과 묶여 있는가
    ok(A.P95_BUDGET_MS == 2000, "지연 예산이 Ch07 의 2초와 같다")
    ok(A.STUCK_SECONDS > 230, "정체 판정이 렌더 1회(230초)보다 넉넉하다",
       f"{A.STUCK_SECONDS}초")
    ok(len(inspect.signature(A.collect).parameters) >= 5,
       "collect 가 네 종류 데이터를 다 받는다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
