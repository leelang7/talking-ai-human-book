# -*- coding: utf-8 -*-
"""
Ch21 §3 — 겹침 경로의 두 부품 (Ch07 §4 의 그림 F4 를 코드로)

    첫 문장이 끝나는 순간 LLM 을 더 기다리지 않고 TTS 로 넘긴다
    TTS 의 첫 오디오 청크가 오는 순간 재생을 시작한다

server.py 의 기본 경로(문장 전체를 기다렸다가 파일로 TTS)는 실측 TTFA 5.4초였다.
같은 부품을 이렇게 겹치면 1.7초 — _work/ttfa.json · ttfa_stream.json.

네트워크가 없어도 검사되는 것은 `first_sentence()` 뿐이다. 그래서 그것만 순수 함수다.
"""
import json
import re
import time

_TAG = re.compile(r"^\s*\[\w+\]\s*\[\w+\]\s*")
_SENT_END = re.compile(r"[.!?~](?:\s|$)")


def first_sentence(pieces):
    """토큰 조각 이터레이터 → (첫 문장, 그때까지 받은 조각 수).

    태그 `[감정][동작]` 는 문장으로 치지 않는다. "Dr." 같은 약어는 Ch07 의 chunker 가
    다루고, 여기서는 **첫 종결부호 뒤 공백** 을 문장 끝으로 본다 — 빠른 것이 목적이다.
    끝까지 종결부호가 없으면 받은 전부를 돌려준다(빈 문장으로 TTS 를 부르지 않는다).
    """
    text = ""
    n = 0
    for piece in pieces:
        n += 1
        text += piece
        body = _TAG.sub("", text)
        m = _SENT_END.search(body)
        if m:
            return body[:m.end()].strip(), n
    return _TAG.sub("", text).strip(), n


def gemini_sse(url, system, prompt, max_tokens=80, temperature=0.9, timeout=30):
    """Gemini REST 스트리밍(alt=sse) 의 텍스트 조각 이터레이터. 네트워크가 필요하다."""
    import requests
    body = {"system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens,
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    with requests.post(url, json=body, stream=True, timeout=timeout) as r:
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            try:
                j = json.loads(line[5:])
                piece = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError, ValueError):
                continue
            if piece:
                yield piece


async def tts_first_chunk(text, voice):
    """edge-tts 스트림에서 첫 오디오 청크까지의 초. 첫 청크만 받고 세션을 닫는다."""
    import edge_tts
    t0 = time.time()
    g = edge_tts.Communicate(text, voice).stream()
    got = None
    async for chunk in g:
        if chunk["type"] == "audio":
            got = time.time() - t0
            break
    await g.aclose()
    return got
