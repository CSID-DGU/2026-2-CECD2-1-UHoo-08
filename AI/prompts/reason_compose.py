"""추천 이유 문장 프롬프트.

결과 카드마다 한 줄짜리 이유를 붙인다. 카드 10개를 한 번에 맡긴다. 카드마다 부르면
LLM 호출이 10번이라 결과가 늦게 나온다.

LLM 에게는 점수가 높은 항목과 질의 조건, 배지만 준다. 점수 근거 밖의 이야기를 지어내지
않게 하려는 것이다. 화장품은 의약품이 아니라 진단, 치료, 효과를 단정하는 말은 쓰면 안
된다. 여기서 막고, 결과 점검 단계(Guard)가 한 번 더 본다.
"""
from __future__ import annotations

import json
from typing import Any

# 이유 문장 최대 글자 수. 카드 한 줄에 들어가야 한다.
이유_최대_글자 = 40

REASON_COMPOSE_SYSTEM = f"""화장품 추천 결과 카드마다 추천 이유 한 문장을 쓴다.
JSON 객체 하나로만 답하라. 설명, 마크다운, 코드블록 출력 금지.

[입력]
- 사용자가 건 조건
- 상품마다 id, 이름, 점수가 높은 항목(이름과 0~100 점수), 카드에 붙은 배지

[출력]
{{"상품 id": "이유 문장", ...}}
- 입력의 상품 id 마다 하나씩 쓴다. 다른 id 를 만들지 마라
- {이유_최대_글자}자 이내의 한 문장, 해요체
- 점수가 높은 항목과 조건을 근거로 쓴다. 입력에 없는 성분, 효과, 후기 내용을 지어내지 마라
- 점수 숫자를 그대로 쓰지 마라

[쓰면 안 되는 말]
- 진단, 치료, 완치, 처방, 의학적, 약효 같은 의료 표현
- 효과 보장, 100%, 무조건, 절대, 부작용 없음 같은 단정
- "아토피에 좋아요" 처럼 피부 질환에 효과가 있다고 말하는 문장

[예]
{{"p1": "건성 피부에 맞고 원하신 매트한 마무리예요"}}"""


def build_reason_compose_user_prompt(conditions: list[str], cards: list[dict[str, Any]]) -> str:
    """cards: [{product_id, name, top_items: [{label, score}], badges: [문구]}]"""
    return (
        f"조건: {json.dumps(conditions, ensure_ascii=False)}\n"
        f"상품: {json.dumps(cards, ensure_ascii=False)}\n\n"
        "상품마다 이유 문장을 JSON으로만 출력하라."
    )
