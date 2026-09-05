# -*- coding: utf-8 -*-
"""
Ch04 — 소스 이미지와 드라이버 영상의 조건, 그리고 그 판정 기준

**이 파일에는 이미지가 들어오지 않는다.** 숫자만 받아서 통과·경고를 낸다.
그래서 사진 없이도 테스트할 수 있고, 기준을 바꾸면 여기만 고치면 된다.

기준값의 출처는 전부 Ch04 본문이다. 근거 없이 정한 값은 하나도 없고,
근거가 약한 것은 `WEAK` 로 표시해 두었다 — **모르는 것을 아는 척하지 않는다.**
"""

WEAK = "근거 약함 — 저자 경험치"

# ── 소스 이미지 (§2) ─────────────────────────────────────────────────
SOURCE = {
    "face_ratio":  {"min": 0.20, "good": 0.35,
                    "why": "얼굴이 화면에서 차지하는 비율이 해상도 자체보다 중요하다 (§2)",
                    "fix": "얼굴이 더 큰 사진을 쓰거나 크롭하세요"},
    "faces":       {"exact": 1,
                    "why": "여럿이면 어느 얼굴을 쓸지 파이프라인이 임의로 고른다",
                    "fix": "한 사람만 나오게 크롭하세요"},
    "brightness":  {"min": 60, "max": 200,
                    "why": "밝고 고른 조명 (§2)",
                    "fix": "너무 어둡거나 날아간 사진은 입 주변 디테일이 없다"},
    "evenness":    {"min": 0.35,
                    "why": "한쪽만 밝은 조명은 입 주변에 그림자를 만든다 (§2)",
                    "fix": "정면 조명으로 다시 찍거나 다른 사진을 쓰세요", "note": WEAK},
    "clipping":    {"max": 0.05,
                    "why": "하이라이트가 날아가면 그 자리에는 정보가 없다",
                    "fix": "노출을 낮춰 다시 찍으세요"},
    "symmetry":    {"min": 0.55,
                    "why": "정면 (§2). 좌우 대칭도는 정면성의 대리 지표다",
                    "fix": "옆을 보는 사진은 결과가 무너집니다", "note": WEAK},
    "min_side":    {"min": 256,
                    "why": "512×512 로 처리하므로 그 아래는 확대가 된다 (§2)",
                    "fix": "더 큰 원본을 찾으세요"},
}

# ── 드라이버 영상 (§3) ───────────────────────────────────────────────
DRIVER = {
    # 하한은 0.40 이었다가 0.22 로 내렸다(2026-09-05). 얼굴 23.5% 짜리 테라피스트 드라이버가 이 기준에 걸렸는데
    # 리타게팅 결과는 셋 중 가장 좋았다(§5 실측) — LivePortrait 가 드라이버 얼굴을 잘라 쓰므로 원본 화면 비율은
    # 립싱크(Ch11) 단계만큼 중요하지 않다. 0.40 은 '경고선' 으로 남긴다.
    "face_ratio":  {"min": 0.22, "good": 0.40,
                    "why": "클로즈업일수록 좋다 (§3). 미디엄샷은 립싱크 단계의 입 모양 해상도가 무너진다",
                    "fix": "얼굴이 화면을 꽉 채우는 영상으로 바꾸세요 — "
                           "'싱크가 안 맞는다' 는 착각의 가장 흔한 원인"},
    "motion":      {"max": 0.25,
                    "why": "차분해야 한다 (§3). 고개를 크게 흔들면 소스로 옮길 때 무너진다",
                    "fix": "또박또박 정면을 보고 말하는 영상을 쓰세요", "note": WEAK},
    # 값은 "드라이버 길이 ÷ 음성 길이". 1.0 이면 딱 같은 길이다.
    "duration_ratio": {"min": 1.0,
                       "why": "음성보다 길어야 한다 (§3). 짧으면 이어붙인 이음매에서 튄다",
                       "fix": "더 긴 클립을 쓰거나 음성을 나눠 처리하세요"},
}

OK, WARN, FAIL = "OK", "WARN", "FAIL"


def _judge(name, spec, value):
    if value is None:
        return (WARN, name, value, "측정하지 못했다")
    if "exact" in spec:
        good = value == spec["exact"]
        return ((OK, name, value, "") if good else (FAIL, name, value, spec["fix"]))
    if "min" in spec and value < spec["min"]:
        return (FAIL, name, value, spec["fix"])
    if "max" in spec and value > spec["max"]:
        return (FAIL, name, value, spec["fix"])
    if "good" in spec and value < spec["good"]:
        return (WARN, name, value, spec["fix"])
    return (OK, name, value, "")


def grade(metrics: dict, table: dict) -> list:
    """(수준, 항목, 값, 조언) 목록. 나쁜 것부터 정렬한다."""
    rows = [_judge(k, table[k], metrics.get(k)) for k in table if k in metrics
            or table[k].get("required", True)]
    order = {FAIL: 0, WARN: 1, OK: 2}
    return sorted(rows, key=lambda r: order[r[0]])


def verdict(rows) -> str:
    if any(r[0] == FAIL for r in rows):
        return FAIL
    return WARN if any(r[0] == WARN for r in rows) else OK


def explain(name: str, table: dict) -> str:
    return table[name]["why"]
