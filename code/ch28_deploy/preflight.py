# -*- coding: utf-8 -*-
"""
Ch28 §2·§4 — 배포 전 점검

배포는 **돌려 보고 아는 것이 가장 비싼 일** 이다. 실시간 서비스는 사용자가
접속해서 알게 되고, 렌더 컨테이너는 4분 뒤에 알게 된다.

여기 있는 것은 전부 **파일과 설정만 보고 판단할 수 있는 것들** 이다.
GPU 도 네트워크도 필요 없다.

    python preflight.py                 이 폴더 기준으로 점검
    python preflight.py --demo          통과/실패 예제를 나란히
"""
import os
import re
import sys

# 걸린 것을 "OK" 로 찍으면 아무도 안 읽는다. 등급을 나눈다.
CRIT, WARN, NOTE, INFO = "CRIT", "WARN", "NOTE", "INFO"

# ── §4 컨테이너 — 실행 시점에 아무것도 내려받지 않는다 ────────────────
#
# 이 원칙이 재현성을 만들고, **그대로 분산 가능성이 된다**(§6).
# 워커가 이미지를 받아 바로 돌릴 수 있으려면 안에 다 들어 있어야 한다.
RUNTIME_FETCH = [
    (r"from_pretrained\((?![^)]*local_files_only)", "실행 중 모델을 내려받는다"),
    (r"hf_hub_download|snapshot_download", "실행 중 허브에서 받는다"),
    (r"torch\.hub\.load", "실행 중 torch.hub 를 친다"),
    (r"\bwget\b|\bcurl\b(?!.*--help)", "실행 중 파일을 받는다"),
    (r"pip\s+install", "실행 중 패키지를 깐다"),
]

DOCKER_MUST = [
    ("COPY", "모델·가중치를 이미지에 넣었는가", CRIT),
    ("ENV ", "버전과 경로를 고정했는가", WARN),
]
DOCKER_SMELL = [
    (r"FROM\s+\S+:latest", "베이스가 :latest 다 — 내일 다른 이미지가 된다", CRIT),
]
# 설치 캐시를 지우는 방법은 도구마다 다르다. 하나만 알면 오탐이 난다 —
# 실제로 `apt-get install ... && rm -rf /var/lib/apt/lists/*` 를 지적했다.
CACHE_CLEANED = ("--no-cache-dir", "rm -rf /var/lib/apt/lists",
                 "rm -rf /root/.cache", "apt-get clean")

# 네트워크를 끊고 돌리겠다는 선언. 있으면 §4 를 진지하게 지킨 것이다.
OFFLINE_HINTS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "local_files_only")

# 서비스인가 배치 잡인가를 가르는 실마리
SERVER_HINTS = ("fastapi", "flask", "uvicorn", "gunicorn", "aiohttp",
                "django", "app.get(", "app.post(", "@app.route")

# ── §2 실시간 서비스 ────────────────────────────────────────────────
SERVICE_MUST = [
    ("health", "헬스체크 경로가 있는가 — 없으면 죽은 줄도 모른다", CRIT),
    ("timeout", "타임아웃을 잡았는가 (Ch08 §7)", WARN),
]
SECRET_SMELL = [
    (r"(?i)(api[_-]?key|secret|token)\s*=\s*[\"'][A-Za-z0-9_\-]{16,}[\"']",
     "키가 코드에 박혀 있다"),
]


def scan_text(text, rules):
    out = []
    for pat, msg in rules:
        m = re.search(pat, text, re.M)
        if m:
            out.append((msg, m.group(0)[:44]))
    return out


def check_container(dockerfile: str, entry_sources: list) -> list:
    """(수준, 항목, 설명) 목록."""
    rows = []
    for token, why, lv in DOCKER_MUST:
        rows.append((INFO if token in dockerfile else lv, why,
                     "있음" if token in dockerfile else "없음"))
    for pat, why, lv in DOCKER_SMELL:
        if re.search(pat, dockerfile, re.M):
            rows.append((lv, why, re.search(pat, dockerfile, re.M).group(0)[:44]))

    for m in re.finditer(r"^\s*RUN\s+(.+?)(?=\n(?!\s)|\Z)", dockerfile, re.M | re.S):
        line = m.group(1)
        if re.search(r"apt-get install|pip install", line) and \
                not any(c in line for c in CACHE_CLEANED):
            rows.append((NOTE, "설치 캐시가 이미지에 남는다", line.split("&&")[0][:40]))

    offline = any(h in dockerfile for h in OFFLINE_HINTS)
    rows.append((INFO if offline else NOTE, "오프라인 실행을 선언했는가 (§4)",
                 "있음" if offline else "없음"))

    for src in entry_sources:
        for msg, hit in scan_text(src, RUNTIME_FETCH):
            rows.append((CRIT, f"§4 {msg}", hit))
    return rows


def looks_like_service(sources: list) -> bool:
    """서비스인가 배치 잡인가.

    **이 구분이 없으면 렌더 잡에 헬스체크를 요구한다.** 실제로 저자의 잡
    컨테이너를 점검했더니 그렇게 나왔다 — 엔드포인트가 없는 것이 정상인데
    치명으로 찍혔다. **검사는 대상의 종류를 먼저 알아야 한다.**
    """
    j = "\n".join(sources).lower()
    return any(h in j for h in SERVER_HINTS)


def check_service(sources: list) -> list:
    if not looks_like_service(sources):
        return [(INFO, "서비스가 아니라 배치 잡이다", "헬스체크·타임아웃 검사 생략")]
    rows = []
    joined = "\n".join(sources)
    for token, why, lv in SERVICE_MUST:
        rows.append((INFO if token in joined else lv, why,
                     "있음" if token in joined else "없음"))
    for msg, hit in scan_text(joined, SECRET_SMELL):
        rows.append((CRIT, msg, hit))
    return rows


def check_consent(consent_fields: list) -> list:
    """§6 — 남의 GPU 로 보낼 거면 동의서에 그 항목이 있어야 한다.

    기술 점검표에 이것을 **같이** 넣은 것이 의도다. 윤리 문서를 따로 두면
    배포 전에 아무도 안 본다.
    """
    need = ["어디서 처리되는가", "보관 기간", "철회 방법"]
    return [(CRIT if n not in consent_fields else INFO,
             f"동의서 항목 — {n}", "있음" if n in consent_fields else "없음")
            for n in need]


def verdict(rows):
    return CRIT if any(r[0] == CRIT for r in rows) else (
        WARN if any(r[0] == WARN for r in rows) else INFO)


MARK = {CRIT: "치명", WARN: "경고", NOTE: "참고", INFO: "OK  "}


def show(title, rows):
    print(f"\n  ── {title} ──")
    order = {CRIT: 0, WARN: 1, NOTE: 2, INFO: 3}
    for lv, why, detail in sorted(rows, key=lambda r: order[r[0]]):
        print(f"   [{MARK[lv]}] {why:44} {detail}")
    return verdict(rows)


GOOD_DOCKER = """FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04
ENV MODEL_DIR=/opt/models PYTHONUNBUFFERED=1
COPY models/ /opt/models/
COPY app/ /app/
RUN pip install --no-cache-dir -r /app/requirements.txt
CMD ["python", "/app/run.py"]
"""
BAD_DOCKER = """FROM python:latest
RUN pip install torch
CMD ["python", "/app/run.py"]
"""
GOOD_ENTRY = """model = load(MODEL_DIR, local_files_only=True)
"""
BAD_ENTRY = """model = AutoModel.from_pretrained("some/repo")
API_KEY = "sk-abcdefghijklmnopqrstuvwx"
"""


def _demo():
    print("\n  같은 일을 하는 두 배포를 나란히 점검합니다.")
    a = show("잘 만든 것", check_container(GOOD_DOCKER, [GOOD_ENTRY])
             + check_service(["@app.get('/health')", "timeout=5"])
             + check_consent(["어디서 처리되는가", "보관 기간", "철회 방법"]))
    b = show("흔한 것", check_container(BAD_DOCKER, [BAD_ENTRY])
             + check_service([BAD_ENTRY, "@app.get('/chat')"])
             + check_consent(["보관 기간"]))
    print(f"\n  → 왼쪽 {MARK[a].strip()} · 오른쪽 {MARK[b].strip()}")
    print("  오른쪽도 로컬에서는 잘 돕니다. 문제는 **내일 다른 이미지가 되고,**")
    print("  **워커가 인터넷 없이 못 돌고,** **키가 이미지에 박혀 나간다** 는 것입니다.\n")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] != "--demo":
        root = sys.argv[1]
        df = os.path.join(root, "Dockerfile")
        dockerfile = open(df, encoding="utf-8").read() if os.path.exists(df) else ""
        srcs = []
        for dp, _, fs in os.walk(root):
            for f in fs:
                if f.endswith(".py"):
                    srcs.append(open(os.path.join(dp, f), encoding="utf-8",
                                     errors="replace").read())
        rows = check_container(dockerfile, srcs) + check_service(srcs)
        return 0 if show(root, rows) != CRIT else 1
    _demo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
