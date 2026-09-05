# -*- coding: utf-8 -*-
"""
Ch03+ 회귀 테스트 — GPU 없이 검사할 수 있는 부분

핵심은 둘이다.
  ★ 요청의 `dialect` 값이 **항상 유효한 어댑터** 로 간다 (서버가 요청마다 죽지 않는다)
  ★ 병합(merge)하면 전환이 **거절된다** — 15.0GB 와 3.2GB 를 가르는 한 줄

    python test_router.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from router import (ADAPTERS, DEFAULT, HotSwap, MergedError,  # noqa: E402
                    deploy_separately, select)

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch03+ 사투리 어댑터 라우팅 ──")

    # ── ① 라우팅 ───────────────────────────────────────────────────
    ok(set(ADAPTERS) == {"gs", "jl", "gw", "cc", "jj"},
       "★ 어댑터 코드가 §1 표의 **다섯** 개다 — 여섯째를 지어내지 않는다",
       " · ".join(ADAPTERS))
    ok(select("gs") == "gs", "코드는 그대로 통과")
    ok(select("JJ") == "jj" and select(" 경상 ") == "gs", "대소문자·공백·한글 이름을 받는다")
    ok(select("gyeongsang") == "gs", "영문 이름도 받는다")
    ok(DEFAULT is None and select(None) is None and select("") is None,
       "★ 값이 없으면 None = 어댑터 없음 = 베이스의 표준어 — 예외도, 지어낸 어댑터도 없다")
    ok(select("표준어") is None and select("xx") is None,
       "모르는 값도 None — 없는 어댑터를 만들어 내지 않는다")
    ok(all((select(k) is None) or (select(k) in ADAPTERS)
           for k in ("gs", "", None, "zzz", "  ", "JEJU")),
       "★ 어떤 입력이든 반환값은 유효한 코드이거나 None 이다")

    # ── ② 핫스왑 ───────────────────────────────────────────────────
    hs = HotSwap()
    for c in ("gs", "jl", "gw", "cc", "jj"):
        hs.load(c)
    ok(len(hs.loaded) == 5 and hs.active == "gs", "다섯을 동시에 얹고 첫 것이 활성")
    ok(hs.activate("jj") == "jj" and hs.active == "jj", "로드된 것 사이 전환은 즉시")
    ok(hs.load("jj") is hs and len(hs.loaded) == 5, "같은 어댑터를 다시 얹어도 중복되지 않는다")
    try:
        hs.activate("gs_v2"); bad = True
    except KeyError:
        bad = False
    ok(not bad, "로드 안 된 어댑터로는 전환할 수 없다")
    ok(hs.activate(None) is None and hs.active is None,
       "★ None 으로 전환하면 어댑터를 전부 끈다 — 표준어로 돌아간다")
    hs.activate("jj")
    try:
        hs.load("xx"); bad = True
    except KeyError:
        bad = False
    ok(not bad, "모르는 어댑터는 얹을 수 없다")

    # VRAM 셈법 — Ch03+ §3 의 숫자
    v = hs.vram_gb()
    ok(abs(v - (3.0 + 5 * 22.5 / 1024)) < 1e-9, "핫스왑 VRAM = 베이스 + 어댑터 5개",
       f"{v:.2f}GB")
    ok(deploy_separately(hs.loaded) == 15.0, "개별 배포 = 3.0GB × 5 = 15.0GB")
    ok(deploy_separately(hs.loaded) / v > 4.5, "★ 다섯 배 가까이 차이난다 (§3)",
       f"{deploy_separately(hs.loaded) / v:.1f}배")

    # ── 병합은 전환을 죽인다 ───────────────────────────────────────
    hs.merge()
    ok(hs.merged and hs.loaded == ["jj"], "병합하면 활성 하나만 남는다")
    try:
        hs.activate("gs"); bad = True
    except MergedError:
        bad = False
    ok(not bad, "★ 병합 후 전환은 거절된다 — 어댑터를 어댑터인 채로 둬야 핫스왑이 된다")
    try:
        hs.load("gw"); bad = True
    except MergedError:
        bad = False
    ok(not bad, "병합 후에는 새 어댑터도 못 얹는다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
