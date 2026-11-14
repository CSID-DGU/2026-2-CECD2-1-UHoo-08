"""조건 수정 선택지를 질의 조건으로 바꾼다.

키와 문장은 BE 의 RefinePreset 과 같아야 한다. BE 는 고른 선택지의 문장 뒤에 직접 쓴
문장을 붙여 쉼표로 이어 raw_query 로 보낸다.
    "더 저렴한 제품으로, 여름에 쓸 것"

선택지는 문장을 해석하지 않고 이 표대로 바로 반영한다. 같은 선택지가 늘 같은 조건이
되어야 수정 이력에 같은 변화로 보인다.

DB, LLM 없이 받은 값만으로 바꾼다.
"""
from __future__ import annotations

import math
import statistics
from typing import Any

from contracts.query_spec import QuerySpec

# 키 → BE 가 보내는 문장
PRESETS: dict[str, str] = {
    "CHEAPER": "더 저렴한 제품으로",
    "UNSCENTED": "무향 제품으로",
    "HIGH_COVERAGE": "커버력이 높은 제품으로",
    "LONG_LASTING": "지속력이 좋은 제품으로",
    "UV_PROTECT": "자외선 차단이 되는 제품으로",
    "SENSITIVE_OK": "민감한 피부에도 괜찮은 제품으로",
}

# 더 저렴하게: 기준가의 이 비율을 새 상한으로, 이 단위로 내린다
저렴_비율 = 0.8
가격_단위 = 1000
# 기준가로 쓰는 이전 결과 카드 수
기준가_카드_수 = 5

# 특징으로 바로 거를 수 있는 카테고리. 그 밖은 문장 조건으로 둔다
_무향_특징 = frozenset({"skincare"})
_커버력_특징 = frozenset({"base"})
_지속력_특징 = frozenset({"base", "sun", "lip"})
_민감_특징 = frozenset({"base", "sun", "skincare"})

# 특징으로 바꾸지 못할 때 붙이는 문장 조건
_문장_조건 = {
    "CHEAPER": "저렴한",
    "UNSCENTED": "무향",
    "HIGH_COVERAGE": "커버력 높은",
    "LONG_LASTING": "지속력 좋은",
    "UV_PROTECT": "자외선 차단",
    "SENSITIVE_OK": "민감 피부",
}


def strip_sentences(raw_query: str | None) -> str:
    """raw_query 에서 선택지 문장을 지우고 직접 쓴 문장만 남긴다."""
    조각들 = [조각.strip() for 조각 in (raw_query or "").split(",")]
    문장들 = set(PRESETS.values())
    return ", ".join(조각 for 조각 in 조각들 if 조각 and 조각 not in 문장들)


def base_price(parent_spec: QuerySpec, parent_result: dict | None) -> int | None:
    """더 저렴하게의 기준가. 이전 예산 상한, 없으면 이전 결과 상위 카드 가격의 중앙값."""
    if parent_spec.budget.max:
        return parent_spec.budget.max
    가격들 = [
        카드["price"] for 카드 in ((parent_result or {}).get("items") or [])[:기준가_카드_수]
        if 카드.get("price")
    ]
    return int(statistics.median(가격들)) if 가격들 else None


def cheaper_max(기준가: int) -> int:
    return math.floor(기준가 * 저렴_비율 / 가격_단위) * 가격_단위


def _조건_추가(값: dict[str, Any], 조건: str) -> None:
    if 조건 not in 값["conditions"]:
        값["conditions"].append(조건)


def apply(
    spec: QuerySpec,
    keys: list[str],
    parent_spec: QuerySpec,
    parent_result: dict | None,
) -> QuerySpec:
    """선택지를 질의 조건에 반영한 새 QuerySpec. 모르는 키는 건너뛴다.

    카테고리마다 특징으로 거를 수 있는 것은 features 에, 아닌 것은 conditions 에 둔다.
    """
    값 = spec.model_dump()
    값["features"] = dict(값["features"])
    값["conditions"] = list(값["conditions"])
    카테고리 = spec.category.value if spec.category else None

    for 키 in keys:
        if 키 == "CHEAPER":
            기준가 = base_price(parent_spec, parent_result)
            if 기준가 and cheaper_max(기준가) > 0:
                값["budget"] = {**값["budget"], "max": cheaper_max(기준가)}
            else:
                _조건_추가(값, _문장_조건[키])
        elif 키 == "UNSCENTED" and 카테고리 in _무향_특징:
            값["features"]["fragrance_free"] = True
        elif 키 == "HIGH_COVERAGE" and 카테고리 in _커버력_특징:
            값["features"]["coverage"] = "높음"
        elif 키 == "LONG_LASTING" and 카테고리 in _지속력_특징:
            값["features"]["lasting_power"] = "높음"
        elif 키 == "SENSITIVE_OK" and 카테고리 in _민감_특징:
            값["features"]["skin_type"] = "민감"
        elif 키 in _문장_조건:
            _조건_추가(값, _문장_조건[키])

    return QuerySpec.model_validate(값)
