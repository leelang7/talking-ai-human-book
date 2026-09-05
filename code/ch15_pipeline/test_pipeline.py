# -*- coding: utf-8 -*-
"""
Ch15 회귀 테스트 — 재개와 건너뛰기

이 파일이 지키는 것은 하나다.
  ★ **mux 가 실패해도 195초짜리 립싱크를 다시 돌지 않는다.**

그리고 그 반대도 — 사진이 바뀌면 리타게팅부터는 반드시 다시 돈다.
건너뛰어야 할 것을 돌리면 시간을 잃고, 돌려야 할 것을 건너뛰면 결과를 잃는다.

    python test_pipeline.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import ORDER, STAGES, Pipeline  # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


class Fake:
    """어느 단계가 몇 번 불렸는지 세는 가짜 실행기. GPU 는 없다."""

    def __init__(self):
        self.calls = []

    def runner(self, name, fail=False):
        def _run(inp, out):
            self.calls.append(name)
            if fail:
                raise RuntimeError("GPU OOM")
            with open(out, "w") as f:
                f.write(name * 4)
        return _run

    def runners(self, fail_at=None):
        return {n: self.runner(n, fail=(n == fail_at)) for n in ORDER}


def setup(d):
    src = os.path.join(d, "src"); os.makedirs(src, exist_ok=True)
    paths = {}
    for key, name, body in (("script", "대본.txt", "안녕"), ("photo", "하늘이.jpg", "IMG"),
                            ("driver", "driver.mp4", "VID")):
        p = os.path.join(src, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        paths[key] = p
    return paths


def main() -> int:
    print("\n  ── Ch15 파이프라인 재개 ──")
    ok([s[0] for s in STAGES] == ["tts", "lipsync", "retarget", "mux"],
       "단계 순서가 §2 그대로다", " → ".join(ORDER))

    with tempfile.TemporaryDirectory() as d:
        src = setup(d)
        quiet = lambda s: None

        # ── 1회차: 전부 돈다 ───────────────────────────────────────
        fk = Fake()
        p = Pipeline(os.path.join(d, "w1"), fk.runners(), log=quiet)
        files = p.stage_inputs(src["script"], src["photo"], src["driver"])
        r = p.run(files)
        ok(r["ran"] == list(ORDER) and r["failed"] is None, "처음엔 네 단계가 다 돈다")
        ok(fk.calls == list(ORDER), "실행기가 순서대로 한 번씩 불렸다")

        # ── ④ 한글 경로 회피 ───────────────────────────────────────
        ok(all(os.path.basename(v).isascii() for v in files.values()),
           "★ 한글 파일명이 ASCII 이름으로 복사됐다",
           " · ".join(os.path.basename(v) for v in files.values()))
        ok(os.path.exists(src["script"]) and "대본" in src["script"],
           "원본은 그대로 남아 있다")

        # ── ⑤ 아무것도 안 바뀌면 전부 건너뛴다 ───────────────────────
        fk.calls.clear()
        r = p.run(files)
        ok(r["skipped"] == list(ORDER) and r["ran"] == [], "★ 입력이 같으면 넷 다 건너뛴다")
        ok(fk.calls == [], "  실행기가 한 번도 안 불렸다")

        # ── 사진만 바뀌면 리타게팅부터 ─────────────────────────────
        with open(files["photo"], "w", encoding="utf-8") as f:
            f.write("IMG-2")
        fk.calls.clear()
        r = p.run(files)
        ok(r["skipped"] == ["tts", "lipsync"] and r["ran"] == ["retarget", "mux"],
           "★ 사진이 바뀌면 리타게팅·mux 만 다시 — 립싱크 195초는 안 돈다")
        ok(fk.calls == ["retarget", "mux"], "  실행기도 그 둘만 불렸다")

        # ── 대본이 바뀌면 전부 ─────────────────────────────────────
        with open(files["script"], "w", encoding="utf-8") as f:
            f.write("안녕 바뀜")
        fk.calls.clear()
        r = p.run(files)
        ok(r["ran"] == list(ORDER), "대본이 바뀌면 하류 전부 다시 — 건너뛰면 결과가 틀린다")

        # ── ③ 게이트 실패 → 즉시 중단 ──────────────────────────────
        fk2 = Fake()
        bad_gate = {"lipsync": lambda out: (False, "적중률 40% < 80% (Ch09)")}
        p2 = Pipeline(os.path.join(d, "w2"), fk2.runners(), gates=bad_gate, log=quiet)
        f2 = p2.stage_inputs(src["script"], src["photo"], src["driver"])
        r = p2.run(f2)
        ok(r["failed"] == "lipsync" and r["ran"] == ["tts"],
           "★ 립싱크 게이트가 떨어지면 리타게팅으로 안 간다")
        ok(fk2.calls == ["tts", "lipsync"], "  뒤 단계 실행기는 불리지 않았다")
        ok(p2.manifest["lipsync"]["ok"] is False and "적중률" in p2.manifest["lipsync"]["msg"],
           "  실패 이유가 매니페스트에 남는다")

        # ── ★ 핵심: mux 실패 → 재실행은 mux 부터 ───────────────────
        fk3 = Fake()
        p3 = Pipeline(os.path.join(d, "w3"), fk3.runners(fail_at="mux"), log=quiet)
        f3 = p3.stage_inputs(src["script"], src["photo"], src["driver"])
        r = p3.run(f3)
        ok(r["failed"] == "mux" and r["ran"] == ["tts", "lipsync", "retarget"],
           "mux 에서 예외가 나면 거기서 멈춘다 (앞 셋은 성공으로 기록)")
        ok(p3.manifest["mux"]["ok"] is False and "OOM" in p3.manifest["mux"]["msg"],
           "  예외 메시지가 기록된다 — 조용히 죽지 않는다")

        p3.runners = fk3.runners()                    # 고쳤다고 치고 다시
        fk3.calls.clear()
        r = p3.run(f3)
        ok(r["skipped"] == ["tts", "lipsync", "retarget"] and r["ran"] == ["mux"],
           "★★ 다시 돌리면 mux 만 돈다 — 립싱크를 다시 하지 않는다")
        ok(fk3.calls == ["mux"], "  실행기도 mux 만 불렸다")
        ok(r["failed"] is None and p3.manifest["mux"]["ok"], "  이번엔 끝까지 갔다")

        # ── 매니페스트가 프로세스를 넘어 산다 ───────────────────────
        p4 = Pipeline(os.path.join(d, "w3"), Fake().runners(), log=quiet)
        ok(all(p4.manifest[n]["ok"] for n in ORDER), "새 프로세스가 지난 결과를 그대로 읽는다")
        ok(p4.run(f3)["skipped"] == list(ORDER), "  그래서 다시 띄워도 안 돈다")

        # ── dry-run 은 아무것도 안 돌린다 ──────────────────────────
        fk5 = Fake()
        p5 = Pipeline(os.path.join(d, "w5"), fk5.runners(), log=quiet)
        f5 = p5.stage_inputs(src["script"], src["photo"], src["driver"])
        r = p5.run(f5, dry_run=True)
        ok(r["ran"] == list(ORDER) and fk5.calls == [], "dry-run 은 계획만 내고 실행기를 안 부른다")
        ok(not os.path.exists(os.path.join(d, "w5", "final.mp4")), "  산출물도 안 생긴다")

        # ── 계획이 이유를 말한다 ───────────────────────────────────
        rows = p5.plan(f5)
        ok(all(len(r) == 3 and r[2] for r in rows), "plan() 은 단계마다 이유를 붙인다",
           rows[0][2])

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
