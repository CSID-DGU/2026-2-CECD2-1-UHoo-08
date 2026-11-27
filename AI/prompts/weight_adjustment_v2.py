"""점수 가중치 보정 프롬프트 (점수 v2).

가중치를 새로 정하게 하지 않고 지금 가중치에 곱할 배수만 받는다. 새 값을 받으면
피드백으로 쌓인 선호와 요청 조건으로 정한 값이 LLM 한 번에 지워진다. 배수는
0.5~2.0 으로 묶여 있어서 보정이 기존 값을 뒤집지 못한다.

LLM 은 숫자로 정하기 어려운 맥락만 본다. 검색 목적(선물, 출근 등)과 문장으로 남은
조건이다. 예산, 환경, 가성비처럼 플래그로 이미 반영한 것은 다시 보정하지 않게 한다.
"""
from __future__ import annotations

import json

from contracts.score import SCORE_LABELS

WEIGHT_ADJUSTMENT_V2_SYSTEM = """화장품 추천 점수의 항목별 가중치를 조금 보정한다.
JSON 객체 하나로만 답하라. 설명, 마크다운, 코드블록 출력 금지.

[입력]
- 켜진 점수 항목과 지금 가중치
- 사용자의 검색 목적과 문장으로 남은 조건

[출력]
{"항목 키": 배수, ...}
- 켜진 항목 키만 쓴다. 다른 키를 만들지 마라
- 배수는 0.5 이상 2.0 이하 실수. 바꿀 이유가 없으면 1.0
- 이유가 분명한 항목만 1.0 에서 벗어나게 한다

[판단 기준]
- GIFT(선물): 받는 사람 만족이 중요하다. review 를 올리고, 내 피부 기준인 personalization 은 내린다
- DAILY, OFFICE(일상, 출근): 오래 쓸 제품이다. personalization 을 올린다
- TRAVEL(여행): 실용성이 중요하다. budget_fit, price_value 를 올린다
- SPECIAL, DATE(특별한 날): review, personalization 을 올린다
- 조건 문장에 후기, 평이 좋은 제품을 찾는 말이 있으면 review 를 올린다
- 예산, 환경, 가성비는 이미 반영되어 있다. 그것만을 이유로 배수를 바꾸지 마라"""


def build_weight_adjustment_v2_user_prompt(
    weights: dict[str, float],
    search_purpose: str | None,
    conditions: list[str],
    value_seeking: bool,
) -> str:
    """켜진 항목(가중치가 0보다 큰 항목)만 보여 준다. 꺼진 항목을 보이면 켜려고 한다."""
    켜진 = {
        키: {"이름": SCORE_LABELS.get(키, 키), "가중치": round(값, 4)}
        for 키, 값 in weights.items() if 값 > 0
    }
    return (
        f"켜진 점수 항목: {json.dumps(켜진, ensure_ascii=False)}\n"
        f"검색 목적: {search_purpose or '없음'}\n"
        f"조건 문장: {json.dumps(conditions, ensure_ascii=False)}\n"
        f"가성비 요청: {'예' if value_seeking else '아니오'}\n\n"
        "항목별 배수를 JSON으로만 출력하라."
    )
