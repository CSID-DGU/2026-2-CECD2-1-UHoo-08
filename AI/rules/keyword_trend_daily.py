"""키워드 트렌드 지수 → 제품 일일 점수 (trend-kw-v1).

1. 키워드 언급: 게시물마다 rules/keyword_extract 로 키워드를 찾는다.
2. 키워드 순위: rules/trend_score.compute_trend 를 그대로 쓴다. 집계 단위만 제품이
   아니라 키워드다(영향력 × 반응 × 최신성 × 광고, 28일, 같은 작성자 감쇠, 작성자 2명 이상).
3. 제품 점수: rules/keyword_trend 가 키워드 순위를 제품 점수로 바꾼다.
4. product_trend_daily 에 넣을 행을 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from rules.keyword_extract import KeywordDictionary, extract_keywords
from rules.keyword_trend import KeywordRank, ProductScore, product_scores
from rules.trend_score import Mention, ProductTrend, compute_trend, top_trends

FORMULA_VERSION = "trend-kw-v1"


@dataclass
class Post:
    post_id: str
    author: str
    caption: str | None
    posted_at: date
    followers: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    is_ad: bool | None = None
    age_group: str | None = None
    source: str = "real"


def _mention(p: Post, keyword_id: str) -> Mention:
    return Mention(post_id=p.post_id, product_id=keyword_id, author=p.author, posted_at=p.posted_at,
                   followers=p.followers, like_count=p.like_count, comment_count=p.comment_count,
                   is_ad=p.is_ad, age_group=p.age_group, source=p.source)


def keyword_mentions(posts: list[Post], d: KeywordDictionary) -> list[Mention]:
    """게시물 → 키워드 언급 기록. Mention.product_id 자리에 keyword_id 가 들어간다."""
    return [_mention(p, h.keyword_id) for p in posts for h in extract_keywords(p.caption, d)]


def keyword_trends(posts: list[Post], d: KeywordDictionary, as_of, allow_synthetic: bool = False) -> list[ProductTrend]:
    """키워드별 트렌드. 평소 반응은 키워드가 없는 글까지 포함한 전체 게시물로 잰다."""
    baseline = [_mention(p, "") for p in posts]
    return compute_trend(keyword_mentions(posts, d), as_of, allow_synthetic=allow_synthetic, baseline_mentions=baseline)


def keyword_ranks(trends: list[ProductTrend]) -> list[KeywordRank]:
    """순위에 오른 키워드(작성자 2명 이상, TOP_N)."""
    return [KeywordRank(t.product_id, t.rank, t.mention_count, t.ad_mention_count, t.engagement)
            for t in top_trends(trends)]


def daily_scores(posts: list[Post], products: list[dict], d: KeywordDictionary, as_of) -> tuple[list[ProductTrend], list[ProductScore]]:
    trends = keyword_trends(posts, d, as_of)
    return trends, product_scores(keyword_ranks(trends), products, d)


def daily_rows(scores: list[ProductScore], as_of: date) -> list[dict]:
    """product_trend_daily 에 넣을 행."""
    return [{
        "product_id": s.product_id, "date": as_of.isoformat(),
        "mention_count": s.mention_count, "ad_mention_count": s.ad_mention_count,
        "engagement": s.engagement, "trend_score": float(s.score), "formula_version": FORMULA_VERSION,
    } for s in scores]
