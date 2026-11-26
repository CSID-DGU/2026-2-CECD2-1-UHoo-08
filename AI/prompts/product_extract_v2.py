"""ProductMatcher v2 추출 프롬프트. 캡션 → [{brand, product_name}] 만 받는다.

v1(prompts/product_extract.py)은 category · evidence · mention_type 까지 받았고, category 값이 정해진 다섯 개 밖이면
코드가 언급째 버렸다(235개 중 36건). v2 는 브랜드와 제품명만 받고, 범위 판단과 브랜드 보정은 코드가 한다.
"""
EXTRACT_V2_VERSION = "extract-v2"

EXTRACT_V2_SYSTEM = """인스타그램 게시물 캡션에서 언급된 화장품을 모두 뽑는다.

[규칙]
- 캡션에 실제로 적힌 제품만 뽑는다. 원문에 없는 제품명을 추측하거나 보충하지 않는다.
- product_name 은 캡션에 적힌 표기 그대로 쓴다. 브랜드 · 호수 · 컬러 · 용량 · 가격 · 기획 구성은 뺀다.
- 브랜드가 캡션에 적혀 있으면 brand 에 적힌 그대로 쓴다(한글 · 영문 · 공식 계정명 모두 가능). 없으면 null.
- 화장품 종류를 가리지 않는다: 스킨케어 · 베이스 · 립 · 선케어 · 아이 · 치크 · 클렌징 · 마스크팩 · 헤어 · 바디 · 네일.
- 화장품이 아닌 것(옷 · 가방 · 신발 · 음식 · 가전 · 렌즈 · 굿즈 · 사은품 파우치)은 넣지 않는다.
- 브랜드만 나오고 제품을 특정할 수 없거나, "틴트 추천"처럼 종류만 나오면 넣지 않는다.
- 해시태그(#롬앤쥬시래스팅틴트)와 줄바꿈 목록도 근거가 된다.
- 같은 제품을 여러 번 말하면 한 번만 넣는다. 호수 · 컬러가 여러 개여도 제품이 같으면 하나다.
- 제품 언급이 없으면 빈 배열을 낸다.

JSON 만 출력한다:
{"products": [{"brand": "..." 또는 null, "product_name": "..."}]}"""


def build_extract_v2_user(caption: str, username: str) -> str:
    return f"[계정] @{username}\n\n[캡션]\n{caption}"
