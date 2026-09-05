# -*- coding: utf-8 -*-
"""Ch25 §3 표 — 실제 장 세 개를 chunker 로 쪼갠 결과. 원고가 바뀌면 다시 돌려 표를 갱신한다.

    python measure.py    → _work/measure.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chunker  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = ["ch25_rag.md", "ch07_latency_budget.md", "ch22_persona.md"]


def main():
    out = {"measured": "", "defaults": {"MAX_CHARS": chunker.MAX_CHARS, "MIN_CHARS": chunker.MIN_CHARS, "OVERLAP": chunker.OVERLAP}, "docs": {}}
    import datetime
    out["measured"] = datetime.date.today().isoformat()
    for doc in DOCS:
        p = os.path.join(ROOT, "draft", doc)
        if not os.path.exists(p):
            print("  (원고 없음 — 컴패니언 저장소에서는 건너뜀)", doc)
            continue
        md = open(p, encoding="utf-8").read()
        cs = chunker.chunk(md)
        sizes = [len(c["body"]) for c in cs]
        out["docs"][doc] = {"chunks": len(cs), "chars": len(md), "mean": round(sum(sizes) / len(sizes)), "min": min(sizes),
                            "max": max(sizes), "in_300_600": round(sum(1 for x in sizes if 300 <= x <= 600) / len(sizes), 2), "with_heading": None}
        print("  %-26s %6d자 %3d조각 평균 %3d 범위 %d~%d 300~600 안 %d%%" % (doc, len(md), len(cs), out["docs"][doc]["mean"], min(sizes), max(sizes), out["docs"][doc]["in_300_600"] * 100))
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work"), exist_ok=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work", "measure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
