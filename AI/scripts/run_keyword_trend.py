"""
키워드 트렌드를 계산해 보여 주고, --write 를 주면 product_trend_daily 에 넣는다.

서버에서는 인스타 수집 스케줄이 수집 뒤에 돌리므로, 이 스크립트는 첫 적재나
결과를 눈으로 확인할 때 쓴다. 기본은 계산만 하고 DB 에 쓰지 않는다.

사용법 (AI 디렉터리에서):
    python -m scripts.run_keyword_trend                     # 오늘(KST) 기준, 출력만
    python -m scripts.run_keyword_trend --date 2026-11-26   # 그날 기준
    python -m scripts.run_keyword_trend --write             # 저장
"""
import argparse
import json
import logging
from datetime import date, datetime

from db.supabase_client import get_supabase
from services.influencer_collector import KST
from services.keyword_trend_job import compute, write


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, help="집계 기준일 (기본: 오늘 KST)")
    parser.add_argument("--write", action="store_true", help="product_trend_daily 에 저장한다")
    parser.add_argument("--top", type=int, default=20, help="보여 줄 제품 수")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    sb = get_supabase()
    r = compute(sb, args.date or datetime.now(KST).date())
    d = r["dictionary"]
    print(f"기준일 {r['as_of']} · 게시물 {len(r['posts'])}개 · 키워드 언급 기록 {sum(t.mention_count for t in r['trends'])}건")
    print("\n[키워드 순위]  순위 / 키워드 / 게시물 / 작성자 / raw_score")
    for t in sorted(r["trends"], key=lambda t: (t.rank is None, t.rank or 0, -t.raw_score)):
        kw = d.by_id[t.product_id]
        mark = f"{t.rank:>3}" if t.rank else "  -"
        print(f"  {mark}  {kw.label:<12} {t.mention_count:>4} {t.author_count:>4}  {t.raw_score:.3f}"
              + ("" if t.qualified else "  (작성자 1명)"))

    names = {p["product_id"]: f"{p.get('brand')} {p.get('name')}"
             for p in sb.table("products").select("product_id,brand,name").execute().data or []}
    print(f"\n[제품 점수] 점수가 있는 제품 {len(r['scores'])}개, 상위 {args.top}개")
    for k, s in enumerate(r["scores"][:args.top], 1):
        kws = ", ".join(f"{d.by_id[x['keyword_id']].label}({x['points']})" for x in s.keywords)
        print(f"  {k:>3}. {s.score:>3}점  {names.get(s.product_id, s.product_id)}  ← {kws}")

    if args.write:
        print("\n" + json.dumps(write(sb, r), ensure_ascii=False))
    else:
        print("\n(저장하지 않음. 저장하려면 --write)")


if __name__ == "__main__":
    main()
