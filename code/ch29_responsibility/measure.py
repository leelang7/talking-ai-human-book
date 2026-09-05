# -*- coding: utf-8 -*-
"""
Ch29 §4 실측 — 생성 로그가 커지면 철회 역추적이 얼마나 걸리나.

GenLog 는 JSON Lines 한 파일 + 선형 탐색이다. "충분히 단순하다" 는 말은 어느 규모까지인가.
    N 건을 쓰고(append 시간) · 한 줄 크기 · retract(원본 해시) · expired(만료) 시간을 잰다.

    python measure.py    → _work/measure.json
"""
import json, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genlog import GenLog, sha_of

MARKS = {"visible": True, "metadata": True, "watermark": "id:0000"}


def run(n):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "gen.jsonl")
        t = [1_000_000.0]
        log = GenLog(path, clock=lambda: t[0])
        target = sha_of(b"face-of-target")
        t0 = time.perf_counter()
        for i in range(n):
            t[0] += 1
            src = target if i % 1000 == 0 else f"{i:016x}"        # 1/1000 이 철회 대상
            log.append(f"user-{i % 500}", f"consent-{i % 50}", [src], f"out/{i}.mp4",
                       "local_only", 30 if i % 3 else 90, MARKS)
        t_append = time.perf_counter() - t0
        size = os.path.getsize(path)
        t0 = time.perf_counter(); hits = log.retract(target); t_retract = time.perf_counter() - t0
        t0 = time.perf_counter(); exp = log.expired(now=t[0] + 40 * 86400); t_expired = time.perf_counter() - t0
        return {"n": n, "append_s": round(t_append, 2), "bytes_per_entry": round(size / n), "file_MB": round(size / 2**20, 2),
                "retract_hits": len(hits), "retract_s": round(t_retract, 3), "expired_hits": len(exp), "expired_s": round(t_expired, 3)}


def main():
    out = []
    print(f"  {'N':>8}  {'쓰기':>7}  {'줄 크기':>7}  {'파일':>8}  {'철회 검색':>9}  {'만료 검색':>9}")
    sizes = (1_000,) if "--quick" in sys.argv else (1_000, 10_000, 100_000)     # --quick: 게이트용(1초 안)
    for n in sizes:
        r = run(n); out.append(r)
        print(f"  {n:>8,}  {r['append_s']:>6.2f}s  {r['bytes_per_entry']:>6}B  {r['file_MB']:>6.2f}MB  {r['retract_s']:>8.3f}s  {r['expired_s']:>8.3f}s   (철회 {r['retract_hits']} · 만료 {r['expired_hits']:,})")
    if "--quick" not in sys.argv:                      # 빠른 점검은 근거 파일을 덮어쓰지 않는다
        json.dump({"measured": "2026-09-03", "runs": out}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work", "measure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  → _work/measure.json")


if __name__ == "__main__":
    main()
