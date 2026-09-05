# -*- coding: utf-8 -*-
"""
Ch29 회귀 테스트 — 지켜야 하는 것은 게이트로

    python test_responsibility.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from genlog import MARK_LAYERS, REQUIRED, GenLog, sha_of, validate  # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


MARKS = {"visible": True, "metadata": True, "watermark": "id:7f3a"}


def main() -> int:
    print("\n  ── Ch29 생성 로그 · 철회 · 보관 ──")

    # ── 스키마 ─────────────────────────────────────────────────────
    good = {"id": "x", "at": 1.0, "who": "A", "consent_ref": "c1", "source_assets": ["s"],
            "output": "o.mp4", "placement": "local_only", "retention_days": 90, "marks": MARKS}
    ok(validate(good) == [], "필수 항목이 다 있으면 통과")
    ok(len(validate({})) >= len(REQUIRED), "★ 빠진 것을 전부 한 번에 알려준다 — 세 번 고치게 하지 않는다")
    ok(any("무기한" in b for b in validate(dict(good, retention_days=0))),
       "★ 보관 기간 0 은 거절 — 무기한 보관은 위험의 무기한 보유 (Ch29 §4)")
    ok(validate(dict(good, retention_days=None)) != [], "None 도 거절")
    ok(any("철회" in b for b in validate(dict(good, source_assets=[]))),
       "★ 원본이 비어 있으면 거절 — 무엇으로 만들었는지 모르면 철회 못 한다")
    ok(any("표시 세 층" in b for b in validate(dict(good, marks={"visible": True}))),
       "★ 표시 세 층 중 하나라도 빠지면 잡는다 (부록 G §4)", " · ".join(MARK_LAYERS))
    ok(validate(dict(good, placement="cloud")) != [], "placement 는 Ch28 §6 의 두 값만")

    with tempfile.TemporaryDirectory() as d:
        t = [1_000_000.0]
        log = GenLog(os.path.join(d, "gen.jsonl"), clock=lambda: t[0])
        face_a, voice_a, face_b = b"face-A", b"voice-A", b"face-B"

        a1 = log.append("A", "c-1", [face_a, voice_a], "a1.mp4", "local_only", 90, MARKS)
        t[0] += 3600
        a2 = log.append("A", "c-1", [face_a], "a2.mp4", "local_only", 90, MARKS)
        b1 = log.append("B", "c-2", [face_b], "b1.mp4", "anywhere", 30, MARKS)
        ok(len(log.entries()) == 3, "세 줄이 남았다")
        ok(a1["source_assets"][0] == sha_of(face_a), "원본은 해시로 남는다 — 원본 자체를 로그에 두지 않는다")

        # ── 철회 역추적 ────────────────────────────────────────────
        hits = log.retract(sha_of(face_a))
        ok([e["output"] for e in hits] == ["a1.mp4", "a2.mp4"],
           "★ A 의 얼굴 해시 하나로 파생물 둘을 전부 찾는다 (Ch29 §4 철회 경로)")
        ok(all(e["who"] == "A" for e in hits), "  B 의 것은 섞이지 않는다 — 지워지는 건 그 사람의 일화뿐 (Ch24 §1)")
        ok(log.retract(sha_of(voice_a)) == [hits[0]], "음성 해시로도 찾는다 — 원본이 둘이면 둘 다 열쇠다")
        ok(log.retract("nope") == [], "모르는 해시는 빈 목록")

        # 목록이지 삭제가 아니다 — 사람이 보고 지운다
        ok(all(not e.get("deleted") for e in log.entries()), "★ retract 는 삭제하지 않는다 (dry_run 과 같은 원칙)")
        n = log.mark_deleted([e["id"] for e in hits])
        ok(n == 2 and log.retract(sha_of(face_a)) == [], "삭제 표시 뒤에는 철회 목록에서 빠진다")
        ok(len(log.entries()) == 3, "  줄은 지우지 않는다 — 로그는 덧붙이기만 한다")

        # ── 보관 만료 ──────────────────────────────────────────────
        t[0] += 40 * 86400
        ok([e["output"] for e in log.expired()] == ["b1.mp4"],
           "★ 40일 뒤엔 30일짜리 B 만 만료 — 90일짜리 A 는 아직 (그리고 삭제된 건 제외)")
        t[0] += 60 * 86400
        ok(log.expired() == [b1] if False else len(log.expired()) == 1,
           "100일 뒤에도 A 는 이미 삭제 표시라 만료 목록에 안 온다")

        # ── 스키마가 append 를 막는다 ──────────────────────────────
        try:
            log.append("C", "c-3", [], "c.mp4", "anywhere", 0, {"visible": True}); bad = True
        except ValueError as e:
            bad = False; msg = str(e)
        ok(not bad and "무기한" in msg and "철회" in msg and "표시" in msg,
           "★ 틀린 항목은 애초에 기록되지 않는다 — 세 문제를 한 번에 말한다")
        ok(len(log.entries()) == 3, "  거절된 줄은 파일에 안 남는다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
