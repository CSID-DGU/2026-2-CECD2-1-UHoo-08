"""price_value: 할인율 기반 가성비 점수."""
from typing import Optional

from rules.product_match import discount_score


def compute(
    lowest_price: Optional[int],
    original_price: Optional[int],
) -> int:
    """
    할인율 = 1 - lowest/original.
    할인 0% → 50점, 50% 이상 → 100점, 그 사이 선형 매핑.
    데이터 없으면 50점 중립.
    """
    점수 = discount_score(lowest_price, original_price)
    return 50 if 점수 is None else 점수
