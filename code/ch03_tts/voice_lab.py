# -*- coding: utf-8 -*-
"""
Ch03 — 목소리 층 실습 (대본 정규화 · 합성 · 검증)

이 책이 Ch03 에서 요구하는 세 가지를 코드로 강제한다.

    1. 대본을 정규화한다        — 이모지·태그가 TTS 로 새어 나가지 않게
    2. 16kHz 모노로 맞춘다       — 안 맞으면 립싱크가 '에러 없이' 이상해진다
    3. 길이를 기록한다           — 이 값이 Ch14 싱크 검증의 기준이 된다

실행:
    python voice_lab.py "안녕하세요. 반갑습니다."
    python voice_lab.py --file script.txt --voice ko-KR-InJoonNeural
    python voice_lab.py --styles                 # 감정 프리셋 4종 비교(Ch03+ §5)

종료 코드 0 = 검증 통과.
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
import media  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

VOICES = {"female": "ko-KR-SunHiNeural", "male": "ko-KR-InJoonNeural"}

# 파라미터 방식 감정 근사 (Ch03 §2). 속도·음높이 두 축이면 상당히 넓게 움직인다.
STYLES = {
    "news":  {"rate": "+0%",  "pitch": "-2Hz",  "desc": "뉴스·브리핑 — 차분·정확"},
    "talk":  {"rate": "+0%",  "pitch": "+0Hz",  "desc": "일상 대화 — 기본"},
    "sad":   {"rate": "-15%", "pitch": "-8Hz",  "desc": "슬픔 — 느리고 낮게"},
    "bright": {"rate": "+8%", "pitch": "+6Hz",  "desc": "밝음 — 빠르고 높게"},
}

# Ch03 §4 · Ch20 §7 — 이모지·대괄호 태그를 지운다.
#
# ★ 순서가 중요하다. 문자 필터를 먼저 돌리면 대괄호만 지워지고 **태그 내용이 남는다.**
#   "[excited][wave] 안녕" → "excited wave 안녕" → TTS 가 "익사이티드 웨이브"라고 읽는다.
#   Ch20 §4 가 경고한 바로 그 사고다. 태그를 **통째로** 먼저 걷어내야 한다.
_TAG = re.compile(r"^\s*(?:\[\w+\]\s*)+")          # 맨 앞 [감정][동작]
_TAG_ANY = re.compile(r"\[[^\]]{1,20}\]")          # 문장 중간에 낀 것까지
_CLEAN = re.compile(r"[^가-힣a-zA-Z0-9 .,!?~]")
_SENT = re.compile(r"(?<=[.!?~])\s+")


def normalize(text, max_sentences=None):
    t = _TAG_ANY.sub(" ", _TAG.sub("", text or ""))   # ① 태그를 내용째 제거
    t = re.sub(r"\s+", " ", _CLEAN.sub(" ", t)).strip()   # ② 그 다음 문자 필터
    if max_sentences:
        parts = [s.strip() for s in _SENT.split(t) if s.strip()][:max_sentences]
        t = " ".join(parts)
    return t


def synth(text, voice, rate="+0%", pitch="+0Hz", tag="v"):
    mp3 = os.path.join(OUT, f"{tag}.mp3")
    # ★ 음수 값은 반드시 '--opt=값' 으로 붙여 쓴다.
    #   '--pitch', '-8Hz' 로 띄우면 CLI 가 '-8Hz' 를 **옵션으로 오인**해 실패한다.
    #   Ch03 §2 의 "슬픔은 느리고 낮게"(= 음수 pitch)를 그대로 따르면 여기서 막힌다.
    cmd = [sys.executable, "-m", "edge_tts", "--voice", voice, "--text", text,
           f"--rate={rate}", f"--pitch={pitch}", "--write-media", mp3]
    p = subprocess.run(cmd, capture_output=True, timeout=40)
    if p.returncode or not os.path.exists(mp3):
        print(f"  ! 합성 실패: {p.stderr.decode(errors='replace')[:160]}")
        return None
    return mp3


def verify(mp3):
    """Ch03 §6 — 들어보기 전에 코드가 먼저 확인할 것 셋."""
    wav = mp3.replace(".mp3", "_16k.wav")
    media.normalize_audio(mp3, wav)          # 16kHz 모노로 변환
    info = media.probe(wav)
    ok = (info.get("sample_rate") == 16000 and info.get("channels") == 1
          and (info.get("duration") or 0) > 0.1)
    return wav, info, ok


def main():
    ap = argparse.ArgumentParser(description="목소리 층 실습 (Ch03)")
    ap.add_argument("text", nargs="?", default="안녕하세요. 오늘은 목소리 층을 만듭니다.")
    ap.add_argument("--file", help="대본 파일(UTF-8)")
    ap.add_argument("--voice", default=VOICES["female"])
    ap.add_argument("--styles", action="store_true", help="감정 프리셋 4종 비교")
    ap.add_argument("--max-sentences", type=int, help="앞 N문장만")
    a = ap.parse_args()

    raw = open(a.file, encoding="utf-8").read() if a.file else a.text
    text = normalize(raw, a.max_sentences)
    if raw != text:
        print(f"\n  정규화 전 : {raw[:70]}")
        print(f"  정규화 후 : {text[:70]}")
    if not text:
        print("  빈 대본입니다."); return 1

    jobs = ([(k, v["rate"], v["pitch"], v["desc"]) for k, v in STYLES.items()]
            if a.styles else [("v", "+0%", "+0Hz", "기본")])

    print(f"\n  음성 : {a.voice}\n")
    rows, bad = [], 0
    for tag, rate, pitch, desc in jobs:
        mp3 = synth(text, a.voice, rate, pitch, tag)
        if not mp3:
            bad += 1; continue
        wav, info, ok = verify(mp3)
        rows.append((tag, desc, info.get("duration"), info.get("sample_rate"),
                     info.get("channels"), ok))
        if not ok:
            bad += 1

    print(f"  {'프리셋':<8}{'설명':<22}{'길이(초)':>9}{'sr':>7}{'ch':>4}  판정")
    for tag, desc, dur, sr, ch, ok in rows:
        print(f"  {tag:<8}{desc:<22}{dur or 0:>9.2f}{sr or 0:>7}{ch or 0:>4}  "
              f"{'OK' if ok else 'FAIL'}")

    if rows:
        d = rows[0][2] or 0
        print(f"\n  ▸ 이 길이({d:.2f}초)를 기록해 두세요. Ch14 의 길이 대조 기준입니다.")
        print(f"  ▸ 산출물: {OUT}")
        if a.styles:
            print("  ▸ 네 파일을 **직접 들어보세요.** 파라미터 감정 제어의 한계도 함께 보입니다(Ch03 §5).")
    print()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
