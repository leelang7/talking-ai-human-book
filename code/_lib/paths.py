# -*- coding: utf-8 -*-
"""
ASCII 작업본 — Windows 한글 경로 회피 (부록 F 실패 14번 / 부록 H §1)

OpenCV 의 파일 읽기는 Windows 에서 시스템 기본 인코딩(cp949)으로 경로를 처리한다.
한글이 포함된 경로는 조용히 실패하거나 빈 이미지를 반환한다. **에러가 안 나서 더 위험하다.**

사용자에게 "한글 파일명 쓰지 마세요" 라고 하는 것은 해법이 아니다. 코드가 처리한다.

    with AsciiWork("outputs") as w:
        src = w.take("입력/하늘이.jpg")     # -> work/a1b2c3d4.jpg
        ...파이프라인 실행...
        w.deliver(result, "하늘이_추모.mp4")  # 최종만 원하는 이름으로
"""
import hashlib
import os
import shutil
import tempfile


def is_ascii(p: str) -> bool:
    try:
        str(p).encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def imread_any(path: str):
    """한글 경로에서도 동작하는 이미지 로드. cv2.imread 대신 쓴다.

    파이썬이 바이트로 읽고 메모리에서 디코딩한다 — 경로를 라이브러리에 넘기지 않는다.
    """
    import cv2
    import numpy as np
    with open(path, "rb") as f:
        buf = np.frombuffer(f.read(), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"이미지 디코딩 실패: {path}")
    return img


class AsciiWork:
    """입력을 ASCII 이름으로 복사해 두고 그 안에서만 파이프라인을 돌린다."""

    def __init__(self, out_dir: str = "outputs", work_dir: str | None = None, keep: bool = False):
        self.out_dir = os.path.abspath(out_dir)
        self.keep = keep
        self._tmp = work_dir is None
        self.work = os.path.abspath(work_dir or tempfile.mkdtemp(prefix="hb_"))
        os.makedirs(self.work, exist_ok=True)
        os.makedirs(self.out_dir, exist_ok=True)
        if not is_ascii(self.work):
            raise RuntimeError(
                f"작업 디렉터리 경로에 비ASCII 문자가 있습니다: {self.work}\n"
                "TEMP 환경변수나 work_dir 를 ASCII 경로로 지정하세요."
            )

    def take(self, src: str) -> str:
        """입력 파일을 작업 디렉터리에 ASCII 이름으로 복사하고 그 경로를 준다."""
        src = os.path.abspath(src)
        if not os.path.exists(src):
            raise FileNotFoundError(src)
        ext = os.path.splitext(src)[1].lower()
        tag = hashlib.sha1(src.encode("utf-8")).hexdigest()[:8]
        dst = os.path.join(self.work, f"{tag}{ext}")
        # 부록 F 실패 17번 — 원본과 대상이 같으면 복사하지 않는다
        if os.path.normcase(src) != os.path.normcase(dst):
            shutil.copy2(src, dst)
        return dst

    def path(self, name: str) -> str:
        """작업 디렉터리 안의 중간 산출물 경로. 이름은 ASCII 로만."""
        if not is_ascii(name):
            raise ValueError(f"중간 산출물 이름은 ASCII 여야 합니다: {name}")
        return os.path.join(self.work, name)

    def deliver(self, produced: str, final_name: str) -> str:
        """최종 결과만 원하는(한글 가능) 이름으로 내보낸다."""
        dst = os.path.join(self.out_dir, final_name)
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        shutil.copy2(produced, dst)
        return dst

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self._tmp and not self.keep:
            shutil.rmtree(self.work, ignore_errors=True)
        return False


# ── 기계마다 다른 경로 ─────────────────────────────────────────────────
# 이 책의 스크립트는 저자의 기계에서 만들어졌다. 저장소를 받은 사람의 기계에는
# `C:/lsc/Avatar/MuseTalk` 도 `.../envs/MuseTalk/python.exe` 도 없다.
# 그래서 **경로를 코드에 박지 않고** 세 곳에서 순서대로 찾는다.
#
#   ① 환경변수            set BOOK_MUSETALK=D:\repos\MuseTalk
#   ② book.config.json    저장소 루트에 두는 파일 (아래 KEYS 참조)
#   ③ 기본값              저자의 기계 값 — 문서로서의 예시다
#
# 없으면 **조용히 넘어가지 않고** 무엇을 설정해야 하는지 말하고 멈춘다(Ch02 §4).
import json as _json

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # …/code 의 부모
_CFG_PATH = os.path.join(_ROOT, "book.config.json")
_CFG_CACHE = {}

#: 설정 키 → (기본값, 무엇인가)
KEYS = {
    "avatar":       ("C:/lsc/Avatar", "모델 저장소들을 모아 둔 작업 폴더"),
    "liveportrait": ("C:/lsc/Avatar/LivePortrait", "LivePortrait 저장소"),
    "musetalk":     ("C:/lsc/Avatar/MuseTalk", "MuseTalk 저장소"),
    "wav2lip":      ("C:/lsc/p/w2l_test/Wav2Lip", "Wav2Lip 저장소"),
    "gemini_key":   ("C:/lsc/Avatar/gemini_key.txt", "Gemini API 키가 든 텍스트 파일"),
    "py_liveportrait": ("C:/Users/leesc/miniconda3/envs/LivePortrait/python.exe", "LivePortrait 환경의 python"),
    "py_musetalk":     ("C:/Users/leesc/miniconda3/envs/MuseTalk/python.exe", "MuseTalk 환경의 python"),
    "py_wav2lip":      ("C:/lsc/p/w2l_test/venv/Scripts/python.exe", "Wav2Lip 환경의 python"),
}


def _cfg():
    if not _CFG_CACHE and os.path.exists(_CFG_PATH):
        try:
            _CFG_CACHE.update(_json.load(open(_CFG_PATH, encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return _CFG_CACHE


def where(key: str, required: bool = False) -> str:
    """설정된 경로를 돌려준다. `required=True` 면 없을 때 무엇을 설정할지 알리고 멈춘다."""
    if key not in KEYS:
        raise KeyError(f"모르는 설정 키: {key} — 아는 것: {', '.join(KEYS)}")
    default, what = KEYS[key]
    val = os.environ.get("BOOK_" + key.upper()) or _cfg().get(key) or default
    if required and not os.path.exists(val):
        raise SystemExit(
            f"\n  [{key}] 를 찾을 수 없습니다 — {what}\n"
            f"      지금 값 : {val}\n"
            f"      고치는 법: 환경변수 BOOK_{key.upper()} 를 두거나,\n"
            f"                 {_CFG_PATH} 에 {{\"{key}\": \"…\"}} 를 적으세요.\n"
            f"      (기본값은 저자의 기계 경로입니다 — 여러분의 기계와 다릅니다)\n")
    return val


def gemini_key(required: bool = True) -> str:
    """Gemini 키 문자열. 환경변수 GEMINI_API_KEY 가 있으면 그것을 먼저 쓴다."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()
    return open(where("gemini_key", required), encoding="utf-8").read().strip()
