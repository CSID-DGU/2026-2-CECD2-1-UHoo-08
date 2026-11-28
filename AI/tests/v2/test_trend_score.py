"""Trend v1 — 게시물 점수 · 제품 집계 · TOP 10 자격."""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from rules.trend_score import (
    AD_WEIGHT,
    ENGAGEMENT_DEFAULT,
    MIN_AUTHORS,
    TOP_N,
    WINDOW_DAYS,
    Mention,
    compute_trend,
    engagement,
    engagement_baselines,
    influence,
    recency,
    top_trends,
)

AS_OF = date(2026, 11, 3)
POSTS = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "trend" / "posts_v1.jsonl"


def m(post, product, author, days_ago=0, *, followers=10_000, likes=100, comments=0, is_ad=False, source="real"):
    return Mention(post_id=post, product_id=product, author=author, posted_at=AS_OF - timedelta(days=days_ago),
                   followers=followers, like_count=likes, comment_count=comments, is_ad=is_ad, source=source)


def by_id(trends):
    return {t.product_id: t for t in trends}


# ── 독립 작성자 수 ─────────────────────────────────────────────

def test_독립_작성자_수는_서로_다른_작성자를_센다():
    t = by_id(compute_trend([m("1", "p", "a"), m("2", "p", "a"), m("3", "p", "b")], AS_OF))["p"]
    assert t.mention_count == 3
    assert t.author_count == 2


def test_같은_게시물이_같은_제품을_두번_언급해도_한번만_센다():
    t = by_id(compute_trend([m("1", "p", "a"), m("1", "p", "a")], AS_OF))["p"]
    assert t.mention_count == 1


# ── 반복 언급 감쇠 ─────────────────────────────────────────────

def test_같은_작성자의_반복_언급은_1_05_025로_줄여_더한다():
    ms = [m(str(k), "p", "brand") for k in range(3)]
    t = by_id(compute_trend(ms, AS_OF))["p"]
    weights = sorted((p["weight"] for p in t.breakdown["posts"]), reverse=True)
    assert weights == [1.0, 0.5, 0.25]
    one = t.breakdown["posts"][0]["score"]
    assert t.raw_score == pytest.approx(one * 1.75)


def test_한_계정의_반복보다_여러_작성자의_언급이_이긴다():
    spam = [m(f"s{k}", "spam", "brand") for k in range(10)]
    crowd = [m(f"c{k}", "crowd", f"u{k}") for k in range(3)]
    t = by_id(compute_trend(spam + crowd, AS_OF))
    assert t["crowd"].raw_score > t["spam"].raw_score


# ── 광고 가중치 ───────────────────────────────────────────────

def test_광고는_03_판별_전은_06_광고_아님은_1이다():
    ms = [m("1", "ad", "a", is_ad=True), m("2", "org", "a", is_ad=False), m("3", "unk", "a", is_ad=None)]
    t = by_id(compute_trend(ms, AS_OF))
    assert t["ad"].raw_score / t["org"].raw_score == pytest.approx(AD_WEIGHT[True])
    assert t["unk"].raw_score / t["org"].raw_score == pytest.approx(AD_WEIGHT[None])
    assert t["ad"].ad_mention_count == 1 and t["unk"].unlabeled_count == 1


# ── 7일 반감기 · 집계 기간 ────────────────────────────────────

def test_최신성은_7일마다_절반이다():
    assert recency(0) == 1.0
    assert recency(7) == pytest.approx(0.5)
    assert recency(14) == pytest.approx(0.25)


def test_28일_밖의_게시물은_집계하지_않는다():
    ms = [m("1", "p", "a", days_ago=WINDOW_DAYS - 1), m("2", "p", "b", days_ago=WINDOW_DAYS), m("3", "p", "c", days_ago=-1)]
    t = by_id(compute_trend(ms, AS_OF))["p"]
    assert t.mention_count == 1


# ── 결측 참여도 ───────────────────────────────────────────────

def test_좋아요를_숨긴_게시물은_평소_수준으로_본다():
    e, note = engagement(m("1", "p", "a", likes=None), {}, {})
    assert e == pytest.approx(ENGAGEMENT_DEFAULT) and note == "좋아요 결측"


def test_좋아요를_숨겨도_언급이_사라지지_않는다():
    t = by_id(compute_trend([m("1", "p", "a", likes=None)], AS_OF))["p"]
    assert t.raw_score > 0


def test_게시물이_5개_이상이면_계정_중앙값_아니면_규모_중앙값을_쓴다():
    ms = [m(str(k), "p", "big", likes=100) for k in range(5)] + [m("x", "p", "small", likes=50)]
    author_base, bucket_base = engagement_baselines(ms)
    assert author_base == {"big": 100}
    assert engagement(m("y", "p", "big", likes=300), author_base, bucket_base) == (1.0, "계정 중앙값")
    e, note = engagement(m("z", "p", "small", likes=75), author_base, bucket_base)
    assert note == "규모 중앙값" and 0 < e < 1


def test_집계일_이후_게시물은_평소_반응에_넣지_않는다():
    ms = [m("1", "p", "a", likes=100), m("2", "p", "b", likes=100)]
    future = [m(f"f{k}", "", "a", days_ago=-1, likes=10_000) for k in range(5)]
    assert compute_trend(ms, AS_OF, baseline_mentions=ms + future)[0].raw_score == \
        pytest.approx(compute_trend(ms, AS_OF, baseline_mentions=ms)[0].raw_score)


def test_평소_반응이_0이면_평소_수준으로_본다():
    e, note = engagement(m("1", "p", "a", likes=0), {"a": 0}, {})
    assert e == pytest.approx(ENGAGEMENT_DEFAULT)


def test_팔로워가_많을수록_영향력이_크지만_로그로_줄어든다():
    assert influence(1_000) < influence(100_000) < influence(1_000_000) == 1.0
    assert influence(100_000) / influence(1_000) < 100


# ── TOP 10 자격 ──────────────────────────────────────────────

def test_작성자가_한_명뿐이면_순위에_올리지_않는다():
    ms = [m("1", "solo", "a"), m("2", "solo", "a"), m("3", "duo", "a"), m("4", "duo", "b")]
    t = by_id(compute_trend(ms, AS_OF))
    assert MIN_AUTHORS == 2
    assert t["solo"].rank is None and t["solo"].breakdown["low_confidence"]
    assert t["duo"].rank == 1


def test_순위는_최대_10개다():
    ms = [m(f"{p}-{k}", f"p{p:02d}", f"u{k}") for p in range(12) for k in range(2)]
    assert len(top_trends(compute_trend(ms, AS_OF))) == TOP_N


def test_raw_score는_원본이고_score는_1위가_100인_표시용이다():
    ms = [m("1", "a", "x"), m("2", "a", "y"), m("3", "b", "x", days_ago=7), m("4", "b", "y", days_ago=7)]
    t = by_id(compute_trend(ms, AS_OF))
    assert t["a"].score == 100.0
    assert t["b"].raw_score == pytest.approx(t["a"].raw_score / 2)


# ── 합성 데이터 격리 ──────────────────────────────────────────

def test_합성_언급은_명시적으로_허용해야_계산한다():
    ms = [m("1", "p", "a", source="synthetic")]
    with pytest.raises(ValueError):
        compute_trend(ms, AS_OF)
    assert compute_trend(ms, AS_OF, allow_synthetic=True)


def test_평소_반응_자료에_섞인_합성_데이터도_거부한다():
    ms = [m("1", "p", "a")]
    base = [m("2", "", "a", source="synthetic")]
    with pytest.raises(ValueError):
        compute_trend(ms, AS_OF, baseline_mentions=base)
    assert compute_trend(ms, AS_OF, allow_synthetic=True, baseline_mentions=base)


# ── 합성 게시물 66개 (data/synthetic/trend/posts_v1.jsonl) ───────────────

def _load():
    rows = [json.loads(line)["input"] for line in POSTS.read_text(encoding="utf-8").splitlines()]
    return [Mention(post_id=r["post_id"], product_id=r["product_id"], author=r["author"],
                    posted_at=date.fromisoformat(r["posted_at"]), followers=r["followers"],
                    like_count=r["like_count"], comment_count=r["comment_count"], is_ad=r["is_ad"],
                    age_group=r["age_group"], source=r["source_kind"]) for r in rows]


def test_합성_데이터는_66개를_1부터_15개까지_배분했다():
    ms = _load()
    assert len(ms) == 66
    counts = {}
    for x in ms:
        counts[x.product_id] = counts.get(x.product_id, 0) + 1
    assert sorted(counts.values()) == [1, 2, 3, 4, 5, 6, 8, 10, 12, 15]
    assert all(x.source == "synthetic" for x in ms)


def test_합성_데이터에_심은_성질이_결과에_나타난다():
    t = by_id(compute_trend(_load(), AS_OF, allow_synthetic=True))
    # 작성자 1명인 제품은 자격이 없다
    assert t["syn-p01"].rank is None and t["syn-p02"].rank is None and t["syn-p02"].author_count == 1
    # 28일 밖 3개는 빠진다
    assert t["syn-p05"].mention_count == 2
    # 좋아요를 숨긴 4개는 평소 수준으로 들어간다
    assert sum(p["engagement_note"] == "좋아요 결측" for p in t["syn-p06"].breakdown["posts"]) == 4
    # 판별 전 게시물은 따로 센다
    assert t["syn-p04"].unlabeled_count == 4
    # 최근 · 비광고 · 작성자 10명인 제품이 1위다
    assert t["syn-p08"].rank == 1
    # 비슷한 조건에 광고 10개가 섞이면 그보다 낮다
    assert t["syn-p09"].raw_score < t["syn-p08"].raw_score
    # 본인 브랜드 12번 반복은 감쇠되어 게시물 수(15)만큼 점수가 오르지 않는다
    brand = [p for p in t["syn-p10"].breakdown["posts"] if p["author"] == "syn_brand"]
    assert len(brand) == 12 and min(p["weight"] for p in brand) == 0.5 ** 11
    assert t["syn-p10"].rank > t["syn-p08"].rank
