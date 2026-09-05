# -*- coding: utf-8 -*-
"""
Ch29 §4 — 생성 로그 스키마 · 철회 역추적 · 보관 만료

Ch29 의 의무 여섯 중 셋은 **코드가 아니면 지켜지지 않는다.**

    동의를 기록한다      → 결과물마다 어떤 원본 · 어떤 동의로 만들었는지 적는다
    철회 경로를 만든다   → "이 사람 것을 다 지워라" 에 답할 수 있어야 한다
    보관 기간을 정한다   → 무기한 보관은 위험의 무기한 보유다

그래서 로그 한 줄의 **필수 항목** 을 스키마로 못박고, 철회 요청이 왔을 때
원본 해시로 파생물을 **역추적** 하고, 기간이 지난 것을 **골라내는** 함수를 둔다.
Ch24 §1 의 구분이 여기서 작동한다 — 지워지는 것은 그 사람의 *일화* 뿐이다.

    python genlog.py      로그 몇 줄을 쓰고 철회·만료를 돌려 본다
"""
import hashlib
import json
import os
import time

REQUIRED = ("id", "at", "who", "consent_ref", "source_assets", "output",
            "placement", "retention_days", "marks")
PLACEMENTS = ("local_only", "anywhere")            # Ch28 §6 과 같은 두 값
MARK_LAYERS = ("visible", "metadata", "watermark")  # 부록 G §4 의 세 층


def sha_of(path_or_bytes) -> str:
    h = hashlib.sha256()
    if isinstance(path_or_bytes, (bytes, bytearray)):
        h.update(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
    return h.hexdigest()[:16]


def validate(entry: dict) -> list:
    """빠진 것 · 틀린 것을 **전부** 돌려준다. 하나만 돌려주면 세 번 고치게 된다."""
    bad = [f"{k} 없음" for k in REQUIRED if k not in entry]
    if "placement" in entry and entry["placement"] not in PLACEMENTS:
        bad.append(f"placement 는 {PLACEMENTS} 중 하나")
    if "retention_days" in entry and not (isinstance(entry["retention_days"], int)
                                          and entry["retention_days"] > 0):
        bad.append("retention_days 는 양의 정수 — 무기한(0·None)은 허용하지 않는다")
    if "source_assets" in entry and not entry["source_assets"]:
        bad.append("source_assets 가 비어 있다 — 무엇으로 만들었는지 모르면 철회할 수 없다")
    if "marks" in entry:
        missing = [m for m in MARK_LAYERS if not entry["marks"].get(m)]
        if missing:
            bad.append("표시 세 층 중 빠짐: " + ", ".join(missing))
    return bad


class GenLog:
    """JSON Lines 한 파일. 덧붙이기만 한다 — 로그는 고치지 않는다."""

    def __init__(self, path: str, clock=time.time):
        self.path, self.clock = path, clock

    def append(self, who, consent_ref, sources, output, placement, retention_days,
               marks, note=""):
        entry = {"id": hashlib.sha1(f"{who}{output}{self.clock()}".encode()).hexdigest()[:10],
                 "at": self.clock(), "who": who, "consent_ref": consent_ref,
                 # bytes → 해시 · 존재하는 경로 → 파일 해시 · 그 밖은 이미 해시라고 본다.
                 # 처음엔 bytes 를 str() 로 저장해 "b'face-A'" 가 남았고, 철회 역추적이
                 # 빈 목록을 냈다 — 로그가 있어도 열쇠가 안 맞으면 철회할 수 없다.
                 "source_assets": [sha_of(s) if isinstance(s, (bytes, bytearray))
                                   else (sha_of(s) if os.path.exists(str(s)) else str(s))
                                   for s in sources],
                 "output": output, "placement": placement,
                 "retention_days": retention_days, "marks": dict(marks), "note": note,
                 "deleted": False}
        bad = validate(entry)
        if bad:
            raise ValueError("; ".join(bad))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def entries(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    # ── 철회 — 원본 해시로 파생물을 찾는다 ────────────────────────
    def retract(self, source_sha: str) -> list:
        """이 원본으로 만든 결과물 전부. **삭제 대상 목록** 이지 삭제가 아니다.

        철회 요청이 오면 이 목록을 사람이 보고 지운다. 자동 삭제는 하지 않는다 —
        Ch28+ §5 의 dry_run 원칙과 같다.
        """
        return [e for e in self.entries()
                if source_sha in e["source_assets"] and not e.get("deleted")]

    def mark_deleted(self, ids) -> int:
        rows = self.entries()
        n = 0
        for e in rows:
            if e["id"] in ids and not e.get("deleted"):
                e["deleted"] = True; e["deleted_at"] = self.clock(); n += 1
        with open(self.path, "w", encoding="utf-8") as f:
            for e in rows:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return n

    # ── 보관 만료 ──────────────────────────────────────────────────
    def expired(self, now=None) -> list:
        now = self.clock() if now is None else now
        return [e for e in self.entries()
                if not e.get("deleted") and now - e["at"] > e["retention_days"] * 86400]


def _demo():
    import tempfile
    t = [1_000_000.0]
    with tempfile.TemporaryDirectory() as d:
        log = GenLog(os.path.join(d, "gen.jsonl"), clock=lambda: t[0])
        face = b"face-of-A"; voice = b"voice-of-A"
        marks = {"visible": True, "metadata": True, "watermark": "id:7f3a"}
        a1 = log.append("user-A", "consent-2026-001", [face, voice], "out/a1.mp4",
                        "local_only", 90, marks)
        t[0] += 3600
        a2 = log.append("user-A", "consent-2026-001", [face], "out/a2.mp4",
                        "local_only", 90, marks)
        log.append("user-B", "consent-2026-002", [b"face-of-B"], "out/b1.mp4",
                   "anywhere", 30, marks)
        print()
        print(f"  로그 {len(log.entries())}건")
        hits = log.retract(sha_of(face))
        print(f"  A 의 얼굴로 만든 것 (철회 대상): {[e['output'] for e in hits]}")
        t[0] += 40 * 86400
        print(f"  40일 뒤 만료: {[e['output'] for e in log.expired()]}   ← B 만 (30일)")
        try:
            log.append("user-C", "consent-x", [], "out/c.mp4", "anywhere", 0,
                       {"visible": True})
        except ValueError as e:
            print(f"  거절된 항목: {e}")
        print()


if __name__ == "__main__":
    _demo()
