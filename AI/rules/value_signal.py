"""가성비 점수 (value-v1). 가격이 사용자에게 맞는지와, 같은 제품군에서 싸게 살 수 있는지를 본다.

LLM 을 부르지 않는다. 같은 입력이면 같은 점수다. 점수는 0~1 이고 scorer 가 0~100 으로 바꾼다.

    현재 가격 점수  A = 0.7 F + 0.3 P        (예산이 없으면 A = P)
      F 예산 적합도   1 - 판매가 / 예산. 예산 안 상품끼리도 싼 쪽이 높다
      P 상대 가격     같은 제품군(카테고리 × 제품 종류) 안 판매가 순위. 1 - (순위 - 1) / (N - 1),
                      동점은 평균 순위. 비교 기준은 검색 후보가 아니라 상품 마스터 전체다.
                      후보가 바뀔 때마다 같은 상품의 점수가 달라지지 않게 하기 위해서다.
                      제품군 상품이 MIN_PEERS 개 미만이면 순위가 의미 없어 계산하지 않는다.
    할인율          d = 1 - 판매가 / 정가                       (실제 할인율, 근거 · 문구에 쓴다)
    할인 점수       D = min(1, d / DISCOUNT_FULL_AT)            (50% 할인이면 만점)
                    실제 할인율은 대부분 20% 안팎이라 그대로 쓰면 할인 비중을 올릴수록 점수 전체가
                    낮아진다. 배지 기준(70점)이 고정이라 가성비를 중시하는 사용자일수록 배지가
                    사라진다. price_value 와 같은 눈금(50% 이상 만점)으로 맞춘다.
    가성비 점수     V = (1 - α) A + α D,  α = 0.05 + 0.35 u
      u 가성비 선호도 0~1. 클수록 할인율을 더 본다. α 는 최대 0.4 라 할인율만으로 정해지지 않는다.
      할인 점수를 50% 만점으로 키운 뒤 0.1 + 0.5 u 로는 기본 사용자(0.5)도 할인 쪽으로 크게
      쏠려, 세 안을 실데이터로 비교해 이 값으로 정했다.

결측은 0 으로 채우지 않는다. 정가가 없다는 것과 할인을 안 한다는 것은 다르다. 빠진 요소는
빼고 남은 요소의 가중치를 다시 맞춘다. 다만 현재 가격 점수 A 는 반드시 있어야 한다.
예산도 상대 가격도 없으면 할인율이 있어도 점수를 내지 않는다(None). 할인율만으로 점수를
내면 비교할 제품군이 없는 상품이 오히려 높은 점수를 받는다. 판매가가 없어도 None 이다.

서비스 범위(SCOPE_CATEGORIES) 밖 카테고리 상품은 점수를 내지 않고, 상대 가격 비교에도 넣지 않는다.

예산 초과 상품은 검색 단계에서 이미 걸러진다. 여기에 들어오면 F = 0 으로 두고 근거에 남긴다.
할인율은 다른 점수 항목(price_value)에도 있다. 가성비 항목은 가성비를 원하는 요청에서만
켜지므로, 그 요청에서 할인을 더 강조하는 것은 의도한 것이다.

가중치(0.7 / 0.3, α)는 멘토링 피드백을 구현하려고 정한 초기값이다.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from rules.product_types import product_types

FORMULA_VERSION = "value-v1"

W_BUDGET = 0.7          # 현재 가격 점수에서 예산 적합도 몫
W_RELATIVE = 0.3        # 현재 가격 점수에서 상대 가격 몫
ALPHA_BASE = 0.05       # 할인율 가중치 최소
ALPHA_RANGE = 0.35      # 선호도 1 일 때 더해지는 할인율 가중치
# 서비스가 다루는 카테고리. 상품 마스터 · 트렌드와 같은 범위다. 아이 · 치크 상품은 마스터에
# 남아 있어도 가성비를 따지지 않는다
SCOPE_CATEGORIES = frozenset({"base", "sun", "lip", "skincare"})
MIN_PEERS = 5           # 상대 가격을 내는 제품군 최소 상품 수
DISCOUNT_FULL_AT = 0.5  # 이 할인율 이상이면 할인 점수 만점. price_value 와 같은 눈금
DEFAULT_PREFERENCE = 0.5
# 사용자 선호 가중치의 value_signal 값이 이만큼이면 선호도 1. 0 이면 기본 0.5.
# 가성비 질의가 켜는 최소 가중치(0.3)와 같은 눈금이다
PREFERENCE_FULL_AT = 0.3

# 근거 문구 · 코드 기준
CHEAP_IN_GROUP = 0.7    # 상대 가격이 이 이상이면 제품군 안에서 싼 편
HIGH_DISCOUNT = 0.2     # 할인율이 이 이상이면 할인 폭이 큰 편
UNDER_BUDGET = 0.2      # 예산보다 이 비율 이상 싸면 예산 대비 저렴

Group = tuple[str, str]


@dataclass
class ValueBreakdown:
    score: float | None
    budget_fit: float | None = None
    relative_price: float | None = None
    discount_rate: float | None = None      # 실제 할인율
    discount_score: float | None = None     # 산식에 쓰는 정규화 할인 점수
    price_score: float | None = None
    weights: dict[str, float] = field(default_factory=dict)
    group: Group | None = None
    peer_count: int = 0
    reason_codes: list[str] = field(default_factory=list)
    formula_version: str = FORMULA_VERSION


def _positive(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if v > 0 else None


def sale_price(product: dict) -> float | None:
    """현재 판매가. 최저가가 없으면 계산하지 않는다(정가로 대신하면 할인 0% 로 보인다)."""
    return _positive(product.get("lowest_price"))


def group_of(product: dict) -> Group | None:
    """비교 제품군: (카테고리, 첫 번째 표준 제품 종류). 둘 중 하나라도 모르면 None."""
    category = product.get("category")
    if category not in SCOPE_CATEGORIES:
        return None
    types = product_types(product.get("feature_json") or {}, category)
    if not types:
        return None
    return (category, types[0])


def group_prices(master: Iterable[dict]) -> dict[Group, dict[str, float]]:
    """상품 마스터 → {제품군: {product_id: 판매가}}. 판매가 없는 상품은 뺀다."""
    out: dict[Group, dict[str, float]] = defaultdict(dict)
    for p in master:
        g, price = group_of(p), sale_price(p)
        if g and price is not None:
            out[g][p["product_id"]] = price
    return dict(out)


def relative_price(product_id: str, price: float, peers: dict[str, float]) -> tuple[float | None, int]:
    """제품군 안 상대 가격 (점수, 비교 상품 수). 이 상품이 마스터에 없으면 넣어서 센다."""
    prices = dict(peers)
    prices[product_id] = price
    n = len(prices)
    if n < MIN_PEERS:
        return None, n
    lower = sum(1 for v in prices.values() if v < price)
    equal = sum(1 for v in prices.values() if v == price)   # 자기 자신 포함
    rank = lower + (equal + 1) / 2                         # 평균 순위 (1부터)
    return 1 - (rank - 1) / (n - 1), n


def budget_fit(price: float, budget: float | None) -> float | None:
    if not budget or budget <= 0:
        return None
    return max(0.0, 1 - price / budget)


def discount_rate(price: float, original: Any) -> float | None:
    """할인율. 정가가 없으면 None, 판매가가 정가 이상이면 0."""
    original = _positive(original)
    if original is None:
        return None
    # 1 - 28000/35000 이 0.19999… 로 나와 20% 기준에서 빠지지 않게 반올림한다
    return round(max(0.0, 1 - price / original), 4)


def discount_score(rate: float | None) -> float | None:
    """실제 할인율 → 할인 점수 0~1. DISCOUNT_FULL_AT 이상이면 1."""
    if rate is None:
        return None
    return min(1.0, rate / DISCOUNT_FULL_AT)


def preference(weight: Any) -> float:
    """사용자 선호 가중치의 value_signal 값 → 가성비 선호도 0~1. 값이 없으면 기본값."""
    if weight is None or isinstance(weight, bool) or not isinstance(weight, (int, float)):
        return DEFAULT_PREFERENCE
    w = max(0.0, float(weight))
    return min(1.0, DEFAULT_PREFERENCE + (1 - DEFAULT_PREFERENCE) * w / PREFERENCE_FULL_AT)
