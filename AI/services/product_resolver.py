"""질의 속 상품 이름을 상품 id 로 바꾼다.

"라네즈 네오쿠션 어때?" 는 평가 경로로 가지만 Normalize 가 남기는 것은 상품
이름 문자열이다. 평가 경로의 노드는 상품 id 가 있어야 돈다.

못 찾으면 None 을 돌려준다. 비슷한 상품을 추측해서 고르면 사용자가 묻지 않은
상품을 평가하게 된다. 그보다는 되묻는 편이 낫다.

이름 비교는 이렇게 한다.
    1. 공백으로 나눈 단어에서 호수, 색상 번호("21호", "#13", "N20")는 뺀다
    2. 상품의 브랜드에 들어 있는 단어도 뺀다. 상품명에는 브랜드가 없는 경우가 많다
    3. 남은 단어가 모두 상품명에 들어 있으면 같은 상품으로 본다
비교할 때는 공백과 대소문자를 무시한다. "네오쿠션" 과 "네오 쿠션" 은 같다.
후보는 단어 하나로 상품명, 브랜드 부분 일치 검색을 해서 모은다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없이는 이 모듈을
불러오지도 못한다.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid

logger = logging.getLogger(__name__)

# 단어 하나로 상품명, 브랜드를 찾을 때 가져올 후보 수
검색_상한 = 20
# 호수, 색상 번호. "21호", "13N", "#21", "N20", "02번" 같은 표기
_호수_표기 = re.compile(r"^#?[a-z]?\d+[a-z]?(호|번)?$", re.IGNORECASE)


def _다듬기(글: str) -> str:
    return re.sub(r"\s+", "", 글).lower()


def _단어들(ref: str) -> list[str]:
    """비교에 쓸 단어. 호수, 색상 번호는 뺀다."""
    return [w for w in ref.split() if w and not _호수_표기.match(w)]


def _uuid_인가(ref: str) -> bool:
    try:
        uuid.UUID(ref)
    except ValueError:
        return False
    return True


def _같은_상품인가(단어들: list[str], 상품: dict) -> bool:
    브랜드 = _다듬기(상품.get("brand") or "")
    이름 = _다듬기(상품.get("name") or "")
    남은 = [_다듬기(w) for w in 단어들 if not (브랜드 and _다듬기(w) in 브랜드)]
    # 브랜드만 말한 경우는 어떤 상품인지 모른다
    return bool(남은) and all(w in 이름 for w in 남은)


async def _id_로_찾기(ref: str) -> str | None:
    from db.product_reader import get_product_meta

    상품 = await asyncio.to_thread(get_product_meta, ref)
    return 상품["id"] if 상품 else None


async def _이름으로_찾기(ref: str) -> str | None:
    from db.product_reader import search_products_by_name

    단어들 = _단어들(ref)
    # 긴 단어일수록 상품명일 가능성이 높고 후보가 적다. 먼저 찾아 본다.
    for 단어 in sorted(단어들, key=len, reverse=True):
        # 이름 검색은 부분 일치라 "네오쿠션" 으로는 "네오 쿠션" 을 못 찾는다.
        # 그대로 찾아 없으면 글자 사이에 와일드카드를 넣어 띄어쓰기를 무시한다.
        for 검색어 in dict.fromkeys((단어, "%".join(단어))):
            후보 = await asyncio.to_thread(search_products_by_name, 검색어, 검색_상한)
            맞는 = [p for p in 후보 if _같은_상품인가(단어들, p)]
            if 맞는:
                # 같은 결과가 나오도록 덧붙은 말이 가장 적은 이름, 그다음 id 순으로 고른다
                return min(맞는, key=lambda p: (len(p.get("name") or ""), p["id"]))["id"]
    return None


async def resolve(ref: str | None) -> str | None:
    """상품 이름이나 id 를 상품 id 로 바꾼다. 못 찾으면 None."""
    ref = (ref or "").strip()
    if not ref:
        return None
    if _uuid_인가(ref):
        찾은 = await _id_로_찾기(ref)
    else:
        찾은 = await _이름으로_찾기(ref)
    if 찾은 is None:
        logger.info("상품 '%s' 를 찾지 못했다.", ref)
    return 찾은
