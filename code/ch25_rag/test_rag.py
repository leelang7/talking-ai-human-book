# -*- coding: utf-8 -*-
"""
Ch25 — 청킹·검색 회귀 테스트

이 장의 주장을 코드로 못 박는다.
  · 제목 맥락이 각 조각에 들어간다 (비용 대비 효과 1위)
  · 표는 쪼개지지 않는다
  · 고유명사·코드는 키워드 검색이 잡는다 (의미 검색만으로는 약하다)
  · 필요·충분조건 양방향 (Ch27 §5+ · Ch25 §7)

실행:  python test_rag.py     (종료 코드 0 = 통과)
"""
import sys

from chunker import SAMPLE, chunk, search, _keyword, _semantic

FAILS = []


def ok(cond, name, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"         {detail}")
        FAILS.append(name)


def run():
    cs = chunk(SAMPLE)

    # ── 제목 맥락 — 이 장의 핵심 ──
    ok(all(c["text"].startswith("[") for c in cs),
       "모든 조각이 제목 맥락으로 시작한다")
    knee = next(c for c in cs if "통증" in c["body"])
    ok("2.2 무릎이 아플 때" in knee["text"] and "2. 스쿼트" in knee["text"],
       "하위 조각에 상위 제목 경로가 전부 들어간다", knee["text"][:40])
    ok(knee["body"] not in knee["text"].split("\n")[0],
       "제목은 본문과 분리된 줄에 있다")

    # ── 표 ──
    tb = [c for c in cs if c["kind"] == "table"]
    ok(len(tb) == 1, "표는 하나의 조각으로 남는다", f"{len(tb)}개")
    ok(all(x in tb[0]["body"] for x in ("B-100", "P-200", "M-300")),
       "표의 모든 행이 같은 조각에 있다(행·열이 흩어지지 않음)")

    # ── 제목 경로가 계층을 지키는가 ──
    basic = next(c for c in cs if "어깨너비" in c["body"])
    ok(basic["path"] == ["홈트 가이드", "2. 스쿼트", "2.1 기본 자세"],
       "제목 경로가 계층 그대로다", f"{basic['path']}")

    # ── 하이브리드: 코드·숫자는 키워드가 잡는다 ──
    q = "P-200 요금"
    top = search(cs, q, k=1)[0][1]
    ok(top["kind"] == "table", "제품 코드 질의가 표 조각을 집는다", f"{top['path']}")
    ok(_keyword(q, tb[0]["text"]) > _semantic(q, tb[0]["text"]),
       "코드 질의는 키워드 점수가 의미 점수보다 높다",
       f"kw {_keyword(q, tb[0]['text']):.3f} vs sem {_semantic(q, tb[0]['text']):.3f}")

    # 반대로 서술형 질의는 의미 쪽이 일한다
    q2 = "무릎 아프면 어떻게 해요"
    ok(search(cs, q2, k=1)[0][1]["body"] == knee["body"],
       "서술형 질의는 해당 절을 집는다")

    # ── 필요·충분조건 양방향 (Ch25 §7) ──
    # 있는 것은 찾아야 하고, 없는 것은 점수가 낮아야 한다.
    hit = search(cs, "하프 스쿼트", k=1)[0]
    ok(hit[0] > 0.05, "문서에 있는 내용은 유의미한 점수로 찾힌다", f"{hit[0]}")
    miss = search(cs, "카페 원두 로스팅 온도", k=1)[0]
    ok(miss[0] < 0.05, "문서에 없는 질의는 점수가 낮다(모른다고 답할 근거)",
       f"{miss[0]}")
    ok(hit[0] > miss[0] * 3, "있는 것과 없는 것의 점수 차가 뚜렷하다",
       f"{hit[0]} vs {miss[0]}")

    # ── 긴 문서 자르기 ──
    long_md = "# 문서\n\n## 절\n\n" + ("가나다라마바사아자차 " * 40 + "\n\n") * 6
    lc = chunk(long_md, max_chars=400, min_chars=200, overlap=0.15)
    ok(len(lc) > 1, "긴 문서는 여러 조각으로 나뉜다", f"{len(lc)}개")
    ok(all(len(c["body"]) <= 400 * 1.35 for c in lc),
       "조각이 상한을 크게 넘지 않는다",
       f"최대 {max(len(c['body']) for c in lc)}자")
    ok(all(c["part"][1] == len(lc) for c in lc), "조각마다 전체 개수를 안다")
    ok(all("[문서 > 절]" in c["text"] for c in lc),
       "쪼개진 조각 전부에 제목이 붙는다")

    # 겹침 — 경계에 걸친 정보를 놓치지 않기 위한 것
    joined = "".join(c["body"] for c in lc)
    ok(len(joined) > len(long_md) * 0.8, "겹침 덕에 총량이 원문보다 줄지 않는다")

    # 빈 문서
    ok(chunk("") == [] or all(c["body"] for c in chunk("")),
       "빈 문서에서 빈 조각을 만들지 않는다")


if __name__ == "__main__":
    print("청킹·검색 회귀 테스트 (Ch25)")
    run()
    print(f"\n  {'전부 통과' if not FAILS else str(len(FAILS)) + '건 실패: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)
