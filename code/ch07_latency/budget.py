# -*- coding: utf-8 -*-
"""
지연 예산 계측 + 문장 청킹 (Ch07)

측정할 숫자는 하나다 — **첫 소리까지의 시간(TTFA)**. 목표 2초, 관리 지표는 p95.
평균만 보면 안 된다. 평균 1.2초인데 10%가 4초면 열 명 중 한 명은 매번 나쁜 경험을 한다.

실행(자체 데모):
    python budget.py --demo
"""
import json
import os
import re
import statistics
import threading
import time
from contextlib import contextmanager

# ── 문장 청킹 ─────────────────────────────────────────────────────────
#
# 경계는 "문장부호 뒤의 공백" 이다. 그런데 **점 뒤의 공백이 전부 문장 끝은 아니다.**
#   `3.14 입니다`  → 점 뒤에 공백이 없으니 애초에 안 걸린다 (운이 좋은 것)
#   `Dr. Kim`      → 점 뒤에 공백이 있다. 자르면 "Dr." 이 TTS 로 따로 나간다
#   `보니... 그렇네요` → 말줄임표. 여기서 끊는 것은 허용한다 — 생각이 끊긴 자리다
#
# 스트리밍에서는 **뒤에 무엇이 올지 모른 채** 판단해야 하므로(Ch07 §3), 앞만 보고
# 정할 수 있는 규칙만 쓴다. 자주 나오는 라틴 약어 뒤의 점은 경계로 치지 않는다.
# 파이썬의 lookbehind 는 고정 폭이라 약어마다 하나씩 둔다.
_ABBR = ("Dr", "Mr", "Mrs", "Ms", "No", "vs", "etc", "e.g", "i.e", "Prof", "St")
# lookbehind 는 공백 **바로 앞** 을 본다 — 그 자리는 "Dr." 처럼 점까지 포함한 문자열이다.
_SENT = re.compile("".join(rf"(?<!\b{re.escape(a)}\.)" for a in _ABBR)
                   + r"(?<=[.!?~])\s+")
_CLEAN = re.compile(r"[^가-힣a-zA-Z0-9 .,!?~]")
_WS = re.compile(r"\s+")


def normalize(text: str, max_sentences: int = 2) -> str:
    """TTS 로 보내기 전 정규화 (Ch03 §4, Ch20 §7).

    이모지·특수문자를 제거한다. 엔진이 읽어버릴지 침묵할지 예측할 수 없기 때문.
    감정·동작 태그가 남아 "대괄호 익사이티드" 로 읽히는 사고도 여기서 막힌다.
    """
    t = _WS.sub(" ", _CLEAN.sub(" ", text or "")).strip()
    parts = [s.strip() for s in _SENT.split(t) if s.strip()][:max_sentences]
    return " ".join(parts) or "네."


def stream_sentences(token_iter, min_chars: int = 10, max_sentences: int = 2):
    """LLM 토큰 스트림에서 문장이 완성될 때마다 즉시 내보낸다 (Ch07 §3).

    전체 응답을 기다렸다 TTS 를 부르면 LLM 생성 시간이 통째로 지연에 들어간다.
    첫 문장만 나오면 바로 보내고, 나머지는 재생 중에 만든다.

    ★ min_chars 는 **두 번째 청크부터** 적용한다.

      짧은 조각을 합치는 이유는 재생이 잘게 끊기지 않게 하려는 것이다.
      그런데 그 규칙을 첫 청크에 적용하면 "네." 같은 짧은 응답이 다음 문장을
      기다리느라 늦어진다 — TTFA 를 재면서 첫 소리를 늦추는 셈이다.

      첫 청크는 경계가 나오는 즉시 내보낸다(지연 우선).
      두 번째부터는 min_chars 까지 합친다(매끄러움 우선).

      이 규칙은 회귀 테스트에서 발견됐다. test_chunker.py 주석 참조.
    """
    buf, sent = "", 0
    for tok in token_iter:
        buf += tok
        while True:
            need = 1 if sent == 0 else min_chars      # ★ 첫 청크는 지연 우선
            # 첫 경계에서 멈추면 안 된다. 짧은 문장이 앞에 오면 거기 갇힌다.
            # 기준을 채우는 **가장 이른** 경계를 찾아 자른다.
            cut = next((m for m in _SENT.finditer(buf)
                        if len(buf[:m.start()].strip()) >= need), None)
            if not cut:
                break                      # 아직 짧다 — 더 모은다
            yield buf[:cut.start()].strip()
            buf = buf[cut.end():]
            sent += 1
            if sent >= max_sentences:
                return
    tail = buf.strip()
    if tail and sent < max_sentences:
        yield tail


# ── 단계별 계측 ───────────────────────────────────────────────────────
class LatencyLog:
    """단계 시작/끝을 찍고 p50·p95 를 낸다 (Ch07 §8).

    항목은 다섯이면 충분하다 — 입력 확정 · STT · LLM 첫 문장 · TTS 첫 청크 · 재생 시작.
    """

    STAGES = ("input", "stt", "llm_first", "tts_first", "play")

    def __init__(self, path: str | None = None):
        self.path = path
        self._rows: list[dict] = []
        self._lock = threading.Lock()

    @contextmanager
    def turn(self):
        t = {"t0": time.perf_counter(), "marks": {}}
        try:
            yield t
        finally:
            row = {k: round((v - t["t0"]) * 1000) for k, v in t["marks"].items()}
            row["ttfa"] = row.get("play") or row.get("tts_first")
            with self._lock:
                self._rows.append(row)
            if self.path:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def mark(t: dict, stage: str):
        t["marks"][stage] = time.perf_counter()

    def report(self) -> dict:
        """p95 를 목표로 잡는다. 평균은 나쁜 경험을 숨긴다."""
        out = {}
        for k in ("ttfa",) + self.STAGES:
            vals = sorted(r[k] for r in self._rows if r.get(k) is not None)
            if not vals:
                continue
            out[k] = {"n": len(vals), "p50": statistics.median(vals),
                      "p95": vals[min(len(vals) - 1, int(len(vals) * 0.95))],
                      "max": vals[-1]}
        return out

    def print_report(self, target_ms: int = 2000):
        r = self.report()
        print(f"  {'단계':<12}{'n':>5}{'p50':>8}{'p95':>8}{'max':>8}")
        for k, v in r.items():
            print(f"  {k:<12}{v['n']:>5}{v['p50']:>8}{v['p95']:>8}{v['max']:>8}")
        t = r.get("ttfa")
        if t:
            ok = t["p95"] <= target_ms
            print(f"\n  TTFA p95 = {t['p95']}ms  (목표 {target_ms}ms)  {'PASS' if ok else 'FAIL'}")
            if not ok:
                print("  → 변동이 큰 구간부터 보세요. 대개 LLM 또는 TTS(둘 다 외부 API)입니다.")


if __name__ == "__main__":
    import random
    log = LatencyLog()
    for i in range(40):
        with log.turn() as t:
            time.sleep(random.uniform(0.00, 0.02)); LatencyLog.mark(t, "input")
            time.sleep(random.uniform(0.02, 0.05)); LatencyLog.mark(t, "stt")
            # 10%는 튄다 — 평균만 보면 안 되는 이유
            time.sleep(random.uniform(0.04, 0.09) + (0.25 if i % 10 == 0 else 0))
            LatencyLog.mark(t, "llm_first")
            time.sleep(random.uniform(0.04, 0.08)); LatencyLog.mark(t, "tts_first")
            time.sleep(random.uniform(0.00, 0.01)); LatencyLog.mark(t, "play")
    log.print_report()
    print("\n  청킹 데모:", list(stream_sentences(iter(
        ["안녕", "하세요. ", "네.", " ", "오늘은 ", "날씨가 좋네요. ", "더 있어요."]))))
