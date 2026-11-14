"""화면에 나가는 문장에 쓰면 안 되는 표현을 찾는다.

화장품은 의약품이 아니다. 질환을 진단하거나 치료한다는 말, 효과를 보장하는 말은
광고 심의에 걸리고 사용자를 속이게 된다. 추천 이유는 LLM 이 쓰므로 프롬프트로 막아도
가끔 새어 나온다. 결과를 내보내기 직전에 한 번 더 본다.

걸린 이유 문장은 점수가 높은 두 항목으로 만든 규칙 문장으로 바꾼다. 규칙 문장은
점수 항목 이름만 쓰므로 금지 표현이 들어갈 수 없다.
"""
from __future__ import annotations

import re
from typing import Any

from contracts.score import SCORE_LABELS

# 질환 이름. "~에 좋아요", "~ 개선", "~ 증상 완화" 처럼 효과를 말할 때만 걸린다.
# "여드름 피부 사용자가 많이 써요" 처럼 피부 상태를 말하는 문장은 걸리지 않는다.
_질환 = r"(아토피|여드름|건선|습진|지루성\s*피부염|피부염|주사비|안면홍조증|백반증|탈모)"
_질환_효과 = (
    r"(좋|효과|개선|낫|나아|없애|잡아|완화|줄여|줄이|줄어|예방|억제|진정|호전|가라앉|사라)"
)

금지_표현: tuple[re.Pattern[str], ...] = tuple(re.compile(p) for p in (
    r"치료", r"완치", r"처방", r"진단", r"의학적", r"약효",
    r"효과\s*(를|가)?\s*보장", r"보장\s*해", r"100\s*%",
    r"무조건", r"절대", r"부작용\s*(이|은|도)?\s*없",
    r"피부과\s*전문의",
    _질환 + r"\s*(증상|흉터|자국)?\s*(에|을|를|이|가|도)?\s*" + _질환_효과,
))


def has_forbidden(문장: str | None) -> bool:
    if not 문장:
        return False
    return any(p.search(문장) for p in 금지_표현)


def fallback_reason(breakdown: list[dict[str, Any]]) -> str | None:
    """점수가 높은 두 항목으로 만든 이유 문장. 항목이 없으면 None."""
    항목들 = sorted(breakdown or [], key=lambda 항목: 항목["score"], reverse=True)[:2]
    if not 항목들:
        return None
    이름들 = ", ".join(SCORE_LABELS.get(항목["key"], 항목["label"]) for 항목 in 항목들)
    return f"{이름들} 점수가 높아요"
