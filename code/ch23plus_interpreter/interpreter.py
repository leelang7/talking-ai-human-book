# -*- coding: utf-8 -*-
"""
Ch23+ — 실시간 통역 아바타: 듣고, 문장 단위로 옮기고, 다른 목소리로 말한다

동시통역이 아니라 **문장 단위 순차 통역** 이다. 화자가 문장을 끝내면 그 문장을 옮겨 말하고,
그동안 다음 문장을 계속 듣는다. 부품은 전부 앞 장에서 왔다.

    STT(Ch23) → 문장 분할(Ch07) → 번역(LLM, 용어 잠금·숫자 보존) → 정규화(Ch03) → TTS(대상 언어 목소리) → 아바타(Ch17/Ch18)

네트워크 없이 검사되는 것: 문장 분할 · 용어 잠금 검사 · 숫자 보존 검사 · 목소리 선택 · 상태 기계 · 지연 예산.
번역 호출(`translate`)만 LLM 을 쓴다 — 호출자가 함수를 넣어 주면 어떤 모델이든 된다.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "ch03_tts"))

# ── 목소리 — 언어마다 하나. 같은 성별·비슷한 톤으로 묶어야 '한 사람이 통역한다' 는 인상이 유지된다
VOICES = {"ko": "ko-KR-SunHiNeural", "en": "en-US-AriaNeural", "ja": "ja-JP-NanamiNeural", "zh": "zh-CN-XiaoxiaoNeural"}
LANG_NAME = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese (Simplified)"}

# 문장 끝 — 한국어·영어·일본어·중국어 종결 부호. 소수점·약어는 문장 끝이 아니다(Ch07 §3)
_END = re.compile(r"(?<!\d)[.!?](?=\s|$)|[。！？]")          # 한·영은 뒤에 공백, 일·중 종결 부호는 그 자체로 끝
_ABBR = ("Dr.", "Mr.", "Ms.", "Mrs.", "St.", "No.", "vs.")


def segment(buffer: str):
    """스트리밍 STT 텍스트 → (완성된 문장들, 남은 조각). 완성된 것만 번역기로 보낸다."""
    done, rest, start = [], buffer, 0
    for m in _END.finditer(buffer):
        head = buffer[start:m.end()]
        if any(head.rstrip().endswith(a) for a in _ABBR):
            continue
        done.append(head.strip())
        start = m.end()
    return done, buffer[start:].lstrip()


class Glossary:
    """용어 잠금 — 고유명·상품명·직함은 번역기가 마음대로 옮기면 안 된다."""

    def __init__(self, pairs=None):
        self.pairs = dict(pairs or {})           # {원어: 대상어}

    def prompt_block(self):
        if not self.pairs:
            return ""
        return "Use exactly these terms: " + "; ".join(f"{k} → {v}" for k, v in self.pairs.items()) + "."

    def check(self, src: str, out: str):
        """원문에 나온 잠금 용어가 번역에 그대로 있는지. 빠진 것을 돌려준다."""
        return [v for k, v in self.pairs.items() if k in src and v not in out]


_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_preserved(src: str, out: str):
    """숫자는 번역되지 않는다 — 원문의 숫자가 전부 번역문에 있어야 한다. 빠진 것을 돌려준다."""
    want = [n.replace(",", "") for n in _NUM.findall(src)]
    have = [n.replace(",", "") for n in _NUM.findall(out)]
    return [n for n in want if n not in have]


def translate_prompt(text: str, src: str, dst: str, glossary: Glossary = None, register: str = "polite"):
    g = glossary.prompt_block() if glossary else ""
    return (f"Translate the following {LANG_NAME[src]} sentence into natural spoken {LANG_NAME[dst]} for a live interpreter. "
            f"Keep every number, unit and proper noun exactly. {g} Register: {register}. "
            f"Output only the translation, no quotes, no notes.\n\n{text}")


def translate(text: str, src: str, dst: str, llm, glossary: Glossary = None, register: str = "polite", retries: int = 1):
    """llm(prompt) -> str. 잠금 용어·숫자가 빠지면 한 번 더 시도한다."""
    prompt = translate_prompt(text, src, dst, glossary, register)
    out = (llm(prompt) or "").strip().strip('"“”')
    for _ in range(retries):
        missing = (glossary.check(text, out) if glossary else []) + numbers_preserved(text, out)
        if not missing:
            break
        out = (llm(prompt + "\n\nYour previous answer dropped: " + ", ".join(missing) + ". Include them.") or out).strip().strip('"“”')
    return out


def normalize_for_tts(text: str, lang: str) -> str:
    """대상 언어가 한국어면 Ch03 의 정규화(숫자·단위·약어)를 거친다. 다른 언어는 엔진에 맡긴다."""
    if lang == "ko":
        try:
            from normalize_ko import normalize
            return normalize(text, english=False)
        except ImportError:
            return text
    return text


def voice_for(lang: str) -> str:
    return VOICES.get(lang, VOICES["en"])


# ── 상태 기계 — 통역 아바타는 화자와 겹쳐 말하지 않는다 ─────────────────
STATES = ("idle", "listening", "translating", "speaking")
ALLOWED = {"idle": ("listening",), "listening": ("translating", "idle"),
           "translating": ("speaking", "listening"), "speaking": ("listening", "idle")}


class Session:
    """문장 단위 순차 통역 세션.

    규칙 ① 화자가 말하는 동안(listening) 아바타는 소리를 내지 않는다 — 자막만 먼저 낸다.
    규칙 ② 화자가 문장을 끝내면(END) 그 문장을 큐에 넣고, 아바타가 말하고 있지 않으면 바로 말한다.
    규칙 ③ 아바타가 말하는 중에 화자가 다시 말하면 아바타는 멈춘다(Ch23 §4 의 끼어들기와 같은 우선순위).
    """

    def __init__(self, src="ko", dst="en", llm=None, glossary=None, subtitle_first=True):
        self.src, self.dst, self.llm, self.glossary = src, dst, llm, glossary
        self.subtitle_first = subtitle_first
        self.state, self.buffer, self.queue, self.spoken, self.subtitles = "idle", "", [], [], []
        self.interrupted = 0

    def _go(self, new):
        if new not in ALLOWED[self.state]:
            raise ValueError(f"{self.state} → {new} 허용 안 됨")
        self.state = new

    def hear(self, partial: str):
        """STT 부분 결과가 들어온다. 화자가 말하는 중이면 아바타는 멈춘다."""
        if self.state == "speaking":
            self.interrupted += 1
            self._go("listening")
        elif self.state != "listening":
            self._go("listening")
        self.buffer = partial
        done, rest = segment(self.buffer)
        for s in done:
            self.queue.append(s)
            if self.subtitle_first:
                self.subtitles.append((s, None))         # 원문 자막은 번역보다 먼저
        self.buffer = rest
        return done

    def end_of_speech(self):
        """Ch23 §2 의 종료 판정 — 남은 조각도 문장으로 친다."""
        if self.buffer.strip():
            self.queue.append(self.buffer.strip())
            if self.subtitle_first:
                self.subtitles.append((self.buffer.strip(), None))
            self.buffer = ""
        return self.speak_next()

    def speak_next(self):
        """큐의 첫 문장을 옮겨 말한다. 화자가 말하는 중이면 기다린다."""
        if not self.queue or self.state == "listening" and self.buffer.strip():
            return None
        src = self.queue.pop(0)
        self._go("translating")
        out = translate(src, self.src, self.dst, self.llm, self.glossary) if self.llm else src
        self._go("speaking")
        self.spoken.append((src, out))
        for i, (s, t) in enumerate(self.subtitles):
            if s == src and t is None:
                self.subtitles[i] = (s, out)
                break
        return out

    def done_speaking(self):
        self._go("listening" if self.queue or self.buffer else "idle")
        return self.speak_next() if self.queue else None


def latency_budget(end_of_speech_s=0.8, translate_s=1.0, tts_first_chunk_s=0.5):
    """화자가 문장을 끝낸 순간 → 통역 음성이 시작되는 순간. 순차 통역의 최소 지연."""
    return {"end_of_speech": end_of_speech_s, "translate": translate_s, "tts_first_chunk": tts_first_chunk_s,
            "total": round(end_of_speech_s + translate_s + tts_first_chunk_s, 2)}


if __name__ == "__main__":
    done, rest = segment("안녕하세요. 오늘 3.5km 걸었어요! 내일은")
    print("  문장:", done, "| 남은 조각:", repr(rest))
    g = Glossary({"올댓에이아이": "AllThatAI"})
    print("  용어 검사:", g.check("올댓에이아이에 오세요.", "Welcome to All That AI."))
    print("  숫자 검사:", numbers_preserved("3.5km 를 12분에", "3.5 km in twelve minutes"))
    print("  예산:", latency_budget())
