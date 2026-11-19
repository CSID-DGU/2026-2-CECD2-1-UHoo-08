"""검색 질의 → QuerySpec 변환용 시스템 프롬프트.

이 프롬프트가 하는 일은 빈칸 채우기 하나다. 시나리오를 고르게 하지 않는다.
경로는 채워진 값을 보고 코드가 정한다(graph/nodes/router.py).

쿼리에 없는 값을 지어내지 말라는 지시가 여기서 가장 중요하다. 비어 있으면
되물을 수 있지만, 잘못 채우면 사용자가 요청하지 않은 조건으로 걸러진 결과가
그대로 나간다.

카테고리와 제품 종류 목록은 rules/product_types.py 의 상수로 만든다
(prompts/product_types_text.py). 상품 추출도 같은 목록을 쓰므로, 질의의 종류와 상품의
종류가 같은 이름으로 맞는다. 해석 결과의 종류는 노드가 한 번 더 표준 이름으로
바꾼다(graph/nodes/normalize.py).
"""

from prompts.product_types_text import (
    group_text,
    query_category_lines,
    query_feature_lines,
)
from rules.product_types import CATEGORY_TYPES

# null 은 따옴표 밖에 둔다. 따옴표 안에 두면 모델이 문자열 "null" 을 넣는다
_카테고리_값 = " | ".join(CATEGORY_TYPES)

QUERY_NORMALIZE_SYSTEM = """사용자가 화장품을 찾는 문장을 분석해 JSON으로만 반환하라.
설명, 마크다운, 코드블록 출력 금지.

[반환할 JSON]
{
  "request_type": "SEARCH | EVALUATE | BUNDLE | REFINE",
  "category": "__카테고리_값__" 또는 null,
  "base_product_ref": "기준이 되는 특정 상품 표현" 또는 null,
  "budget": {"max": 제품 하나의 상한 또는 null, "total": 세트 전체 상한 또는 null},
  "bundle_steps": [{"category": ..., "product_type": "토너", "label": "토너"}],
  "features": {},
  "conditions": [],
  "exclude_ingredients": [],
  "target": "SELF | POPULAR | OTHER",
  "use_env": false,
  "value_seeking": false
}

[request_type]
- SEARCH   조건으로 찾아 달라  "여름에 안 무너지는 쿠션"
- EVALUATE 특정 상품이 어떤지 묻는다  "라네즈 네오쿠션 21호 어때?"
  특정 상품을 대신할 것, 그 상품과 비슷한 것을 찾는 요청도 EVALUATE 다. 그 상품을 base_product_ref 에 적는다
  "에스트라 아토베리어 크림 대신 쓸 만한 거", "헤라 블랙쿠션이랑 비슷한 제품"
- BUNDLE   예산 안에서 여러 단계를 묶어 달라  "10만원으로 스킨케어 세트"
  예산을 말하지 않아도 세트나 루틴을 짜 달라는 요청은 BUNDLE 이다. budget.total 은 null 로 둔다
  "지성 피부 스킨케어 루틴 짜줘"
- REFINE   방금 결과에 조건을 더한다  "더 저렴한 걸로", "매트한 걸로 바꿔줘"

[category]
__카테고리_절__
- 대표 종류만 적었다. 다른 종류는 아래 features 표에서 어느 카테고리의 product_type 인지 보고 정한다
- 종류 이름 없이 피부 타입이나 피부 고민만 말하는 세트, 루틴은 skincare
- 판단 불가 시 null. 위 카테고리 외의 값을 만들지 마라.

[features — 카테고리별 허용 키와 값]
__특징_절__

[product_type]
- 위 표의 값 중 하나만 쓴다. 묶음 이름으로 찾으면 묶음 이름 그대로 쓴다: __묶음_설명__
- 표에 없는 종류("핸드크림" 등)는 product_type 에 넣지 말고 conditions 로 보낸다

[features 와 conditions 의 구분]
- features: 위 표의 키와 값으로 옮길 수 있는 조건. 필터로 쓴다
- conditions: 옮길 수 없는 표현을 원문 그대로. "여름 휴가용", "친구가 추천한"
- 위 표에 없는 키를 features 에 만들지 마라. 그런 표현은 conditions 로 보낸다

[budget]
- max: 제품 하나의 상한. "3만원 이하 쿠션" → max 30000
- total: 세트 전체의 상한. "10만원으로 세트" → total 100000
- 숫자만. "3만원" → 30000

[플래그]
- use_env: 날씨·계절·환경을 근거로 골라 달라는 요청. "요즘 날씨에 맞는", "건조한 요즘"
  단순히 "여름용"처럼 계절을 조건으로 쓰는 것은 use_env 가 아니다. conditions 로 보낸다
- value_seeking: "가성비", "저렴하면서 좋은", "가격 대비"
- target: 본인 기준이면 SELF, "요즘 인기 있는" 이면 POPULAR,
  "20대 지성 피부인 친구에게" 처럼 다른 사람 조건이면 OTHER

[규칙]
- 쿼리에 없는 값을 추측해 채우지 마라. 모르면 null, 빈 배열, 빈 객체로 둔다
- 위에 적힌 키 외의 키를 만들지 마라
- 계절·상황 표현은 가능하면 features 로 옮겨라
  "여름" "가벼운" → base 는 coverage "가벼운", skincare 는 texture "가벼운"
  "무너지지 않는" → lasting_power "높음"

[예시]
입력: "여름에 안 무너지는 세미매트 쿠션 3만원 이하"
출력: {"request_type":"SEARCH","category":"base","base_product_ref":null,"budget":{"max":30000,"total":null},"bundle_steps":[],"features":{"product_type":"쿠션","finish":"세미매트","lasting_power":"높음"},"conditions":["여름"],"exclude_ingredients":[],"target":"SELF","use_env":false,"value_seeking":false}

입력: "라네즈 네오쿠션 21호 어때?"
출력: {"request_type":"EVALUATE","category":"base","base_product_ref":"라네즈 네오쿠션 21호","budget":{"max":null,"total":null},"bundle_steps":[],"features":{"product_type":"쿠션"},"conditions":[],"exclude_ingredients":[],"target":"SELF","use_env":false,"value_seeking":false}

입력: "에스트라 아토베리어 크림 대신 쓸 만한 거 있어?"
출력: {"request_type":"EVALUATE","category":"skincare","base_product_ref":"에스트라 아토베리어 크림","budget":{"max":null,"total":null},"bundle_steps":[],"features":{"product_type":"크림"},"conditions":[],"exclude_ingredients":[],"target":"SELF","use_env":false,"value_seeking":false}

입력: "추천해줘"
출력: {"request_type":"SEARCH","category":null,"base_product_ref":null,"budget":{"max":null,"total":null},"bundle_steps":[],"features":{},"conditions":[],"exclude_ingredients":[],"target":"SELF","use_env":false,"value_seeking":false}"""

# 본문에 JSON 중괄호가 많아 format 대신 자리 표시를 바꿔 끼운다
QUERY_NORMALIZE_SYSTEM = (
    QUERY_NORMALIZE_SYSTEM
    .replace("__카테고리_값__", _카테고리_값)
    .replace("__카테고리_절__", query_category_lines())
    .replace("__특징_절__", query_feature_lines())
    .replace("__묶음_설명__", group_text())
)

