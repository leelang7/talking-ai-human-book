# -*- coding: utf-8 -*-
"""
미디어 유틸 — 오디오 정규화 · fps 재해석 mux · 길이 대조 (Ch03 §6 / Ch14)

이 모듈이 막는 실패:
  · 부록 F 8번  — 영상↔음성 길이 불일치로 뒤로 갈수록 싱크 밀림
  · 부록 F 15번 — fps 가 정수형이라 터지는 것
  · Ch03 §6    — 16kHz 모노가 아닌 오디오를 넣고 조용히 이상해지는 것

**setpts 로 늘리지 않는다.** 입력 앞의 -r 로 fps 를 재해석한다 (Ch14 §4).
"""
import json
import os
import shutil
import subprocess
from fractions import Fraction

FFMPEG = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = os.environ.get("FFPROBE_BIN") or shutil.which("ffprobe") or "ffprobe"

# 파이프라인 전체가 참조하는 단일 상수 (Ch14 §5). 분수로 다룬다 — 29.97 = 30000/1001
FPS = Fraction(30000, 1001)


def _win(p: str) -> str:
    """Git Bash 의 `/c/foo` 를 `C:/foo` 로. ffmpeg.exe 는 전자를 못 읽는다 (부록 H).

    실제 결과물에 `check_lengths` 를 돌리다 이걸로 죽었다 — 셸이 준 경로를 그대로
    넘겼기 때문이다. 경로처럼 생긴 인자만 바꾸고 옵션은 건드리지 않는다.
    """
    s = str(p)
    if os.name == "nt" and len(s) > 3 and s[0] == "/" and s[2] == "/" and s[1].isalpha():
        return f"{s[1].upper()}:{s[2:]}"
    return s


def _run(cmd: list[str]) -> str:
    cmd = [cmd[0]] + [_win(a) if a.startswith("/") and len(a) > 3 else a for a in cmd[1:]]
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if p.returncode:
        raise RuntimeError(f"명령 실패 ({p.returncode}): {' '.join(cmd[:3])}...\n{p.stderr[-800:]}")
    return p.stdout


def probe(path: str) -> dict:
    """길이·fps·샘플레이트·채널을 한 번에. 값이 없으면 None 으로 둔다."""
    out = _run([FFPROBE, "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", path])
    d = json.loads(out)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    info = {"duration": float(d["format"].get("duration", 0)) or None,
            "has_video": v is not None, "has_audio": a is not None}
    if v:
        r = v.get("r_frame_rate", "0/1")
        info["fps"] = float(Fraction(r)) if "/" in r and not r.startswith("0/") else None
        info["fps_raw"] = r
        info["width"], info["height"] = v.get("width"), v.get("height")
        n = v.get("nb_frames")
        info["frames"] = int(n) if n and n.isdigit() else None
    if a:
        info["sample_rate"] = int(a.get("sample_rate", 0)) or None
        info["channels"] = a.get("channels")
    return info


def normalize_audio(src: str, dst: str, rate: int = 16000, mono: bool = True) -> str:
    """립싱크 모델이 기대하는 16kHz 모노 wav 로 정규화 (Ch03 §6).

    이 단계를 건너뛰면 에러 없이 이상한 결과가 나온다. 그게 제일 나쁘다.
    """
    _run([FFMPEG, "-y", "-loglevel", "error", "-i", src,
          "-ar", str(rate), "-ac", "1" if mono else "2", "-vn", dst])
    return dst


def mux(video: str, audio: str, out: str, fps: Fraction | float | None = None,
        pix_fmt: str = "yuv420p") -> str:
    """영상 + 음성 결합. fps 를 지정하면 **입력을 그 fps 로 재해석** 한다.

    -r 이 -i **앞** 에 오는 것이 핵심 (Ch14 §4).
      앞  = "이 입력을 이 fps 로 해석하라"   ← 우리가 원하는 것
      뒤  = "출력을 이 fps 로 만들어라"      ← 프레임을 버리거나 복제한다
    """
    fps = FPS if fps is None else fps
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    if fps:
        cmd += ["-r", f"{Fraction(fps).numerator}/{Fraction(fps).denominator}"]
    cmd += ["-i", video, "-i", audio,
            "-map", "0:v:0", "-map", "1:a:0",          # 스트림 매핑 명시 — 원본 오디오 섞임 방지
            "-c:v", "libx264", "-pix_fmt", pix_fmt,    # yuv420p 아니면 일부 브라우저가 재생 못 함
            "-c:a", "aac", "-shortest", out]
    _run(cmd)
    return out


def make_idle_loop(src_video: str, out: str) -> str:
    """원본 + 역재생을 이어붙여 이음매 없는 아이들 루프를 만든다 (Ch08 §2).

    그냥 반복하면 마지막 프레임과 첫 프레임이 달라서 튄다.
    앞뒤로 왕복하면 시작과 끝이 같은 프레임이므로 무한 반복해도 안 보인다.
    """
    _run([FFMPEG, "-y", "-loglevel", "error", "-i", src_video,
          "-filter_complex", "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[v]",
          "-map", "[v]", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", out])
    return out


def check_lengths(video: str, audio: str, tol: float = 0.1) -> dict:
    """영상과 음성 길이를 대조한다. 파이프라인 끝에 자동 게이트로 건다 (Ch14 §6)."""
    v, a = probe(video), probe(audio)
    diff = abs((v["duration"] or 0) - (a["duration"] or 0))

    # ★ 길이만 비교하면 놓치는 것이 있다 — **프레임 수** 다.
    #
    # 실측: MuseTalk 이 6.072초 음성에 176프레임을 냈다(29.97fps 면 182 이어야 한다).
    # LivePortrait 이 그 176프레임을 29fps 로 쓰자 길이가 6.069초가 되어 음성과 '맞았다'.
    # 길이 검사는 통과, 그런데 재생 속도는 3.3% 느리다 — 뒤로 갈수록 밀린다(Ch14 §2).
    # -r 30000/1001 로 재해석하면 속도는 맞지만 0.2초가 모자란다. 어느 쪽이든 원인은
    # **상류가 프레임을 덜 낸 것** 이고, 길이만 봐서는 그것이 안 보인다.
    fps = v.get("fps") or 0.0
    frames = v.get("frames")
    expected = round((a["duration"] or 0) * fps) if fps else None
    shortfall = ((expected - frames) / fps) if (fps and frames is not None and expected) else None
    ok = diff <= tol and (shortfall is None or abs(shortfall) <= tol)
    return {"video": v["duration"], "audio": a["duration"], "diff": round(diff, 3),
            "frames": frames, "expected_frames": expected,
            "shortfall_s": (round(shortfall, 3) if shortfall is not None else None),
            "ok": ok, "video_fps": v.get("fps_raw")}
