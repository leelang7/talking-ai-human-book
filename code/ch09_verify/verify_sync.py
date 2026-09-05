# -*- coding: utf-8 -*-
"""
싱크 검증 — 발화구간 × 입 활발도 상위 N프레임 적중률 (Ch09)

이 책에서 가장 중요한 스크립트다. 저자가 며칠을 태운 실패(부록 F 18번)를 막는다.

  ✗ 틀린 지표 : corr(입 벌림, 음량)
      진짜 립싱크는 음소에 맞춘다. "브"는 크지만 입을 닫는다.
      제대로 된 립싱크에서 이 상관계수는 원래 0에 가깝다.
      이 숫자를 올리려는 시도가 프레임 재배열·시간워핑·보간 외삽을 전부 만들어냈다.

  ○ 옳은 검증 : 입이 가장 활발한 상위 N프레임이 발화구간 안에 있는가
      조용한 구간에서 입이 활발히 움직이면 그건 싱크가 아니라 잡음이다.

실행:
    python verify_sync.py 결과.mp4 --audio 음성.wav --top 15
    python verify_sync.py 결과.mp4                      # 영상 내장 오디오 사용

종료 코드: 0 = 통과, 1 = 기준 미달 (CI/파이프라인 게이트로 그대로 쓴다)
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
import media  # noqa: E402


# ── 1단계: 음성에서 발화구간 뽑기 ──────────────────────────────────────
def speech_spans(audio: str, noise_db: int = -30, min_sil: float = 0.3) -> list[tuple[float, float]]:
    """ffmpeg silencedetect 로 무음을 찾고, 그 여집합을 발화구간으로 돌려준다."""
    p = subprocess.run(
        [media.FFMPEG, "-i", audio, "-af", f"silencedetect=n={noise_db}dB:d={min_sil}",
         "-f", "null", "-"],
        capture_output=True, text=True, errors="replace")
    log = p.stderr
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", log)]
    dur = media.probe(audio)["duration"] or 0.0

    # 무음 구간을 [(s,e)] 로 정리한 뒤 뒤집는다
    sil = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else dur
        sil.append((s, e))
    spans, cur = [], 0.0
    for s, e in sil:
        if s > cur:
            spans.append((cur, s))
        cur = max(cur, e)
    if cur < dur:
        spans.append((cur, dur))
    return [(a, b) for a, b in spans if b - a > 0.05]


# ── 2단계: 영상에서 입 활발도 재기 ─────────────────────────────────────
LAST_ROI = {"mode": None, "box": None}     # 마지막 호출이 어느 영역을 쟀는지 — CLI 가 찍는다


def _mouth_box(frame):
    """입 영역. **얼굴을 먼저 찾고 그 안에서 잡는다.** 못 찾으면 화면 비율로 대신한다.

    실측에서 잡힌 결함이다. 화면 비율(세로 55~90%)로만 잡으면 얼굴이 512² 로 크롭된
    결과물에서는 맞지만, 1280×720 미디엄샷 드라이버에서는 **가슴과 손** 을 잰다.
    그렇게 잰 값은 우연보다 나빴다(0.55배). Haar 로 얼굴을 찾아 그 안의 아래 1/3 을
    잡자 같은 영상이 1.11배가 됐다. 지표가 틀리면 결론이 뒤집힌다 (Ch09 §2).
    동물 얼굴은 Haar 가 못 찾는다 — 그때는 크롭된 결과물이라는 전제로 화면 비율을 쓴다.
    """
    import cv2
    h, w = frame.shape[:2]
    try:
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = sorted(casc.detectMultiScale(g, 1.1, 5, minSize=(24, 24)),
                       key=lambda f: -f[2] * f[3])
    except Exception:
        faces = []
    if len(faces):
        x, y, fw, fh = [int(v) for v in faces[0]]
        LAST_ROI.update(mode="face", box=(x, y, fw, fh))
        return (y + int(fh * 0.58), y + int(fh * 0.92), x + int(fw * 0.25), x + int(fw * 0.75))
    LAST_ROI.update(mode="frame", box=None)
    return (int(h * 0.55), int(h * 0.90), int(w * 0.25), int(w * 0.75))


def mouth_activity(video: str) -> tuple[list[float], float]:
    """프레임마다 입 영역의 변화량. 랜드마크 추적까지 갈 필요 없다 (Ch09 §4).

    영역은 첫 프레임에서 한 번 정한다(`_mouth_box`). 사람 얼굴이면 얼굴 기준,
    아니면 크롭된 결과물이라는 전제로 화면 비율 기준이다.
    """
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    acts, prev, box = [], None, None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if box is None:
            box = _mouth_box(frame)
        y0, y1, x0, x1 = box
        roi = frame[y0:y1, x0:x1]
        g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
        acts.append(0.0 if prev is None else float(np.abs(g - prev).mean()))
        prev = g
    cap.release()
    return acts, fps


# ── 3단계: 적중률 계산 ────────────────────────────────────────────────
def hit_rate(acts: list[float], fps: float, spans: list[tuple[float, float]], top: int) -> dict:
    order = sorted(range(len(acts)), key=lambda i: acts[i], reverse=True)[:top]
    hits = []
    for i in order:
        t = i / fps
        hits.append(any(s <= t <= e for s, e in spans))
    n = sum(hits)
    return {"top": top, "hits": n, "rate": (n / top if top else 0.0),
            "frames": len(acts), "fps": round(fps, 3), "spans": len(spans)}


def main() -> int:
    ap = argparse.ArgumentParser(description="립싱크 싱크 검증 (Ch09)")
    ap.add_argument("video")
    ap.add_argument("--audio", help="생략하면 영상에 내장된 오디오를 뽑아 쓴다")
    ap.add_argument("--top", type=int, default=15, help="검사할 상위 프레임 수")
    ap.add_argument("--threshold", type=float, default=0.8, help="통과 기준 적중률")
    ap.add_argument("--noise-db", type=int, default=-30)
    a = ap.parse_args()

    tmp = None
    audio = a.audio
    if not audio:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        media.normalize_audio(a.video, tmp)
        audio = tmp

    try:
        spans = speech_spans(audio, a.noise_db)
        if not spans:
            print("[!] 발화구간이 없습니다. 무음 파일이거나 임계값(--noise-db)이 부적절합니다.")
            return 1
        acts, fps = mouth_activity(a.video)
        # 적중률 하나만 보면 안 된다 (Ch09 §5). 우연 기준선과 조용한 구간을 같이 본다.
        # 실제 결과물에서 이 CLI 가 기준선 없이 67% 만 찍고 있는 것을 발견하고 고쳤다 —
        # metrics.py 를 만들어 놓고 정작 CLI 는 옛 계산을 쓰고 있었다.
        from metrics import evaluate, explain
        r = evaluate(acts, fps, spans, top=a.top,
                     duration=len(acts) / fps if fps else None)
        roi = "얼굴 기준" if LAST_ROI["mode"] == "face" else "화면 비율 기준(얼굴 미검출 — 크롭 결과물 전제)"
        print(f"  프레임 {len(acts)} · {fps:.3f}fps · 발화구간 {len(spans)}개 · 입 영역: {roi}")
        print(explain(r))
        if not r["pass"]:
            print("\n  확인 순서 (Ch09 §6):")
            print("   1) 드라이버가 클로즈업인가        → 부록 B §2")
            print("   2) 끝부분이 밀리는가              → Ch14 fps 드리프트")
            print("   3) 조용한 구간에서 입이 달싹이는가 → 소스 영상이 계속 말하는 영상인가")
        return 0 if r["pass"] else 1
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


if __name__ == "__main__":
    sys.exit(main())
