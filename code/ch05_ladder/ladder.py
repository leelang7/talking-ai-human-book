# -*- coding: utf-8 -*-
"""
Ch05 — 사다리 결정 트리를 코드로

§2 의 세 질문과 §4 의 시나리오별 답이 이 파일에 있다.
**둘이 어긋나면 테스트가 먼저 안다.**

산문으로 쓴 결정 트리는 조용히 낡는다. 4단이 생겼을 때 §1 은 고쳤는데
§4 의 답 목록은 안 고쳤다면 아무도 모른다. 코드로 옮기면 §4 의 답 여덟 개가
전부 회귀 테스트가 된다.

    python ladder.py            시나리오 여덟 개를 전부 돌린다
"""
from dataclasses import dataclass

R1, R15, R2, R3, R3R, R4 = ("1단 2D 파츠", "1.5단 2.5D 메시", "2단 3D VRM",
                            "3단 신경망 립싱크", "3단 + 리타게팅 경유",
                            "4단 원샷 오디오→영상")

# Ch05 §3 결정표 — 값은 전부 본문에서 온 것이다.
TABLE = {
    R1:  {"gpu": False, "ttfa": 2.0, "human_only": False, "gesture": "제한적",
          "art_style": "완전", "head_turn": False, "per_user": "브라우저"},
    R15: {"gpu": False, "ttfa": 2.0, "human_only": False, "gesture": "제한적",
          "art_style": "완전", "head_turn": "착시", "per_user": "브라우저"},
    R2:  {"gpu": False, "ttfa": 2.0, "human_only": False, "gesture": "가능",
          "art_style": "3D 재해석", "head_turn": True, "per_user": "브라우저"},
    R3:  {"gpu": True, "ttfa": 230.0, "human_only": True, "gesture": "불가",
          "art_style": None, "head_turn": "제한적", "per_user": "GPU 1장"},
    R3R: {"gpu": True, "ttfa": 260.0, "human_only": False, "gesture": "불가",
          "art_style": None, "head_turn": "제한적", "per_user": "GPU 1장"},
    R4:  {"gpu": True, "ttfa": 600.0, "human_only": True, "gesture": "가능(자동)",
          "art_style": None, "head_turn": True, "per_user": "API 예산"},
}

REALTIME_BUDGET = 2.0          # §2 질문 1 — 첫 소리까지 2초


@dataclass
class Need:
    """무엇이 필요한가. **사실감은 여기 없다** — §2 의 요점이다."""
    latency_budget: float           # 첫 소리까지 허용 초. 큰 값 = 배치
    art_style_is_product: bool = False   # 일러스트 화풍이 상품인가
    face_is_human: bool = True           # 사람 얼굴인가
    needs_head_turn: bool = False        # 고개를 돌려야 하는가
    needs_gesture: bool = False          # 손·상반신이 움직여야 하는가
    concurrent_users: int = 1


def choose(need: Need) -> dict:
    """(사다리, 이유들). 이유를 같이 내는 것이 중요하다 —
    **왜 그 칸인지 말하지 못하는 결정은 나중에 못 뒤집는다.**"""
    why = []

    # 질문 1 — 목표 지연. 가장 강력한 필터다.
    if need.latency_budget <= REALTIME_BUDGET:
        why.append(f"지연 예산 {need.latency_budget}초 → 실시간 트랙")
        # 질문 2 — 그림체가 상품인가
        if need.art_style_is_product:
            why.append("그림체가 상품 → 3D 로 재해석하면 원작의 맛이 사라진다")
            if need.needs_head_turn:
                why.append("고개 돌리기가 필요 → 메시 변형이 있어야 한다")
                return {"rung": R15, "why": why}
            return {"rung": R1, "why": why}
        why.append("그림체 제약 없음 → 브라우저 3D 가 제스처까지 준다")
        return {"rung": R2, "why": why}

    # 배치 트랙 — 여기서부터 사실감을 산다
    why.append(f"지연 예산 {need.latency_budget}초 → 품질 트랙")
    if not need.face_is_human:
        why.append("사람 얼굴이 아님 → 직접 적용하면 사람 입술이 그려진다")
        return {"rung": R3R, "why": why}
    if need.needs_gesture:
        why.append("손·상반신까지 필요 → 얼굴만 다루는 3단으로는 부족")
        return {"rung": R4, "why": why}
    why.append("사람 얼굴 · 얼굴만으로 충분")
    return {"rung": R3, "why": why}


def gpu_count(rung: str, concurrent: int) -> int:
    """§3 — *"동시 사용자 = GPU 대수"* 를 숫자로.

    1·2단은 렌더가 사용자 브라우저에서 일어나므로 0 이다. 이 차이가
    사실감이 아니라 **원가 구조** 를 고르는 문제로 만든다.
    """
    return 0 if not TABLE[rung]["gpu"] else max(1, concurrent)


def feasible(rung: str, need: Need) -> list:
    """그 칸을 골랐을 때 어겨지는 제약. 빈 목록이면 문제 없다."""
    t, bad = TABLE[rung], []
    if need.latency_budget <= REALTIME_BUDGET and t["ttfa"] > REALTIME_BUDGET:
        bad.append(f"첫 소리까지 {t['ttfa']:.0f}초 — 예산 {need.latency_budget}초를 넘는다")
    if not need.face_is_human and t["human_only"]:
        bad.append("사람 얼굴에만 작동한다 — 동물·캐릭터는 리타게팅을 경유해야 한다")
    if need.needs_gesture and t["gesture"] in ("불가", "제한적"):
        bad.append(f"제스처 {t['gesture']}")
    if need.art_style_is_product and t["art_style"] not in ("완전",):
        bad.append("그림체가 유지되지 않는다")
    if need.needs_head_turn and t["head_turn"] is False:
        bad.append("고개를 돌릴 수 없다")
    return bad


# §4 — 본문이 답을 준 시나리오들. 코드와 산문을 묶는 자리다.
SCENARIOS = [
    ("우리 회사 대표님 얼굴로 사내 공지 영상",
     Need(latency_budget=600), R3),
    ("학습 사이트에 설명해 주는 캐릭터",
     Need(latency_budget=2.0, concurrent_users=200), R2),
    ("세상을 떠난 반려동물이 말하는 영상",
     Need(latency_budget=600, face_is_human=False), R3R),
    ("버추얼 스트리머",
     Need(latency_budget=2.0, art_style_is_product=True, needs_head_turn=True), R15),
    ("상담 키오스크",
     Need(latency_budget=2.0, concurrent_users=1), R2),
    ("게임 안의 NPC 여럿",
     Need(latency_budget=2.0, art_style_is_product=True), R1),
    ("강연하듯 손짓하며 말하는 홍보 영상",
     Need(latency_budget=1800, needs_gesture=True), R4),
    ("내 사진으로 아바타 만들어주는 앱",
     Need(latency_budget=600), R3),
]


def _demo():
    print()
    for label, need, expected in SCENARIOS:
        got = choose(need)
        mark = "  " if got["rung"] == expected else "✗ "
        g = gpu_count(got["rung"], need.concurrent_users)
        print(f"  {mark}{label}")
        print(f"      → {got['rung']}"
              + (f"   GPU {g}장" if g else "   GPU 0장 (브라우저 렌더)"))
        for w in got["why"]:
            print(f"        · {w}")
    print()
    print("  같은 질문에 같은 답이 나오는지가 요점입니다 —")
    print("  본문 §4 의 답과 이 코드가 어긋나면 test_ladder.py 가 먼저 압니다.")
    print()


if __name__ == "__main__":
    _demo()
