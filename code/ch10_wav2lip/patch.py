# -*- coding: utf-8 -*-
"""
Ch10 §4 — 낡은 저장소를 *지금* 라이브러리에 맞게 고치는 패치 (②′ 경로)

핀(numpy 1.23.5 · librosa 0.9.2)으로 환경을 낮추는 대신, 저장소 쪽을 고친다.
저자가 2026-06 에 numpy 1.26 으로 돌리려고 만든 것을 그대로 옮겼다(_work/attempts.json).

    python patch.py [저장소 경로]      기본값은 저자의 경로 — 여러분 것으로 바꾸세요
"""
import re, pathlib, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402
sys.stdout.reconfigure(encoding="utf-8")
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else where("wav2lip"))
# 1) 제거된 numpy 별칭 → 파이썬 빌트인 (np.float32/int32 등은 \w 경계로 보호)
alias = {"float":"float","int":"int","bool":"bool","object":"object","complex":"complex","str":"str"}
pat = re.compile(r"np\.(float|int|bool|object|complex|str)(?![\w])")
n_alias = 0
for f in root.rglob("*.py"):
    t = f.read_text(encoding="utf-8", errors="ignore"); orig = t
    t, c = pat.subn(lambda m: alias[m.group(1)], t)
    n_alias += c
    # 2) librosa.filters.mel 위치인자 → 키워드 (librosa 0.10+ 필수)
    t = t.replace("librosa.filters.mel(hp.sample_rate, hp.n_fft,",
                  "librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft,")
    if t != orig:
        f.write_text(t, encoding="utf-8")
print("numpy 별칭 치환:", n_alias, "건")
# 검증
print("남은 bare np.int/float/bool:",
      sum(len(re.findall(r"np\.(float|int|bool|object|complex)(?![\w])", f.read_text(encoding='utf-8',errors='ignore'))) for f in root.rglob("*.py")))
print("audio.py mel 라인:", [l.strip() for l in (root/"audio.py").read_text(encoding="utf-8").splitlines() if "filters.mel" in l])
