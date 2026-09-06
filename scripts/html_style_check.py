# -*- coding: utf-8 -*-
"""
조판 HTML 스타일 검수 — PDF 글꼴 플래그로는 못 잡는 것을 브라우저가 계산한 스타일로 잡는다

  ① 기울임 누출   <em> 이 닫히지 않으면 브라우저가 다음 문단으로 강조를 이어 붙여 책 뒤쪽이 전부 기울어진다.
                 글꼴에 이탤릭 면이 없으면 합성 기울임이라 PDF 검수기(type_qa)는 세지 못한다(2026-09-05 Ch20 사고).
  ② 굵게 누출     같은 원리로 <strong>.
  ③ 캡션 번호     '그림 0.x' 처럼 장 번호 없는 앞부분에 0 이 붙은 것.

    python scripts/html_style_check.py            build/book.html 검수, 문제 있으면 종료코드 1
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "build", "book.html")


def main():
    if not os.path.exists(HTML):
        print("  book.html 이 없다 — scripts/build_book.py --html 을 먼저 돌려라")
        return 2
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto("file:///" + HTML.replace("\\", "/"), wait_until="load", timeout=120000)
        r = pg.evaluate("""() => {
            const els = [...document.querySelectorAll('p, li, h1, h2, h3, h4, td, th, figcaption, blockquote')];
            let it = 0, bold = 0; const ex_it = [], ex_b = [];
            for (const e of els) {
                const st = getComputedStyle(e);
                if (st.fontStyle !== 'normal') { it++; if (ex_it.length < 3) ex_it.push(e.textContent.trim().slice(0, 40)); }
                const tag = e.tagName.toLowerCase();
                if ((tag === 'p' || tag === 'li' || tag === 'td') && parseInt(st.fontWeight) >= 600 && e.querySelector('strong') === null && e.textContent.trim().length > 60) {
                    bold++; if (ex_b.length < 3) ex_b.push(e.textContent.trim().slice(0, 40));
                }
            }
            return {n: els.length, it, ex_it, bold, ex_b};
        }""")
        b.close()
    html = open(HTML, encoding="utf-8").read()
    zero = re.findall(r"(?:그림|표) 0\.\d+", html)
    body = html.split("<body>", 1)[1] if "<body>" in html else html
    parts = re.split(r"(<pre>.*?</pre>|<code>.*?</code>|<style>.*?</style>)", body, flags=re.S)
    text = "".join(re.sub(r"<[^>]+>", "", parts[i]) for i in range(0, len(parts), 2))
    stars = len(re.findall(r"\*\*", text)) + len(re.findall(r"(?<!\*)\*(?!\*)", text))
    print(f"\n  HTML 스타일 검수 — 블록 {r['n']}개")
    print(f"  ① 기울임 누출  {r['it']:>4}개  {r['ex_it']}")
    print(f"  ② 굵게 누출    {r['bold']:>4}개  {r['ex_b']}")
    print(f"  ③ 0.x 캡션     {len(zero):>4}개  {zero[:4]}")
    print(f"  ④ 본문 '*' 잔존 {stars:>4}개  (마크다운 강조가 변환되지 않은 것)\n")
    return 1 if (r["it"] or r["bold"] or zero or stars) else 0


if __name__ == "__main__":
    sys.exit(main())
