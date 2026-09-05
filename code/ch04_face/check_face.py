# -*- coding: utf-8 -*-
"""
Ch04 — 소스 이미지 · 드라이버 영상 적합성 체커

렌더가 4분 걸린 뒤에 "소스가 나빴네" 를 알게 되는 것보다, **넣기 전에 0.1초**
만에 아는 편이 낫다. Ch14 의 `mux_lint.py` 와 같은 사상이다.

    python check_face.py photo.jpg              소스 이미지 검사
    python check_face.py --driver clip.mp4      드라이버 영상 검사
    python check_face.py --driver clip.mp4 --audio v.wav
    python check_face.py --demo                 합성 예제로 시연

**얼굴 검출은 OpenCV 의 Haar 캐스케이드** 를 쓴다. 정확한 검출기는 아니지만
*얼굴이 화면의 몇 할인가* 를 재는 데는 충분하고, 설치가 필요 없다.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from criteria import DRIVER, FAIL, OK, SOURCE, WARN, grade, verdict  # noqa: E402


def _cascade():
    import cv2
    p = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    return cv2.CascadeClassifier(p)


def faces_in(gray) -> list:
    """(x, y, w, h) 목록. 큰 것부터."""
    import cv2
    g = np.asarray(gray, dtype=np.uint8)
    found = _cascade().detectMultiScale(g, scaleFactor=1.1, minNeighbors=5,
                                        minSize=(24, 24))
    return sorted((tuple(int(v) for v in f) for f in found),
                  key=lambda f: -f[2] * f[3])


def image_metrics(gray, box=None) -> dict:
    """이미지 한 장에서 §2 의 조건을 숫자로 뽑는다.

    `box=(x, y, w, h)` 를 주면 검출기를 건너뛰고 그 상자를 얼굴로 본다.
    **검출기는 사람 얼굴용이다** — 고양이·개 사진에서는 0개를 내거나 엉뚱한 곳을 잡는다.
    동물 소스(Ch13)를 재려면 상자를 직접 주어야 한다.
    """
    g = np.asarray(gray, dtype=np.float32)
    h, w = g.shape
    found = [tuple(int(v) for v in box)] if box else faces_in(g)
    m = {"faces": len(found), "min_side": int(min(h, w))}

    if not found:
        m.update(face_ratio=None, brightness=None, evenness=None,
                 clipping=None, symmetry=None)
        return m

    fx, fy, fw, fh = found[0]
    m["face_ratio"] = round(fh / h, 3)
    face = g[fy:fy + fh, fx:fx + fw]
    m["brightness"] = round(float(face.mean()), 1)

    # 조명이 고른가 — 사분면 평균의 최소/최대 비
    hh, hw = fh // 2, fw // 2
    quads = [face[:hh, :hw], face[:hh, hw:], face[hh:, :hw], face[hh:, hw:]]
    means = [float(q.mean()) for q in quads if q.size]
    m["evenness"] = round(min(means) / max(means), 3) if means and max(means) else None

    blown = float(((face > 250) | (face < 5)).mean())
    m["clipping"] = round(blown, 3)

    # 정면인가 — 왼쪽 절반과 오른쪽 절반을 뒤집어 맞춰 본다
    left, right = face[:, :hw], face[:, fw - hw:][:, ::-1]
    n = min(left.shape[1], right.shape[1])
    if n > 2:
        a, b = left[:, :n].ravel(), right[:, :n].ravel()
        denom = a.std() * b.std()
        m["symmetry"] = round(float(((a - a.mean()) * (b - b.mean())).mean() / denom), 3) \
            if denom else None
    else:
        m["symmetry"] = None
    return m


def video_metrics(path: str, audio_seconds=None, sample=24) -> dict:
    """드라이버 영상에서 §3 의 조건을 뽑는다. 프레임을 듬성듬성 본다."""
    import cv2
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"열 수 없다: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = total / fps if fps else 0.0

    step = max(1, total // sample) if total else 1
    ratios, prev, diffs = [], None, []
    i = 0
    while True:
        okf, frame = cap.read()
        if not okf:
            break
        if i % step == 0:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(g, (160, 90))
            if prev is not None:
                diffs.append(float(np.abs(small.astype(np.float32)
                                          - prev).mean()) / 255.0)
            prev = small.astype(np.float32)
            f = faces_in(g)
            if f:
                ratios.append(f[0][3] / g.shape[0])
        i += 1
    cap.release()

    m = {"duration": round(dur, 2), "fps": round(fps, 3),
         "face_ratio": round(float(np.median(ratios)), 3) if ratios else None,
         "motion": round(float(np.mean(diffs)), 4) if diffs else None}
    if audio_seconds:
        m["duration_ratio"] = round(dur / audio_seconds, 2)
    return m


MARK = {OK: "OK  ", WARN: "경고", FAIL: "실패"}


def show(title, metrics, table):
    rows = grade(metrics, table)
    print(f"\n  ── {title} ──")
    for lv, name, val, fix in rows:
        v = "?" if val is None else val
        print(f"   [{MARK[lv]}] {name:12} {str(v):>8}" + (f"   {fix}" if fix else ""))
    v = verdict(rows)
    print(f"   → {MARK[v]}")
    return v


def _demo():
    from closeup import synth_frame
    print("\n  합성 프레임으로 시연합니다 — 실제 사진은 인자로 넘기세요.")
    for label, ratio in (("클로즈업 (얼굴 0.70)", 0.70), ("미디엄샷 (얼굴 0.25)", 0.25)):
        img, _ = synth_frame(ratio, 0.3)
        m = image_metrics(img)
        show(label, m, SOURCE)
    print("\n  합성 얼굴은 Haar 가 잘 못 잡습니다 — 값이 '?' 면 검출 실패입니다.")
    print("  실제 사진에서는 잡힙니다. 이 시연의 요점은 **기준표가 도는가** 입니다.\n")


def main() -> int:
    a = sys.argv[1:]
    if not a or a[0] == "--demo":
        _demo()
        return 0
    if a[0] == "--driver":
        audio = None
        if "--audio" in a:
            import wave
            w = wave.open(a[a.index("--audio") + 1], "rb")
            audio = w.getnframes() / w.getframerate()
            w.close()
        m = video_metrics(a[1], audio)
        print(f"\n  길이 {m['duration']}초 · {m['fps']}fps")
        return 0 if show(os.path.basename(a[1]), m, DRIVER) != FAIL else 1

    import cv2
    box = None
    if "--box" in a:
        box = tuple(int(v) for v in a[a.index("--box") + 1].split(","))
    # 한글 파일명은 cv2.imread 가 못 읽는다(부록 F · Ch28 §4) — 바이트로 읽어 디코딩한다
    g = cv2.imread(a[0], cv2.IMREAD_GRAYSCALE)
    if g is None and os.path.exists(a[0]):
        g = cv2.imdecode(np.fromfile(a[0], dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if g is not None:
            print("  (한글·비ASCII 경로 — imdecode 로 우회해 읽었다)")
    if g is None:
        print(f"  읽을 수 없다: {a[0]}")
        return 2
    m = image_metrics(g, box)
    if not box and not m["faces"]:
        print("  얼굴 검출 0 — 이 검출기는 **사람 얼굴용** 이다. 동물 사진이면"
              " `--box x,y,w,h` 로 얼굴 상자를 직접 주고 다시 재라(Ch13).")
    return 0 if show(os.path.basename(a[0]), m, SOURCE) != FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
