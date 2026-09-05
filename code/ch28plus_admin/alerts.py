# -*- coding: utf-8 -*-
"""
Ch28+ — 콘솔의 첫 화면은 숫자가 아니라 "지금 이상한 것" 이어야 한다

기존 콘솔은 사용자 수 · 퍼널 · 최근 산출물을 보여준다. 전부 맞는 지표인데
**오늘 무엇을 할지는 알려주지 않는다.** 운영자는 매일 아침 그 화면을 보고
"음, 괜찮네" 하고 닫는다. 그리고 사흘 뒤에 큐가 멈춰 있었다는 것을 안다.

이 파일은 같은 데이터에서 **행동을 뽑는다.**

세 가지 규칙을 지킨다.

  ① **다음 행동이 없는 경보는 만들지 않는다.**
     "실패율 12%" 는 지표다. "실패 8건 중 7건이 같은 오류 — 로그를 보라" 가 경보다.
  ② **조용한 화면과 죽은 화면을 구분한다.**
     경보가 없으면 "이상 없음" 과 **마지막 점검 시각** 을 같이 보여준다.
  ③ **소리와 얼굴은 로그에 안 남는다.**
     그래서 길이·무음 같은 *산출물 자체의* 이상을 따로 본다 (Ch28+ §1).

    python alerts.py      합성 데이터로 경보를 뽑아 본다
"""
CRIT, WARN, INFO = "crit", "warn", "info"

# 기준값. 전부 이 책 본문에서 온 것이고, 근거는 각 항목에 적었다.
STUCK_SECONDS = 900          # 렌더 하나가 4분(Ch06)이므로 15분이면 확실히 멈춘 것
FAIL_RATE = 0.20             # 다섯 건에 하나가 실패하면 원인이 있다
P95_BUDGET_MS = 2000         # Ch07 — 실시간 트랙의 지연 예산
SILENT_SECONDS = 0.3         # 이보다 짧은 산출물은 사실상 무음이다
LONG_RATIO = 3.0             # 텍스트 길이 대비 음성이 이만큼 길면 이상하다


def _pct(n, d):
    return 0.0 if not d else n / d


def alert(level, title, detail, action):
    """**행동이 없으면 만들지 않는다** — 인자에 필수로 둔 이유다."""
    assert action, "다음 행동이 없는 경보는 지표이지 경보가 아니다"
    return {"level": level, "title": title, "detail": detail, "action": action}


# ── ① 큐가 멈췄는가 ─────────────────────────────────────────────────
def queue_alerts(jobs, now, stuck_seconds=STUCK_SECONDS):
    out = []
    stuck = [j for j in jobs if j.get("state") == "running"
             and now - (j.get("started") or now) > stuck_seconds]
    if stuck:
        mins = int((now - min(j["started"] for j in stuck)) / 60)
        out.append(alert(CRIT, "큐가 멈췄다",
                         f"{len(stuck)}건이 {mins}분째 처리 중 — 워커가 죽었을 수 있다",
                         "recover() 를 돌려 대기로 되돌리고 워커 로그를 보라"))
    waiting = [j for j in jobs if j.get("state") == "pending"]
    if len(waiting) >= 10:
        out.append(alert(WARN, "대기가 쌓인다",
                         f"대기 {len(waiting)}건 — 처리보다 유입이 빠르다",
                         "워커를 늘리거나 접수를 잠시 닫아라"))

    done = [j for j in jobs if j.get("state") in ("done", "failed")]
    failed = [j for j in done if j["state"] == "failed"]
    rate = _pct(len(failed), len(done))
    if len(done) >= 5 and rate >= FAIL_RATE:
        top = {}
        for j in failed:
            k = (j.get("error") or "알 수 없음")[:40]
            top[k] = top.get(k, 0) + 1
        worst, n = max(top.items(), key=lambda kv: kv[1])
        out.append(alert(CRIT, "실패율이 높다",
                         f"{len(failed)}/{len(done)} 실패 ({rate:.0%}) · "
                         f"그중 {n}건이 같은 오류 — “{worst}”",
                         "같은 오류가 몰려 있으면 원인은 하나다. 그 하나를 먼저 보라"))
    return out


# ── ② 지연이 예산을 넘는가 ──────────────────────────────────────────
def latency_alerts(gen_ms_list, budget_ms=P95_BUDGET_MS):
    if len(gen_ms_list) < 5:
        return []
    s = sorted(gen_ms_list)
    p95 = s[min(len(s) - 1, int(len(s) * 0.95))]
    med = s[len(s) // 2]
    if p95 <= budget_ms:
        return []
    # 평균이 아니라 p95 를 보는 이유 — 평균은 꼬리를 감춘다
    return [alert(WARN if p95 < budget_ms * 2 else CRIT, "지연이 예산을 넘는다",
                  f"p95 {p95}ms · 중앙값 {med}ms (예산 {budget_ms}ms)",
                  "중앙값이 멀쩡한데 p95 만 나쁘면 특정 입력이 원인이다 — "
                  "가장 느린 건의 입력을 보라")]


# ── ③ 산출물 자체의 이상 — 로그에는 안 남는다 (§1) ───────────────────
def output_alerts(gens):
    """소리는 로그로 알 수 없다. **길이로 안다.**"""
    out = []
    silent = [g for g in gens if (g.get("audio_sec") or 0) < SILENT_SECONDS]
    if silent:
        out.append(alert(CRIT, "사실상 무음인 산출물",
                         f"{len(silent)}건이 {SILENT_SECONDS}초 미만 — "
                         "성공으로 기록됐지만 소리가 없다",
                         "미리듣기로 직접 들어 보라. TTS 는 빈 문자열에도 성공을 반환한다"))
    stretched = [g for g in gens
                 if g.get("text") and (g.get("audio_sec") or 0)
                 > len(g["text"]) / 5.0 * LONG_RATIO]
    if stretched:
        out.append(alert(WARN, "글자 수에 비해 너무 긴 음성",
                         f"{len(stretched)}건 — 태그가 그대로 읽혔을 수 있다",
                         "Ch03 §3 의 정규화가 빠졌는지 보라"))
    return out


# ── ④ 보안 — 민감 잡이 밖으로 나가려 했는가 (Ch28 §6) ────────────────
def placement_alerts(denied_remote_claims):
    if not denied_remote_claims:
        return []
    return [alert(INFO, "민감 잡이 원격 배정에서 거절됐다",
                  f"{denied_remote_claims}건 — 게이트가 동작했다",
                  "정상이다. 다만 이 수가 계속 늘면 로컬 워커가 모자란 것이다")]


# ── 모아서 ──────────────────────────────────────────────────────────
ORDER = {CRIT: 0, WARN: 1, INFO: 2}


def collect(*, jobs=(), now=0.0, gen_ms=(), gens=(), denied_remote=0):
    out = (queue_alerts(list(jobs), now) + latency_alerts(list(gen_ms))
           + output_alerts(list(gens)) + placement_alerts(denied_remote))
    return sorted(out, key=lambda a: ORDER[a["level"]])


def summarize(alerts, checked_at):
    """**조용한 화면과 죽은 화면을 구분한다.**

    경보가 0건일 때 빈 화면을 보여주면 운영자는 그것이 '정상' 인지
    '수집이 멈춘 것' 인지 알 수 없다. 마지막 점검 시각을 반드시 같이 낸다.
    """
    c = sum(1 for a in alerts if a["level"] == CRIT)
    w = sum(1 for a in alerts if a["level"] == WARN)
    if c:
        head = f"확인이 필요한 것 {c}건"
    elif w:
        head = f"지켜볼 것 {w}건"
    else:
        head = "이상 없음"
    return {"headline": head, "crit": c, "warn": w,
            "total": len(alerts), "checked_at": checked_at}


def _demo():
    now = 10_000.0
    jobs = [{"state": "running", "started": now - 1800},
            {"state": "running", "started": now - 30},
            {"state": "failed", "error": "CUDA out of memory"},
            {"state": "failed", "error": "CUDA out of memory"},
            {"state": "failed", "error": "ffmpeg not found"},
            {"state": "done"}, {"state": "done"}, {"state": "done"}]
    gens = [{"text": "안녕하세요 반갑습니다", "audio_sec": 1.8},
            {"text": "볼넷은 네 번 공을 고르는 것입니다", "audio_sec": 0.05},
            {"text": "짧게", "audio_sec": 9.0}]
    a = collect(jobs=jobs, now=now, gen_ms=[400, 520, 610, 480, 3900, 520],
                gens=gens, denied_remote=2)
    s = summarize(a, checked_at="10:42")
    print()
    print(f"  {s['headline']}   (마지막 점검 {s['checked_at']})")
    print()
    for x in a:
        print(f"  [{x['level']:4}] {x['title']}")
        print(f"         {x['detail']}")
        print(f"      → {x['action']}")
    print()
    print("  경보마다 **다음 행동** 이 붙어 있습니다. 없으면 그건 지표이지 경보가 아닙니다.")
    print()


if __name__ == "__main__":
    _demo()
