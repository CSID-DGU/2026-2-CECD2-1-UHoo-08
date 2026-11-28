"""제품별 트렌드 지수 (Trend v1). 홈 '요즘 뜨는 제품'의 순위 근거다.

인플루언서 게시물이 제품을 언급한 기록(mention)을 받아, 최근 28일 동안의 화제성을
제품별 점수로 낸다. LLM 을 부르지 않는다. 같은 입력이면 같은 결과다.

게시물 점수   S = 영향력 I × 반응 E × 최신성 R × 광고 A        (각 0~1)
  I  log(1+팔로워) / log(1+100만). 대형 계정 하나가 순위를 독점하지 않게 한다.
  E  (좋아요 + 3×댓글) / (그 계정의 평소 반응 × 3), 1 에서 자른다. 계정마다 팔로워가
     880 명부터 58만 명까지라 절대 참여율로는 비교가 안 된다. "평소보다 얼마나 반응이
     컸나"를 본다. 평소 반응은 그 계정의 유효 게시물이 5개 이상이면 그 중앙값, 아니면
     팔로워 규모가 비슷한 계정들의 중앙값이다. 좋아요를 숨긴 글 · 기준이 0 인 경우는
     1/3(평소 수준)로 둔다. 0 으로 두면 좋아요를 숨긴 계정의 언급이 사라진다.
  R  2^(-경과일/7). 반감기 7일.
  A  광고 아님 1.0 · 광고 0.3 · 판별 전 0.6.

제품 점수
  같은 작성자의 언급은 점수 큰 순으로 1, 0.5, 0.25 … 를 곱해 더한다. 본인 브랜드
  계정이 같은 제품을 여러 번 올려 순위를 만드는 것을 막는다. 합계가 raw_score 다.
  raw_score 는 날짜끼리 비교할 수 있는 원본이고, 0~100 의 score 는 그날 1위를 100 으로
  맞춘 표시용이다. 상승세(v2)는 raw_score 로 계산해야 한다.

TOP 10 자격
  서로 다른 작성자 2명 이상이 언급한 제품만 순위에 올린다. 한 명뿐인 제품은
  low_confidence 로 표시만 하고 순위에서 뺀다.

합성 데이터
  source == "synthetic" 인 언급은 allow_synthetic=True 일 때만 받는다. 실험 데이터
  (data/synthetic/trend/)가 운영 트렌드에 섞이지 않게 하는 마지막 안전장치다.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from statistics import median

FORMULA_VERSION = "trend-v1"

WINDOW_DAYS = 28
HALF_LIFE_DAYS = 7.0
FOLLOWER_CAP = 1_000_000
COMMENT_WEIGHT = 3
ENGAGEMENT_SATURATION = 3.0   # 평소의 몇 배면 반응 만점인가
ENGAGEMENT_DEFAULT = 1 / ENGAGEMENT_SATURATION  # 평소 수준. 결측 · 기준 0 일 때
MIN_BASELINE_POSTS = 5
FOLLOWER_BUCKETS = (10_000, 100_000)  # 이 경계로 나눈 규모끼리 평소 반응을 빌려 쓴다
INFLUENCE_DEFAULT = 0.5       # 팔로워 수를 모를 때
AD_WEIGHT = {True: 0.3, False: 1.0, None: 0.6}
AUTHOR_DECAY = 0.5
MIN_AUTHORS = 2
TOP_N = 10


@dataclass
class Mention:
    """게시물 하나가 제품 하나를 언급한 기록. 하울 글은 제품마다 한 줄이다."""
    post_id: str
    product_id: str
    author: str
    posted_at: date
    followers: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    is_ad: bool | None = None
    age_group: str | None = None
    source: str = "real"


@dataclass
class PostScore:
    post_id: str
    author: str
    influence: float
    engagement: float
    recency: float
    ad: float
    score: float
    weight: float = 1.0   # 같은 작성자 감쇠 계수
    engagement_note: str = ""


@dataclass
class ProductTrend:
    product_id: str
    raw_score: float
    score: float
    mention_count: int
    author_count: int
    ad_mention_count: int
    unlabeled_count: int
    engagement: int
    qualified: bool
    rank: int | None
    breakdown: dict = field(default_factory=dict)


def _as_date(d) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def influence(followers: int | None) -> float:
    if followers is None:
        return INFLUENCE_DEFAULT
    return min(1.0, math.log1p(max(followers, 0)) / math.log1p(FOLLOWER_CAP))


def recency(age_days: float) -> float:
    return 2 ** (-max(age_days, 0.0) / HALF_LIFE_DAYS)


def raw_engagement(m: Mention) -> float | None:
    """좋아요를 숨긴 글은 None. 댓글만으로 평소와 비교하면 과소평가된다."""
    if m.like_count is None:
        return None
    return m.like_count + COMMENT_WEIGHT * (m.comment_count or 0)


def _bucket(followers: int | None) -> int:
    if followers is None:
        return -1
    return sum(followers >= b for b in FOLLOWER_BUCKETS)


def engagement_baselines(mentions: list[Mention]) -> tuple[dict[str, float], dict[int, float]]:
    """작성자별 평소 반응, 팔로워 규모별 평소 반응. 같은 게시물은 한 번만 센다."""
    by_author: dict[str, list[float]] = defaultdict(list)
    bucket_of: dict[str, int] = {}
    seen = set()
    for m in mentions:
        if m.post_id in seen:
            continue
        seen.add(m.post_id)
        bucket_of[m.author] = _bucket(m.followers)
        r = raw_engagement(m)
        if r is not None:
            by_author[m.author].append(r)
    author_base = {a: median(v) for a, v in by_author.items() if len(v) >= MIN_BASELINE_POSTS}
    by_bucket: dict[int, list[float]] = defaultdict(list)
    for a, v in by_author.items():
        by_bucket[bucket_of[a]].append(median(v))
    bucket_base = {b: median(v) for b, v in by_bucket.items() if v}
    return author_base, bucket_base


def engagement(m: Mention, author_base: dict[str, float], bucket_base: dict[int, float]) -> tuple[float, str]:
    r = raw_engagement(m)
    if r is None:
        return ENGAGEMENT_DEFAULT, "좋아요 결측"
    base, note = author_base.get(m.author), "계정 중앙값"
    if base is None:
        base, note = bucket_base.get(_bucket(m.followers)), "규모 중앙값"
    if not base:
        return ENGAGEMENT_DEFAULT, "기준 없음"
    return min(1.0, r / (base * ENGAGEMENT_SATURATION)), note


def compute_trend(mentions: list[Mention], as_of, allow_synthetic: bool = False,
                  baseline_mentions: list[Mention] | None = None) -> list[ProductTrend]:
    """언급 기록 → 제품별 트렌드 (raw_score 내림차순).

    as_of: 집계 기준일. 이 날 기준 WINDOW_DAYS 안의 게시물만 본다.
    baseline_mentions: 평소 반응 계산에 쓸 게시물. 주지 않으면 mentions 로 계산한다.
      운영에서는 작성자의 최근 게시물 전체(제품 언급이 없는 글 포함)를 넘기는 게 맞다.
    """
    if not allow_synthetic and any(m.source == "synthetic" for m in [*mentions, *(baseline_mentions or [])]):
        raise ValueError("합성 언급(source=synthetic)이 섞여 있다. 운영 트렌드에는 쓰지 않는다")

    as_of = _as_date(as_of)
    live = [m for m in mentions if 0 <= (as_of - _as_date(m.posted_at)).days < WINDOW_DAYS]
    # 집계일 이후 게시물이 평소 반응을 바꾸면 과거 날짜를 다시 계산할 때 순위가 달라진다
    base = [m for m in (baseline_mentions or mentions) if _as_date(m.posted_at) <= as_of]
    author_base, bucket_base = engagement_baselines(base)

    by_product: dict[str, list[tuple[Mention, PostScore]]] = defaultdict(list)
    seen = set()
    for m in live:
        key = (m.post_id, m.product_id)
        if key in seen:  # 같은 게시물이 같은 제품을 두 번 언급해도 한 번
            continue
        seen.add(key)
        e, note = engagement(m, author_base, bucket_base)
        i, r, a = influence(m.followers), recency((as_of - _as_date(m.posted_at)).days), AD_WEIGHT[m.is_ad]
        by_product[m.product_id].append((m, PostScore(m.post_id, m.author, i, e, r, a, i * e * r * a, engagement_note=note)))

    out = []
    for pid, items in by_product.items():
        per_author: dict[str, list[PostScore]] = defaultdict(list)
        for _, ps in items:
            per_author[ps.author].append(ps)
        raw = 0.0
        for posts in per_author.values():
            posts.sort(key=lambda p: -p.score)
            for k, ps in enumerate(posts):
                ps.weight = AUTHOR_DECAY ** k
                raw += ps.score * ps.weight
        ms = [m for m, _ in items]
        ages = defaultdict(int)
        for m in ms:
            ages[m.age_group or "unknown"] += 1
        top = max(items, key=lambda x: x[1].score * x[1].weight)[1]
        out.append(ProductTrend(
            product_id=pid, raw_score=raw, score=0.0,
            mention_count=len(ms), author_count=len(per_author),
            ad_mention_count=sum(m.is_ad is True for m in ms),
            unlabeled_count=sum(m.is_ad is None for m in ms),
            engagement=sum((m.like_count or 0) + (m.comment_count or 0) for m in ms),
            qualified=len(per_author) >= MIN_AUTHORS, rank=None,
            breakdown={
                "formula_version": FORMULA_VERSION,
                "ad_ratio": round(sum(m.is_ad is True for m in ms) / len(ms), 3),
                "age_groups": {k: round(v / len(ms), 3) for k, v in sorted(ages.items())},
                "top_post_id": top.post_id,
                "low_confidence": len(per_author) < MIN_AUTHORS,
                "posts": [vars(ps) for _, ps in items],
            },
        ))

    best = max((t.raw_score for t in out), default=0.0)
    for t in out:
        t.score = round(100 * math.log1p(t.raw_score) / math.log1p(best), 2) if best > 0 else 0.0
    out.sort(key=lambda t: (-t.raw_score, -t.author_count, t.product_id))
    for k, t in enumerate([t for t in out if t.qualified][:TOP_N], 1):
        t.rank = k
    return out


def top_trends(trends: list[ProductTrend]) -> list[ProductTrend]:
    """홈에 올릴 순위. 자격(작성자 2명 이상)을 갖춘 상위 TOP_N 개."""
    return sorted((t for t in trends if t.rank), key=lambda t: t.rank)
