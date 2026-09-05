# -*- coding: utf-8 -*-
"""
Ch30 §5 실험 — 한 학생이 잡 열 개를 먼저 넣으면, 나머지 열아홉은 얼마나 기다리나.

    제출 순(FIFO)  : Ch28 의 Queue.claim
    학생별 순환     : ClassQueue.claim (이미 돈 잡이 가장 적은 학생 먼저)
    잡 하나 = 10초 음성 × 21배 = 210초 (Ch06 어림값) · GPU 한 장

    python fairness.py    → _work/fairness.json
"""
import json, os, statistics, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ch28_deploy"))
from jobqueue import Queue
from gpu_queue import ClassQueue

JOB_S = 210.0
STUDENTS = [f"s{i:02d}" for i in range(20)]


def run(cls):
    t = [0.0]
    with tempfile.TemporaryDirectory() as d:
        q = cls(d, clock=lambda: t[0]) if cls is Queue else cls(d, clock=lambda: t[0], window=None)
        for _ in range(10):
            q.submit(10.0, owner=STUDENTS[0])          # 한 명이 열 개를 먼저
        for s in STUDENTS[1:]:
            q.submit(10.0, owner=s)                     # 나머지 열아홉은 하나씩, 그 뒤에
        first_start = {}
        while True:
            j = q.claim("gpu-0")
            if not j:
                break
            first_start.setdefault(j["owner"], t[0])
            t[0] += JOB_S
            q.complete(j["id"])
    others = [first_start[s] for s in STUDENTS[1:]]
    med, mx = statistics.median(others), max(others)
    return {"first_student_first_start_s": first_start[STUDENTS[0]],
            "others_median_wait_s": med, "others_max_wait_s": mx, "others_min_wait_s": min(others), "total_s": t[0],
            "others_median_wait_min": round(med / 60, 1), "others_max_wait_min": round(mx / 60, 1), "total_min": round(t[0] / 60)}


def main():
    out = {"fifo": run(Queue), "fair": run(ClassQueue)}
    print(f"  {'':10s} 나머지 19명 첫 잡 시작까지 — 중앙값 / 최대")
    for k, v in out.items():
        print(f"  {k:10s} {v['others_median_wait_s']/60:5.1f}분 / {v['others_max_wait_s']/60:5.1f}분   (총 처리 {v['total_s']/60:.0f}분)")
    json.dump({"measured": "2026-09-03", "students": 20, "first_student_jobs": 10, "job_s": JOB_S, "results": out},
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work", "fairness.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/fairness.json")


if __name__ == "__main__":
    main()
