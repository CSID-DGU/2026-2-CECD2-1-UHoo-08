"""키워드 트렌드 지수 → 제품 일일 점수 (trend-kw-v1)."""
from datetime import date, timedelta

from rules.keyword_extract import load_keywords
from rules.keyword_trend import TOP_N
from rules.keyword_trend_daily import FORMULA_VERSION, Post, daily_rows, daily_scores, keyword_ranks, keyword_trends

D = load_keywords()
AS_OF = date(2026, 11, 26)


def post(pid, author, caption, days_ago=1, likes=100):
    return Post(post_id=pid, author=author, caption=caption, posted_at=AS_OF - timedelta(days=days_ago),
                followers=10_000, like_count=likes, comment_count=0, is_ad=False)


def prod(pid, name):
    return {"product_id": pid, "name": name, "feature_json": {}}


POSTS = [
    post("1", "a", "PDRN 앰플 최고"), post("2", "b", "pdrn 세럼 추천"), post("3", "c", "피디알엔 크림"),
    post("4", "a", "보습 크림"), post("5", "b", "수분 가득"),
    post("6", "a", "판테놀 토너"),            # 작성자 1명 → 순위 밖
    post("7", "d", "오늘 점심 맛집"),          # 키워드 없음, 평소 반응 계산에만 쓰인다
]


def test_keyword_rank_needs_two_authors():
    trends = {t.product_id: t for t in keyword_trends(POSTS, D, AS_OF)}
    assert trends["pdrn"].rank == 1 and trends["pdrn"].author_count == 3
    assert trends["hydration"].rank == 2
    assert trends["panthenol"].rank is None and not trends["panthenol"].qualified


def test_keyword_ranks_carry_counts():
    ranks = keyword_ranks(keyword_trends(POSTS, D, AS_OF))
    assert [(r.keyword_id, r.rank, r.mention_count) for r in ranks] == [("pdrn", 1, 3), ("hydration", 2, 2)]


def test_daily_rows_shape():
    _, scores = daily_scores(POSTS, [prod("p", "PDRN 앰플")], D, AS_OF)
    [row] = daily_rows(scores, AS_OF)
    assert row == {"product_id": "p", "date": "2026-11-26", "mention_count": 3, "ad_mention_count": 0,
                   "engagement": 300, "trend_score": float(TOP_N), "formula_version": FORMULA_VERSION}


def test_old_posts_fall_out_of_window():
    old = [post("1", "a", "PDRN", days_ago=40), post("2", "b", "PDRN", days_ago=40)]
    assert daily_scores(old, [prod("p", "PDRN 앰플")], D, AS_OF)[1] == []
