# -*- coding: utf-8 -*-
"""
Ch23+ §6 — 수어 브리지: 인식기의 단어열 ↔ 아바타의 손동작 태그

입력 쪽: 저자의 KSL 단어 인식 MVP(MediaPipe Holistic + BiLSTM, 20단어)가 내는 단어열을
         문장으로 엮어 TTS 로 읽는다. 단어열은 문장이 아니다 — 조사와 어순을 LLM 이 채운다.
출력 쪽: 텍스트를 아바타의 손동작 태그열로 바꾼다. Ch20 의 [감정][동작] 태그 체계를
         [sign:단어] 로 확장한다. 어휘 밖 단어는 지문자(fingerspell) 표식으로 남겨 **빠뜨리지 않는다**.

    python signbridge.py
"""
import re

# 인식기 어휘 그대로 — vocab_real.json (2026-04-30)
KSL_VOCAB = ("견제하다", "골키퍼", "구경", "권투", "그립다", "꿈", "낚시", "남매", "노래", "놀다",
             "누나", "망가지다", "상처", "성토", "여동생", "운전면허", "운전면허정지", "울보", "키우다", "힘")
NO_SIGN = "NO_SIGN"

# 어간 → 어휘. 인식기는 기본형을 내지만 문장은 활용형이다 (놀았어요 → 놀다)
_STEMS = {w: w[:-1] if w.endswith("다") else w for w in KSL_VOCAB}
_TOKEN = re.compile(r"[가-힣]+|[A-Za-z]+|\d+")


def words_to_prompt(words, lang="ko"):
    """인식된 단어열 → 문장을 만들라는 LLM 지시. 단어를 더하거나 빼지 말라고 못박는다."""
    ws = [w for w in words if w and w != NO_SIGN]
    return ("다음은 수어 인식기가 순서대로 인식한 단어입니다. 이 단어들만으로 자연스러운 한국어 한 문장을 만드세요. "
            "단어를 새로 넣거나 빼지 말고, 조사와 어순만 채우세요. 문장만 출력하세요.\n\n" + " / ".join(ws)), ws


def words_to_sentence(words, llm=None):
    prompt, ws = words_to_prompt(words)
    if not ws:
        return ""
    if llm is None:                                   # LLM 없이도 동작한다 — 단어를 이어 붙인 최소 문장
        return " ".join(ws) + "."
    return (llm(prompt) or " ".join(ws)).strip()


_VERB_END = ("아", "어", "았", "었", "고", "면", "요", "지", "는", "니", "게", "자")        # "라" 를 넣으면 놀라운 → 놀다
_NOUN_END = ("", "이", "가", "을", "를", "은", "는", "도", "에", "의", "과", "와", "로", "만")


def _match(tok, word, stem):
    """활용형·조사를 허용하되 한 글자 어간(놀·꿈·힘)은 어미까지 봐서 '놀라다·힘들다' 를 잡지 않는다."""
    if not tok.startswith(stem):
        return False
    tail = tok[len(stem):]
    if word.endswith("다"):                                # 동사·형용사: 어간 + 어미
        return tail == "" or tail[:1] in _VERB_END if len(stem) == 1 else True
    return tail in _NOUN_END or (len(stem) >= 2 and len(tail) <= 2)   # 명사: 조사만 허용


def sentence_to_signs(text):
    """텍스트 → 손동작 태그열. 어휘에 있는 단어는 [sign:단어], 없는 내용어는 [spell:단어]."""
    tags, covered, total = [], 0, 0
    for tok in _TOKEN.findall(text):
        hit = next((w for w, stem in _STEMS.items() if _match(tok, w, stem)), None)
        if hit:
            tags.append(f"[sign:{hit}]"); covered += 1; total += 1
        elif len(tok) >= 2 and re.match(r"[가-힣]{2,}", tok):
            tags.append(f"[spell:{tok}]"); total += 1
    return tags, (covered / total if total else 0.0)


def coverage(sentences):
    """문장 묶음에서 어휘가 덮는 내용어 비율 — 어휘 20개로는 어디까지 되는가."""
    cov = [sentence_to_signs(s)[1] for s in sentences]
    return round(sum(cov) / len(cov), 3) if cov else 0.0


if __name__ == "__main__":
    print("  단어열 → 문장(LLM 없이):", words_to_sentence(["누나", "노래", "놀다"]))
    tags, c = sentence_to_signs("누나가 노래하고 놀았어요. 운전면허 시험은 내일이에요.")
    print("  문장 → 태그:", tags, f"덮음 {c:.0%}")
    print("  덮음 비율(예문 4):", coverage(["누나가 노래해요", "여동생이 꿈을 키워요", "병원이 어디예요", "운전면허가 정지됐어요"]))
