# -*- coding: utf-8 -*-
"""
Ch02 — 환경 점검기 (무GPU 트랙 / GPU 트랙)

환경 문제로 첫 시간을 날리는 것을 막는다. **되는 것과 안 되는 것을 3초에 구분한다.**

실행:  python doctor.py            (무GPU 트랙만)
       python doctor.py --gpu      (GPU 트랙까지)

종료 코드 0 = 무GPU 트랙 준비 완료.
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402

OK, NO, WARN = "  [OK]  ", "  [--]  ", "  [!!]  "
fails = []


def chk(cond, name, hint="", critical=True):
    print((OK if cond else (NO if critical else WARN)) + name + ("" if cond else f"  → {hint}"))
    if not cond and critical:
        fails.append(name)
    return cond


def has(mod):
    return importlib.util.find_spec(mod) is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", action="store_true", help="GPU 트랙(Track A)까지 점검")
    a = ap.parse_args()

    print("\n■ 무GPU 트랙 — Track B·C 는 이것만 있으면 됩니다\n")

    v = sys.version_info
    chk(v >= (3, 10), f"Python {v.major}.{v.minor}.{v.micro}", "3.10 이상 필요")

    for m, why in (("fastapi", "웹 서버"), ("uvicorn", "ASGI 실행기"), ("edge_tts", "무료 TTS")):
        chk(has(m), f"{m:<10} ({why})", f"pip install {m.replace('_', '-')}")

    ff = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")
    if chk(bool(ff), "ffmpeg", "설치 후 PATH 등록 (부록 A §1)"):
        try:
            ver = subprocess.run([ff, "-version"], capture_output=True, text=True,
                                 timeout=10).stdout.split("\n")[0]
            print(f"         {ver[:70]}")
        except Exception:
            pass

    # 부록 H §2 — 이 한 줄이 없어서 반나절을 잃는 사람이 있다
    chk(os.environ.get("PYTHONUTF8") == "1", "PYTHONUTF8=1",
        "한국어 Windows 에서 이모지 출력 시 cp949 오류 방지", critical=False)

    # 부록 H §1 — 작업 경로에 한글이 있으면 OpenCV 가 조용히 실패한다
    here = os.path.abspath(".")
    try:
        here.encode("ascii"); ascii_ok = True
    except UnicodeEncodeError:
        ascii_ok = False
    chk(ascii_ok, "작업 경로가 ASCII", f"한글 경로는 OpenCV 가 못 읽음: {here}", critical=False)

    if a.gpu:
        print("\n■ GPU 트랙 — Track A 에만 필요합니다\n")
        if chk(has("torch"), "torch", "부록 A §2 참조"):
            import torch
            cu = torch.cuda.is_available()
            chk(cu, f"CUDA 사용 가능 (torch {torch.__version__})", "드라이버·휠 버전 확인")
            if cu:
                p = torch.cuda.get_device_properties(0)
                gb = p.total_memory / 1024**3
                print(f"         {p.name} · {gb:.1f}GB")
                if gb < 10:
                    print(f"         ! 12GB 미만 — 배치 크기를 절반으로 (Ch11 §3)")
        for m in ("cv2", "numpy"):
            chk(has(m), m, f"pip install {'opencv-python' if m == 'cv2' else m}")

    print()
    if fails:
        print(f"  {len(fails)}개 미충족: {', '.join(fails)}")
        print("  → 부록 A(환경 구축) · 부록 H(Windows 트러블슈팅)\n")
        return 1
    if a.gpu:
        # Ch02 §4 — 기본 파이썬의 torch 로는 부족하다. Track A 는 conda 환경 두 벌을 쓴다.
        # 각 환경의 python 을 절대 경로로 불러 torch·CUDA 를 직접 묻는다(Ch10 §4 의 격리 원칙).
        envs = {"MuseTalk": os.environ.get("MUSETALK_PY", where("py_musetalk")),
                "LivePortrait": os.environ.get("LIVEPORTRAIT_PY", where("py_liveportrait"))}
        print(chr(10) + "■ 격리 환경 두 벌 — 립싱크 / 리타게팅 (Ch02 §4)" + chr(10))
        for name, py in envs.items():
            if not chk(os.path.exists(py), f"{name:<12} python 있음", f"conda create -n {name} …  (부록 A)", critical=False):
                continue
            try:
                out = subprocess.run([py, "-c", "import torch;print(torch.__version__, torch.cuda.is_available())"],
                                     capture_output=True, text=True, timeout=60).stdout.strip()
                ver, cuda = (out.split() + ["", ""])[:2]
                chk(cuda == "True", f"{name:<12} torch {ver} · CUDA {cuda}", "CUDA 빌드로 다시 설치", critical=False)
            except Exception as e:
                chk(False, f"{name:<12} torch 확인 실패", str(e)[:60], critical=False)

    print("  준비 완료. Ch01 의 `code/ch01_stack/app.py` 를 실행해 보세요.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
