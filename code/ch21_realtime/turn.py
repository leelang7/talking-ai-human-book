# -*- coding: utf-8 -*-
"""
Ch21 — 한 턴의 순수 로직

`server.py` 가 네트워크(LLM · TTS)를 부르고, 이 파일이 **그 앞뒤의 판단** 을 한다.
저자의 실제 서버(`rigged/chat_vrm.py`)에서 판단 부분만 떼어 왔다.

    ① 태그 파싱     LLM 답 맨 앞의 [감정][동작] 을 읽는다 — 없거나 틀려도 죽지 않는다
    ② 정규화       Ch07 의 normalize 를 그대로 쓴다 — 태그·이모지가 TTS 로 새지 않는다
    ③ 폴백         LLM 이 비어 있으면 **감정 태그가 붙은** 대기 문장을 쓴다 (Ch22 §6)
    ④ 지표         LLM 초 · TTS 초 · 첫 소리까지 — Ch07 의 TTFA 가 여기서 찍힌다

네트워크가 없어도 전부 검사된다. 그래서 회귀 테스트가 여기 붙는다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "ch07_latency"))
try:
    from budget import normalize                  # Ch07 §3 — 문장 청킹과 같은 정규화
except Exception:                                 # ch07 폴더가 없어도 이 파일은 돈다
    def normalize(t, max_sentences=2):
        t = re.sub(r"[^가-힣a-zA-Z0-9 .,!?~]", " ", t or "")
        s = [x.strip() for x in re.split(r"(?<=[.!?~])\s+", t) if x.strip()][:max_sentences]
        return " ".join(s) or "네."

EMOS = ("greet", "happy", "excited", "think", "sad", "neutral")
ACTS = ("wave", "bow", "nod", "point", "clap", "cheer", "think", "shrug",
        "jumpingjack", "armcircle", "stretch", "twist", "squat", "none")

# LLM 이 침묵할 때. **감정 태그가 붙어 있다** — 폴백도 캐릭터여야 한다 (Ch22 §6)
FALLBACK = "[neutral][none] 네, 말씀하세요."
TTFA_BUDGET = 2.0                                  # Ch07 — 첫 소리까지 2초


def parse_tags(text: str):
    """맨 앞 `[감정][동작]` → (emotion, action, 나머지). 순서가 바뀌어도, 하나만 있어도 된다.

    모르는 태그는 버리고 기본값(neutral · none)으로 간다. LLM 은 형식을 자주 어긴다.
    """
    s = (text or "").strip()
    tags = []
    while len(tags) < 2:
        m = re.match(r"\s*\[(\w+)\]\s*(.*)", s, re.S)
        if not m:
            break
        tags.append(m.group(1).lower())
        s = m.group(2)
    emo = next((x for x in tags if x in EMOS), "neutral")
    act = next((x for x in tags if x in ACTS), "none")
    return emo, act, s


def make_turn(llm_text: str, llm_sec: float, tts_sec: float, audio_url) -> dict:
    """LLM 원문과 시간들을 받아 클라이언트에 줄 한 턴을 만든다."""
    raw = llm_text or FALLBACK
    emo, act, body = parse_tags(raw)
    reply = normalize(body) or "네."
    ttfa = llm_sec + tts_sec                      # 순차면 이것이 첫 소리까지다 (Ch07 §2)
    return {
        "reply": reply, "emotion": emo, "action": act, "audio": audio_url,
        "fallback": not llm_text,
        "llm_sec": round(llm_sec, 2), "tts_sec": round(tts_sec, 2),
        "ttfa_sec": round(ttfa, 2), "over_budget": ttfa > TTFA_BUDGET,
        "info": f"LLM {llm_sec:.1f}s · TTS {tts_sec:.1f}s · {emo}/{act}"
                + (" · 예산 초과" if ttfa > TTFA_BUDGET else ""),
    }


def _demo():
    print()
    for raw, l, t in (("[excited][jumpingjack] 자 같이 운동해요! 준비됐죠?", 0.6, 0.5),
                      ("[bogus][wave]안녕하세요 😀 반가워요!!!", 0.4, 0.4),
                      ("태그 없이 그냥 말합니다. 두 번째 문장. 세 번째는 잘립니다.", 1.3, 0.9),
                      ("", 5.0, 0.0)):
        r = make_turn(raw, l, t, "/audio/x.mp3")
        print(f"  {r['emotion']:8}{r['action']:12} {r['reply'][:34]:36} {r['info']}")
    print()


if __name__ == "__main__":
    _demo()
