# -*- coding: utf-8 -*-
"""Ch06 회귀 테스트 — 프로파일 보고의 산술과 병목 판정."""
import contextlib
import io
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from profile_pipeline import report   # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


ENV = {"gpu": "테스트", "vram_gb": 12, "torch": "x", "os": "y", "python": "z"}


def run(stages, audio):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = report(stages, audio, ENV, note="테스트")
    return r, buf.getvalue()


def main():
    print("\n  ── Ch06 프로파일 보고 ──")
    # 저자 환경 — 립싱크 195.8 · 리타게팅 32.1 · mux 2 · TTS 0.5 / 음성 10.67초
    r, out = run([{"name": "TTS", "sec": 0.5}, {"name": "립싱크", "sec": 195.8},
                  {"name": "리타게팅", "sec": 32.1}, {"name": "mux", "sec": 2.0}], 10.67)
    ok(r["total_sec"] == 230.4 and r["rt_factor"] == 21.59, "★ 합계 230.4초 · 실시간 21.6배 (부록 C 와 같은 자릿수)", f"{r['total_sec']} / {r['rt_factor']}")
    ok("병목 : 립싱크 — 전체의 85%" in out, "★ 병목은 립싱크 85%", [l for l in out.splitlines() if "병목" in l][:1])
    ok("쏠려 있습니다" in out and "34.6초(15%)" in out, "  쏠림 안내 — 나머지 전부 0 이어도 34.6초(15%)", [l for l in out.splitlines() if "쏠려" in l][:1])
    r2, out2 = run([{"name": "A", "sec": 10}, {"name": "B", "sec": 9}, {"name": "C", "sec": 8}], 6.0)
    ok("분산돼 있습니다" in out2 and r2["rt_factor"] == 4.5, "  병목이 60% 아래면 '분산' 안내 · 27/6 = 4.5배")
    r3, out3 = run([], 0.0)
    ok(r3["total_sec"] == 0 and r3["rt_factor"] == 0 and "병목" not in out3, "  단계도 음성도 없으면 0 — 0 나누기 없음")
    ok(all(k in r for k in ("env", "audio_sec", "stages", "total_sec", "rt_factor", "note")), "  반환 키 여섯")
    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
