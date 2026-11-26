"""ProductMatcher v1 프롬프트: 캡션 → 제품 언급 추출, 후보 판정.

추출 LLM 은 "캡션이 무엇을 말하는지"만 적는다. 상품 마스터의 어느 행인지는 고르지
않는다. 그건 DB 후보 검색과 규칙(rules/product_match)이 정하고, 애매할 때만 판정 LLM 이
주어진 후보 ID 중에서 고른다. LLM 이 모르는 제품 ID 를 지어내지 못하게 하려는 분리다.

버전을 바꾸면 캐시가 새로 쌓인다 (services/product_extractor).
"""

EXTRACT_VERSION = "extract-v1"
VERIFY_VERSION = "verify-v1"

EXTRACT_SYSTEM = """인스타그램 게시물 캡션에서 언급된 화장품을 모두 뽑는다.

[규칙]
- 캡션에 실제로 적힌 제품만 뽑는다. 원문에 없는 제품명을 추측하거나 보충하지 않는다.
- 브랜드만 나오고 제품을 특정할 수 없으면 mention_type 을 "brand_only", product_name 을 null 로 둔다.
  브랜드만 보고 그 브랜드의 대표 제품을 떠올려 채우지 않는다.
- "틴트 추천", "쿠션 뭐 써요" 처럼 종류만 나오면 mention_type 을 "category_only" 로 둔다.
- 해시태그(#롬앤쥬시래스팅틴트), 브랜드 공식 계정명(herabeauty_official), 줄바꿈 목록도 근거가 된다.
- 화장품이 아닌 것(옷 · 가방 · 음식 · 가전 · 네일 · 헤어 기기)은 넣지 않는다.
- 같은 제품을 여러 번 말하면 한 번만 넣는다. 호수 · 컬러가 여러 개여도 제품이 같으면 하나다.
- 제품 언급이 없으면 빈 배열을 낸다.

[필드]
- brand: 캡션에 적힌 브랜드 표기 그대로 (한글이든 영문이든). 모르면 null
- product_name: 브랜드를 뺀 제품명. 캡션 표기 그대로. 호수 · 컬러 · 용량은 뺀다
- variant: 호수 · 컬러명이 있으면 (예: "23호", "체리온탑"), 없으면 null
- category: base(쿠션·파운데이션·프라이머·컨실러) | sun(선크림·선스틱·선쿠션·선세럼) |
  lip(틴트·립스틱·립글로스·립밤·립펜슬) | skincare(토너·세럼·에센스·앰플·크림·로션·오일) |
  other(아이 · 치크 · 클렌징 · 마스크팩 · 바디 등 위에 없는 화장품)
- evidence: 그 제품을 가리키는 캡션 원문 구간을 한 글자도 바꾸지 않고 그대로 복사한다
- mention_type: product | brand_only | category_only
- specificity: exact(제품명이 정확히 적힘) | partial(일부 · 줄임말 · 애칭) | ambiguous(여러 제품일 수 있음)

JSON 만 출력한다:
{"mentions": [{"brand": "...", "product_name": "..." 또는 null, "variant": "..." 또는 null,
  "category": "...", "evidence": "...", "mention_type": "...", "specificity": "..."}]}"""

VERIFY_SYSTEM = """인스타그램 캡션의 제품 언급 하나가 상품 마스터의 어느 제품인지 고른다.

후보 목록 안에서만 고른다. 후보에 없는 제품 ID 를 만들지 않는다.
- 같은 제품이 확실하면 그 후보의 id 를 고른다. 호수 · 컬러 · 용량 · 기획 구성 차이는 같은 제품으로 본다.
- 이름이 비슷해도 다른 라인 · 다른 제형이면 고르지 않는다 (예: "립 세럼" 과 "립 스틱", "팁 컨실러" 와 "컨실러 펜슬").
- 후보 중에 맞는 제품이 없으면 "unmatched".
- 둘 이상이 맞을 수 있어 하나로 정할 수 없으면 "review".

JSON 만 출력한다: {"choice": "<후보 id>" | "review" | "unmatched", "reason": "한 문장"}"""


def build_extract_user(caption: str, username: str, owned_brands: list[str] | None) -> str:
    owned = ", ".join(owned_brands) if owned_brands else "없음"
    return f"[계정] @{username} (운영 브랜드: {owned})\n\n[캡션]\n{caption}"


def build_verify_user(caption: str, mention: dict, candidates: list[dict]) -> str:
    lines = "\n".join(f"- id={c['product_id']} | {c['brand']} | {c['name']} | {c.get('category') or ''}" for c in candidates)
    m = {k: mention.get(k) for k in ("brand", "product_name", "variant", "category", "evidence")}
    return f"[캡션]\n{caption}\n\n[추출한 언급]\n{m}\n\n[후보]\n{lines}"
