# -*- coding: utf-8 -*-
"""
Ch08 — 지연을 숨기는 네 장치

브라우저에서 눈으로 봐야 하는 부분(HTML)은 `player.html` 에 있다.
이 파일은 **눈이 아니라 숫자로 확인할 수 있는 부분** 만 떼어낸 것이다.

    ① 더블 버퍼      화면이 비는 프레임을 0 으로 만든다        (§5)
    ② 크로스페이드    전환을 100~200ms 디졸브로 감춘다          (§4)
    ③ 상태           "로딩" 이라는 상태를 아예 만들지 않는다     (§1)
    ④ 폴백           어떤 경로로 끝나도 소리가 난다             (§7)

"깜빡임이 없어졌다" 는 눈으로 하는 주장이다. 여기서는 **빈 프레임 수를 센다.**

    python hide.py       단일 버퍼와 더블 버퍼를 나란히 시뮬레이션
"""
import io
import wave

CROSSFADE_MS = 150          # §4 — 사람이 전환으로 인식하지 못하는 구간
IMPERCEPTIBLE = (100, 200)
TIMEOUT_S = 5.0             # §7 — 30초 기다리는 것보다 5초에 포기하는 편이 낫다
IDLE_SECONDS = 4.0          # §2 — 무음 4초를 한 번 렌더해서 아이들 소스로 쓴다


# ── ① 더블 버퍼 ──────────────────────────────────────────────────────
class SingleBuffer:
    """영상 요소 하나로 소스만 바꾸는 방식. 로드되는 동안 화면이 빈다."""

    def __init__(self, initial=None):
        self.src = initial
        self._loading = 0

    def prime(self, src):
        self.src, self._loading = src, 0
        return self

    def stage(self, src, load_frames):
        self.src, self._loading = src, load_frames

    def tick(self):
        """한 프레임 진행하고 지금 화면에 보이는 것을 반환한다."""
        if self._loading > 0:
            self._loading -= 1
            return None                      # ← 검은 프레임. 이것이 깜빡임이다.
        return self.src


class DoubleBuffer:
    """요소 둘을 겹쳐 두고 번갈아 쓴다. 뒤에서 로드하고 준비되면 앞으로.

    **앞 요소는 뒤가 준비될 때까지 마지막 프레임을 계속 보여준다.**
    그래서 화면이 비는 순간이 없다 (§5).
    """

    def __init__(self, initial=None):
        self.slots = [initial, None]
        self._loading = [0, 0]
        self.front = 0
        self.swaps = 0

    def prime(self, src):
        """앞 슬롯을 직접 채운다 — 서버가 뜰 때 아이들 루프를 올리는 것.

        **더블 버퍼는 보여줄 이전 프레임이 있을 때만 깜빡임을 없앤다.**
        아무것도 없는 상태에서 첫 영상을 올리면 요소가 둘이어도 똑같이 빈다.
        §2 의 아이들 루프가 §5 의 전제조건인 이유다.
        """
        self.slots[self.front] = src
        self._loading[self.front] = 0
        return self

    @property
    def visible(self):
        return self.slots[self.front]

    @property
    def back(self):
        return 1 - self.front

    def stage(self, src, load_frames):
        """뒤 슬롯에 로드를 시작한다. 앞은 건드리지 않는다."""
        b = self.back
        self.slots[b], self._loading[b] = src, load_frames
        return b

    def ready(self, slot=None):
        return self._loading[self.back if slot is None else slot] <= 0

    def promote(self):
        """준비된 경우에만 앞뒤를 바꾼다. 안 됐으면 **바꾸지 않는다.**

        이 한 줄이 더블 버퍼의 전부다. 준비 안 된 것을 앞으로 올리면
        요소가 둘이어도 똑같이 깜빡인다.
        """
        if not self.ready():
            return False
        self.front = self.back
        self.swaps += 1
        return True

    def tick(self):
        for i in (0, 1):
            if self._loading[i] > 0:
                self._loading[i] -= 1
        self.promote()
        return self.visible


def simulate(buf, sources, load_frames=3, hold_frames=6, initial="idle_loop.mp4"):
    """소스를 차례로 교체하며 프레임을 돌린다. 화면이 빈 프레임 수를 센다.

    `initial` 은 서버가 뜰 때 이미 돌고 있는 아이들 루프다. 두 방식을
    공평하게 비교하려면 양쪽 다 같은 상태에서 출발해야 한다.
    """
    if initial is not None:
        buf.prime(initial)
    blanks, seen = 0, []
    for src in sources:
        buf.stage(src, load_frames)
        for _ in range(load_frames + hold_frames):
            v = buf.tick()
            seen.append(v)
            if v is None:
                blanks += 1
    return {"blank_frames": blanks, "total": len(seen), "last": seen[-1]}


# ── ② 크로스페이드 ───────────────────────────────────────────────────
def crossfade(elapsed_ms: float, duration_ms: float = CROSSFADE_MS):
    """(나가는 것, 들어오는 것)의 불투명도. 합은 항상 1 이다.

    합이 1 이라는 것이 중요하다 — 둘 다 반투명한 순간에 배경이 비쳐 보이면
    그것도 깜빡임이다. 하드 컷을 원하면 duration 0 을 넘긴다.
    """
    if duration_ms <= 0:
        return (0.0, 1.0)
    p = min(1.0, max(0.0, elapsed_ms / duration_ms))
    return (1.0 - p, p)


def imperceptible(duration_ms: float) -> bool:
    """§4 가 권하는 100~200ms 안인가."""
    return IMPERCEPTIBLE[0] <= duration_ms <= IMPERCEPTIBLE[1]


def jump(a: float, b: float, duration_ms: float, fps: float = 30.0) -> float:
    """전환 구간에서 **한 프레임 사이에 생기는 최대 변화량.**

    하드 컷은 1프레임에 0 → 1 로 튄다. 150ms 디졸브는 같은 변화를
    4~5 프레임에 나눠 담으므로 프레임당 변화가 1/5 로 준다.
    """
    if duration_ms <= 0:
        return abs(b - a)
    frames = max(1.0, duration_ms / 1000.0 * fps)
    return abs(b - a) / frames


# ── ③ 상태 ──────────────────────────────────────────────────────────
# **로딩이라는 상태가 없다.** 이것이 §1 의 주장을 코드로 옮긴 모습이다.
STATES = ("idle", "listening", "thinking", "speaking")
ALLOWED = {
    "idle": ("listening",),
    "listening": ("thinking", "idle"),
    "thinking": ("speaking", "idle"),       # idle 로 빠지는 것은 폴백 실패 경로
    "speaking": ("idle", "listening"),      # listening = 사용자가 끼어든 것(barge-in)
}


def visual(state: str) -> str:
    """그 상태에서 화면에 무엇이 도는가. **스피너는 어느 상태에도 없다.**"""
    if state not in STATES:
        raise ValueError(f"모르는 상태: {state}")
    return "speaking_clip" if state == "speaking" else "idle_loop"


def can(src: str, dst: str) -> bool:
    return dst in ALLOWED.get(src, ())


# ── ④ 폴백 ──────────────────────────────────────────────────────────
FALLBACK_LINE = "잠깐만요, 다시 말씀해 주시겠어요?"


def resolve_turn(llm_seconds, tts_ok=True, offline=None, timeout=TIMEOUT_S):
    """한 턴의 결과. **어떤 경로로 끝나도 audio 가 None 이 아니다** (§7).

    화면에 붉은 토스트를 띄우지 않는다. 로그에만 남기고 소리는 낸다.
    """
    if llm_seconds is not None and llm_seconds <= timeout and tts_ok:
        return {"path": "normal", "audio": "tts", "text": None, "log": None}
    reason = "timeout" if (llm_seconds is None or llm_seconds > timeout) else "tts_failed"
    if offline:
        return {"path": "offline", "audio": "prerendered",
                "text": offline, "log": reason}
    return {"path": "fallback", "audio": "prerendered",
            "text": FALLBACK_LINE, "log": reason}


# ── 아이들 소스용 무음 wav — ffmpeg 없이 만든다 ────────────────────────
def silent_wav(seconds: float = IDLE_SECONDS, rate: int = 16000) -> bytes:
    """§3 — 소스 영상을 그대로 루프하면 대기 중에 혼자 떠든다.

    무음을 한 번 통과시키면 모델이 입을 다문 채 렌더하고, 눈 깜빡임과
    머리의 미세 움직임은 소스에서 그대로 남는다.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


def _demo():
    srcs = ["reply_1.mp4", "reply_2.mp4", "reply_3.mp4"]
    a = simulate(SingleBuffer(), srcs)
    b = simulate(DoubleBuffer(), srcs)
    cold = simulate(DoubleBuffer(), srcs, initial=None)
    print()
    print("  ── 영상 교체 3회 · 로드에 3프레임 ──\n")
    print(f"  단일 버퍼   화면이 빈 프레임 {a['blank_frames']:>2} / {a['total']}")
    print(f"  더블 버퍼   화면이 빈 프레임 {b['blank_frames']:>2} / {b['total']}")
    print(f"  더블·콜드   화면이 빈 프레임 {cold['blank_frames']:>2} / {cold['total']}"
          "   ← 아이들 루프 없이 시작하면 첫 로드는 여전히 빈다")
    print()
    print(f"  하드 컷     프레임당 최대 변화 {jump(0, 1, 0):.2f}")
    print(f"  {CROSSFADE_MS}ms 디졸브 프레임당 최대 변화 {jump(0, 1, CROSSFADE_MS):.2f}")
    print()
    print("  상태별 화면 —", ", ".join(f"{s}={visual(s)}" for s in STATES))
    print("  '로딩' 은 상태 목록에 없다. 그것이 §1 의 주장이다.")
    print()
    for lat in (1.2, 9.9):
        r = resolve_turn(lat)
        print(f"  LLM {lat:>4}초 → {r['path']:9} audio={r['audio']}")
    print()


if __name__ == "__main__":
    _demo()
