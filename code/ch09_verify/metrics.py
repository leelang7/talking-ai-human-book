# -*- coding: utf-8 -*-
"""
Ch09 — 적중률을 어떻게 읽을 것인가

`verify_sync.py` 가 재는 것은 *활발도 상위 N프레임 중 몇 개가 발화구간에
들어 있는가* 다. 15/15 면 100% 다. 좋아 보인다.

**그런데 그 숫자만으로는 아무것도 알 수 없다.**

발화가 타임라인의 90% 를 차지하면 **아무 프레임이나 찍어도 90%** 다.
이 장이 §2 에서 *"잘못된 지표는 아무것도 측정하지 않는 것보다 나쁘다"* 고
했는데, 기준선 없는 적중률이 정확히 그 종류다.

그래서 이 파일은 세 가지를 같이 낸다.

    ① 적중률        상위 N프레임 중 발화구간 안에 든 비율
    ② 우연 기준선    발화가 차지하는 시간 비율 — **아무 프레임이나의 기댓값**
    ③ 조용한 구간 활발도   ①이 못 잡는 것을 잡는다

③이 필요한 이유가 이 파일의 요점이다. **말하는 내내 입을 무의미하게 떠는
모델은 ①을 만점으로 통과한다.** 상위 프레임이 전부 발화구간에 있으니까.
소리와 무관하게 떨어도 그렇다. 그것을 가르는 것은 *조용할 때 닫혀 있는가* 다.

    python metrics.py       세 가지 경우를 나란히 채점
"""
CHANCE_MARGIN = 1.25        # 우연보다 이만큼은 나아야 한다
QUIET_MAX = 0.35            # 조용한 구간 활발도가 발화 구간의 이 배를 넘으면 실패
PASS_RATE = 0.80            # §7 의 기준


def speech_ratio(spans, duration: float) -> float:
    """발화가 차지하는 시간 비율 = **아무 프레임이나 찍었을 때의 기댓값.**

    구간이 겹쳐 있어도 두 번 세지 않는다. 겹친 구간을 그냥 더하면
    기준선이 1 을 넘어 버리고, 그러면 어떤 결과도 '우연 이하' 가 된다.
    """
    if duration <= 0 or not spans:
        return 0.0
    merged = []
    for s, e in sorted((min(a, b), max(a, b)) for a, b in spans):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    total = sum(min(e, duration) - max(s, 0.0) for s, e in merged
                if e > 0 and s < duration)
    return max(0.0, min(1.0, total / duration))


def in_speech(t: float, spans) -> bool:
    return any(s <= t <= e for s, e in spans)


def hit_rate(acts, fps: float, spans, top: int) -> float:
    """활발도 상위 `top` 프레임 중 발화구간에 든 비율."""
    if not acts or top <= 0:
        return 0.0
    top = min(top, len(acts))
    order = sorted(range(len(acts)), key=lambda i: acts[i], reverse=True)[:top]
    return sum(in_speech(i / fps, spans) for i in order) / top


def quiet_activity_ratio(acts, fps: float, spans) -> float:
    """조용한 구간의 평균 활발도 ÷ 발화구간의 평균 활발도.

    **이것이 ① 이 못 잡는 것을 잡는다.** 소리와 무관하게 입을 계속 떠는
    모델은 이 값이 1 에 가깝다. 제대로 따라가는 모델은 0 에 가깝다.
    조용한 구간이 없으면 판단하지 않는다(None).
    """
    loud = [a for i, a in enumerate(acts) if in_speech(i / fps, spans)]
    quiet = [a for i, a in enumerate(acts) if not in_speech(i / fps, spans)]
    if not loud or not quiet:
        return None
    m_loud = sum(loud) / len(loud)
    if m_loud <= 0:
        return None
    return (sum(quiet) / len(quiet)) / m_loud


def evaluate(acts, fps: float, spans, top: int = 15, duration=None) -> dict:
    """세 지표를 한 번에. **판정은 셋을 다 보고 내린다.**"""
    duration = duration if duration is not None else (len(acts) / fps if fps else 0.0)
    base = speech_ratio(spans, duration)
    rate = hit_rate(acts, fps, spans, top)
    quiet = quiet_activity_ratio(acts, fps, spans)
    lift = (rate / base) if base > 0 else None

    reasons = []
    if rate < PASS_RATE:
        reasons.append(f"적중률 {rate:.0%} < 기준 {PASS_RATE:.0%}")
    if lift is not None and lift < CHANCE_MARGIN:
        reasons.append(f"우연 기준선 {base:.0%} 대비 {lift:.2f}배 — 우연과 구분 안 됨")
    if quiet is not None and quiet > QUIET_MAX:
        reasons.append(f"조용한 구간 활발도가 발화구간의 {quiet:.0%} — 계속 떨고 있다")

    return {"rate": rate, "baseline": base, "lift": lift, "quiet_ratio": quiet,
            "top": min(top, len(acts)), "duration": duration,
            "pass": not reasons, "reasons": reasons}


def explain(r: dict) -> str:
    lines = [f"  적중률        {r['rate']:.0%}  (상위 {r['top']}프레임)",
             f"  우연 기준선    {r['baseline']:.0%}  ← 아무 프레임이나 찍었을 때"]
    if r["lift"] is not None:
        lines.append(f"  우연 대비      {r['lift']:.2f}배")
    if r["quiet_ratio"] is not None:
        lines.append(f"  조용한 구간    발화구간의 {r['quiet_ratio']:.0%}")
    lines.append("  판정          " + ("통과" if r["pass"] else "실패"))
    lines += [f"                · {x}" for x in r["reasons"]]
    return "\n".join(lines)


# ── 시연용 합성 데이터 ───────────────────────────────────────────────
FPS = 30.0


def _make(kind, seconds=10.0, speech=((1.0, 4.0), (5.5, 9.0))):
    """세 종류의 가짜 결과. 난수를 쓰지 않아 값이 매번 같다."""
    n = int(seconds * FPS)
    acts = []
    for i in range(n):
        t = i / FPS
        talking = in_speech(t, speech)
        if kind == "good":                       # 말할 때만, 그리고 들쭉날쭉
            acts.append((0.3 + 0.7 * ((i * 7) % 11) / 10) if talking else 0.02)
        elif kind == "always":
            # 말할 때 더 크게 움직이기는 한다. **조용할 때 안 닫힐 뿐이다.**
            # 그래서 적중률과 우연 대비는 통과한다 — ③ 만 이것을 잡는다.
            acts.append((0.85 + 0.15 * ((i * 7) % 11) / 10) if talking
                        else (0.5 + 0.1 * ((i * 5) % 7) / 6))
        else:                                    # 발화가 거의 전부인 파일
            acts.append((0.5 + 0.5 * ((i * 3) % 9) / 8) if talking else 0.4)
    return acts


def _demo():
    seconds = 10.0
    cases = [
        ("잘 맞는 결과", _make("good"), ((1.0, 4.0), (5.5, 9.0))),
        ("조용할 때 안 닫히는 모델", _make("always"), ((1.0, 4.0), (5.5, 9.0))),
        ("발화가 95% 인 파일", _make("good", speech=((0.2, 9.7),)), ((0.2, 9.7),)),
    ]
    print()
    for label, acts, spans in cases:
        r = evaluate(acts, FPS, spans, top=15, duration=seconds)
        print(f"  ── {label}")
        print(explain(r))
        print()
    print("  둘째는 적중률도 우연 대비도 통과합니다 — ③ 만 잡습니다.")
    print("  셋째는 적중률 100% 인데 우연 기준선이 95% 라 아무 의미가 없습니다.")
    print("  **적중률 하나만 보면 둘 다 통과시킵니다.**")
    print()


if __name__ == "__main__":
    _demo()
