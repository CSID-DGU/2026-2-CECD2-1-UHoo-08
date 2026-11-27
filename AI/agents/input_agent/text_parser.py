import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import settings
from models.extracted_product import ExtractedProduct
from prompts.product_types_text import category_lines

PROMPT = """너는 화장품 상품 정보 추출 전문가이다.

주어진 텍스트에서 언급된 정보만 근거로 상품 정보를 추출하라.
텍스트에 없는 정보는 절대 추측하지 말고 null로 출력하라.

반드시 유효한 JSON만 출력하라.
설명 문장, 마크다운, 코드블록은 출력하지 마라.

[추출 대상]

{
  "product_name": null,
  "brand": null,
  "category": {
    "main": null,
    "sub": null
  },
  "attributes": {
    "shade": null,
    "type": null,
    "volume": null,
    "unit": null
  },
  "package_claims": [],
  "detected_objects": []
}

[카테고리 분류 기준]
__카테고리_절__
category.main에는 위 카테고리 중 하나를 넣어라. 세부 유형이 목록에 없어도 속하는 카테고리가 분명하면 넣는다. 예: 핸드크림은 skincare.
category.sub에는 위 세부 제품 유형을 글자 그대로 넣어라. 목록에 없는 유형이면 null.

[규칙]
- detected_objects: 텍스트에서 언급된 상품명, 성분, 특징 등 주요 키워드를 넣어라.
- package_claims: 텍스트에서 언급된 효능/특징 문구만 넣어라.
- brand: 영문 대문자로 표기 (예: HERA, LANEIGE, PRETTYSKIN)
- volume: 숫자만 추출 (예: "15g" → 15, "100mL" → 100)
- unit: g 또는 ml 중 하나만
- 모르는 값은 null. 배열 정보가 없으면 빈 배열 []."""

# 카테고리와 종류 목록은 상수로 만든다. 본문에 JSON 중괄호가 많아 format 대신 바꿔 끼운다
PROMPT = PROMPT.replace("__카테고리_절__", category_lines())

# TODO(llm): services.llm 으로 옮긴다. nfc_parser 와 같은 설정을 따로 만들고 있다.
_client = ChatOpenAI(
    model=settings.QWEN_TEXT_MODEL,
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.QWEN_TEXT_BASE_URL,
    temperature=0,
    max_tokens=1024,
)


def parse_text(text: str) -> ExtractedProduct:
    message = HumanMessage(content=f"{PROMPT}\n\n[입력 텍스트]\n{text}")
    response = _client.invoke([message])

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()

    return ExtractedProduct(**json.loads(raw))
