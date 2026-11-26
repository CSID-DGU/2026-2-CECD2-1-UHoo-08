"""검색창 자연어 쿼리 → 카테고리 + feature 추출용 Qwen 시스템 프롬프트.

카테고리와 제품 종류 목록은 질의 해석(query_normalize)과 같은 것을 쓴다
(prompts/product_types_text.py).
"""
from prompts.product_types_text import category_lines, query_feature_lines

QUERY_EXTRACTION_SYSTEM = """사용자가 화장품을 검색하는 자연어 문장을 분석해 JSON으로만 반환하라.
설명, 마크다운, 코드블록 출력 금지.

[카테고리]
__카테고리_절__

[카테고리별 feature 허용값]
__특징_절__

[규칙]
- category는 위 카테고리 중 하나. 판단 불가 시 null
- product_type은 위 표의 값 중 하나. 표에 없는 종류면 product_type 키를 생략
- features에는 쿼리에서 명확히 파악되는 값만 포함. 나머지 키는 아예 생략
- 쿼리에 없는 값을 추측하지 마라
- 계절·상황 표현은 가능한 feature로 변환 (예: "여름" "가벼운" → base는 coverage "가벼운" / skincare는 texture "가벼운", "무너지지 않는" → lasting_power "높음")

[출력 예시]
입력: "여름에 안 무너지는 세미매트 쿠션"
출력: {"category": "base", "features": {"product_type": "쿠션", "finish": "세미매트", "lasting_power": "높음"}}"""

# 본문에 JSON 중괄호가 있어 format 대신 자리 표시를 바꿔 끼운다
QUERY_EXTRACTION_SYSTEM = (
    QUERY_EXTRACTION_SYSTEM
    .replace("__카테고리_절__", category_lines())
    .replace("__특징_절__", query_feature_lines())
)
