import base64
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import settings
from models.extracted_product import ExtractedProduct
from prompts.product_types_text import category_lines

PROMPT = """너는 화장품 상품 이미지 분석 전문가이다.

주어진 이미지에서 보이는 정보만 근거로 상품 정보를 추출하라.
이미지에 보이지 않는 정보는 절대 추측하지 말고 null로 출력하라.

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
- detected_objects: 이미지에서 읽히는 모든 텍스트를 넣어라.
- package_claims: 패키지에 표시된 효능/특징/마케팅 문구만 넣어라.
- brand: 영문 대문자로 표기 (예: HERA, LANEIGE, PRETTYSKIN)
- volume: 숫자만 추출 (예: "15g" → 15, "100mL" → 100)
- unit: g 또는 ml 중 하나만
- 상품명, 브랜드, 용량, 색상은 이미지에서 확인 가능한 경우만 채워라.
- 모르는 값은 null. 배열 정보가 없으면 빈 배열 []."""

# 카테고리와 종류 목록은 상수로 만든다. 본문에 JSON 중괄호가 많아 format 대신 바꿔 끼운다
PROMPT = PROMPT.replace("__카테고리_절__", category_lines())

# TODO(llm): services.llm 의 vlm 역할로 옮긴다. 사진 인식 모델을 바꿔 보려면
#            여기와 services/llm 두 곳을 같이 고쳐야 해서, 지금은 비교가 번거롭다.
_client = ChatOpenAI(
    model=settings.QWEN_VL_MODEL,
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.QWEN_VL_BASE_URL,
    temperature=0,
    max_tokens=1024,
)


def parse_image(image_bytes: bytes) -> ExtractedProduct:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    message = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
        },
        {"type": "text", "text": PROMPT},
    ])
    response = _client.invoke([message])

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()

    return ExtractedProduct(**json.loads(raw))
