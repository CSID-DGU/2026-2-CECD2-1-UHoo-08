"""키워드 순위 → 제품 점수. 홈 '요즘 뜨는 제품'을 키워드 기준으로 매기는 규칙이다.

캡션 속 제품을 직접 식별하는 대신, 성분 · 고민 키워드의 순위를 받아 그 키워드에
해당하는 제품에 점수를 준다. 결과가 제품 단위라 기존 product_trend_daily · API ·
화면을 그대로 쓴다.

1. 제품 ↔ 키워드: 제품이 가진 키워드를 feature_json 의 key_ingredient · skin_concern,
   상품명으로 찾는다(data/trend_keywords.json 의 product_* 기준).
2. 순위대로 점수: 키워드 TOP_N 개에 1위 TOP_N 점, 2위 TOP_N-1 점, … TOP_N 위 1점.
3. 제품 점수: 제품이 가진 키워드의 점수를 더한다.

같은 키워드 조합을 가진 제품은 점수가 같다. 동점은 그대로 두고, 순위는 보여 주는 쪽이
순서대로 매긴다. 키워드에 하나도 해당하지 않는 제품은 점수가 없어 결과에서 빠진다.
키워드 순위를 어떻게 매기는지는 이 파일이 정하지 않는다. 받은 순위를 점수로 바꿀 뿐이다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from rules.keyword_extract import KeywordDictionary

TOP_N = 10


@dataclass(frozen=True)
class KeywordRank:
    """순위에 오른 키워드 하나. 언급 수 등은 제품 점수에 근거로 함께 싣는다."""
    keyword_id: str
    rank: int
    mention_count: int = 0
    ad_mention_count: int = 0
    engagement: int = 0


@dataclass
class ProductScore:
    product_id: str
    score: int
    keywords: list[dict] = field(default_factory=list)  # [{keyword_id, rank, points, via}]
    mention_count: int = 0
    ad_mention_count: int = 0
    engagement: int = 0


def _features(product: dict) -> dict:
    f = product.get("feature_json") or {}
    if isinstance(f, str):
        f = json.loads(f)
    return f if isinstance(f, dict) else {}


def _values(v) -> set[str]:
    if v is None:
        return set()
    if isinstance(v, list):
        return {str(x) for x in v if x is not None}
    return {str(v)}


def product_keywords(product: dict, d: KeywordDictionary) -> dict[str, str]:
    """제품 → {keyword_id: 근거}. 근거는 ingredient:값 · concern:값 · name:표기 중 처음 걸린 것."""
    f = _features(product)
    ingredients, concerns = _values(f.get("key_ingredient")), _values(f.get("skin_concern"))
    name = (product.get("name") or "").lower()
    out = {}
    for kw in d.keywords:
        hit = next((f"ingredient:{v}" for v in kw.product_ingredients if v in ingredients), None)
        hit = hit or next((f"concern:{v}" for v in kw.product_concerns if v in concerns), None)
        hit = hit or next((f"name:{v}" for v in kw.product_name_forms if v in name), None)
        if hit:
            out[kw.id] = hit
    return out


def keyword_points(ranks: list[KeywordRank]) -> dict[str, tuple[int, int]]:
    """키워드 → (순위, 점수). 1위가 TOP_N 점, TOP_N 위가 1점. TOP_N 밖은 점수가 없다."""
    return {r.keyword_id: (r.rank, TOP_N + 1 - r.rank) for r in ranks if 1 <= r.rank <= TOP_N}


def product_scores(ranks: list[KeywordRank], products: list[dict], d: KeywordDictionary) -> list[ProductScore]:
    """키워드 순위 → 제품 점수 (점수 내림차순, 동점은 product_id 순). 0점 제품은 뺀다."""
    points = keyword_points(ranks)
    by_kw = {r.keyword_id: r for r in ranks}
    out = []
    for p in products:
        kws = [(k, via) for k, via in product_keywords(p, d).items() if k in points]
        if not kws:
            continue
        kws.sort(key=lambda x: points[x[0]][0])
        out.append(ProductScore(
            product_id=p["product_id"],
            score=sum(points[k][1] for k, _ in kws),
            keywords=[{"keyword_id": k, "rank": points[k][0], "points": points[k][1], "via": via} for k, via in kws],
            mention_count=sum(by_kw[k].mention_count for k, _ in kws),
            ad_mention_count=sum(by_kw[k].ad_mention_count for k, _ in kws),
            engagement=sum(by_kw[k].engagement for k, _ in kws),
        ))
    out.sort(key=lambda s: (-s.score, s.product_id))
    return out
