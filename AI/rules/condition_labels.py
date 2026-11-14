"""질의 조건을 화면에 보일 짧은 말로 바꾼다.

조건 수정 화면은 "지금 걸린 조건" 을 칩으로 그린다. 특징 조건은 키와 값으로
저장되어 있어서 그대로 보이면 "coverage: 높음" 처럼 읽힌다. "커버력 높음" 처럼
사람이 읽는 말로 바꾼다.

예산은 넣지 않는다. BE 가 budgetMax, budgetTotal 로 따로 그린다.
"""
from __future__ import annotations

from typing import Any

from contracts.query_spec import QuerySpec
from contracts.result import QuerySummary

# 값 앞뒤에 붙일 말. 표에 없는 키는 값을 그대로 쓴다.
_값_형식: dict[str, str] = {
    "coverage": "커버력 {}",
    "lasting_power": "지속력 {}",
    "texture": "{} 제형",
    "skin_type": "{} 피부",
}
# 참, 거짓 값의 키. 그 값일 때만 말이 된다.
_참거짓_말: dict[tuple[str, bool], str] = {
    ("fragrance_free", True): "무향",
    ("white_cast", False): "백탁 없음",
    ("moisturizing", True): "보습",
}


def _한_특징(키: str, 값: Any) -> list[str]:
    if 값 is None:
        return []
    if isinstance(값, bool):
        말 = _참거짓_말.get((키, 값))
        return [말] if 말 else []
    if isinstance(값, list):
        return [str(v) for v in 값 if v is not None and str(v).strip()]
    return [_값_형식.get(키, "{}").format(값)]


def feature_labels(features: dict[str, Any]) -> list[str]:
    """특징 조건을 짧은 말 목록으로. 같은 말은 한 번만."""
    말들 = [말 for 키, 값 in features.items() for 말 in _한_특징(키, 값)]
    return list(dict.fromkeys(말들))


def summarize(spec: QuerySpec, raw_query: str | None) -> QuerySummary:
    """결과의 query 칸. 특징 조건을 읽는 말로 바꾼 것 뒤에 문장 조건 원문을 잇는다."""
    조건 = feature_labels(spec.features) + [c for c in spec.conditions if c.strip()]
    return QuerySummary(
        raw=raw_query or "",
        category=spec.category,
        conditions=list(dict.fromkeys(조건)),
        budget_max=spec.budget.max,
        budget_total=spec.budget.total,
        target=spec.target,
        use_env=spec.use_env,
        value_seeking=spec.value_seeking,
    )
