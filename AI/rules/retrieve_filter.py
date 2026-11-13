"""검색으로 찾은 후보 중 질의 조건을 어긴 것을 거른다.

거르는 것은 어기면 추천 자체가 틀리는 조건뿐이다.
    제품 종류     "쿠션" 을 찾는데 파운데이션이 나오면 안 된다
    예산 상한     "3만원 이하" 인데 4만원이 나오면 안 된다
    제외 성분     "레티놀 빼고" 인데 레티놀이 든 제품이 나오면 안 된다

그 밖의 특징(제형, 마무리감 등)은 거르지 않는다. 조금 덜 맞는 상품도 다른 점이
좋으면 추천할 만하다. 얼마나 맞는지는 점수(query_fit)가 따진다.

모르는 값은 대부분 남긴다. 제품 종류나 성분을 모른다고 빼면 정보가 비어 있는 상품은
영영 추천되지 않는다. 예산만은 다르다. 가격을 모르는 상품은 예산을 지켰는지 보장할 수
없으므로 뺀다.

DB, 임베딩 없이 받은 값만으로 거른다. 성분은 부른 쪽이 읽어 넘긴다.
"""
from __future__ import annotations

from typing import Any

from contracts.query_spec import QuerySpec


def _같은_말(글: str) -> str:
    return "".join(글.split()).casefold()


def _제품_종류(메타: dict[str, Any]) -> str | None:
    return (메타.get("feature_json") or {}).get("product_type")


def _어긴_조건(
    메타: dict[str, Any] | None,
    spec: QuerySpec,
    성분: list[str] | None,
    뺄_성분: set[str],
) -> bool:
    메타 = 메타 or {}

    원하는_종류 = spec.features.get("product_type")
    종류 = _제품_종류(메타)
    if 원하는_종류 and 종류 and _같은_말(종류) != _같은_말(str(원하는_종류)):
        return True

    상한 = spec.budget.max
    if 상한 is not None:
        가격 = 메타.get("price")
        if 가격 is None or 가격 > 상한:
            return True

    if 뺄_성분 and 성분:
        if 뺄_성분 & {_같은_말(이름) for 이름 in 성분}:
            return True

    return False


def apply(
    candidates: list[dict],
    meta: dict[str, dict],
    spec: QuerySpec,
    *,
    ingredients: dict[str, list[str]] | None,
    limit: int,
) -> list[dict]:
    """조건을 어긴 후보를 빼고, 유사도 순 상위 limit 개를 남긴다.

    ingredients 가 None 이면 성분을 읽지 못한 것이다. 제외 성분 조건을 건너뛴다.
    후보에 slot_key 가 있으면(예산 세트) 칸마다 limit 개를 남긴다.
    """
    뺄_성분 = {_같은_말(이름) for 이름 in spec.exclude_ingredients if 이름.strip()}
    if ingredients is None:
        뺄_성분 = set()

    남은 = [
        후보 for 후보 in candidates
        if not _어긴_조건(
            meta.get(후보["product_id"]), spec,
            (ingredients or {}).get(후보["product_id"]), 뺄_성분,
        )
    ]
    남은.sort(key=lambda 후보: 후보.get("similarity") or 0.0, reverse=True)

    칸별_수: dict[Any, int] = {}
    결과 = []
    for 후보 in 남은:
        칸 = 후보.get("slot_key")
        if 칸별_수.get(칸, 0) >= limit:
            continue
        칸별_수[칸] = 칸별_수.get(칸, 0) + 1
        결과.append(후보)
    return 결과
