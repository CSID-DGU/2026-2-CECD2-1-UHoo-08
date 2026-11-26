"""노드끼리 함께 쓰는 상품 정보.

후보를 찾은 노드가 상품 정보를 한 번 읽어 상태의 product_meta 에 담고, 뒤 노드는
그것을 읽는다. 노드마다 같은 상품을 다시 조회하면 후보 수만큼 조회가 늘어난다.

노드는 이렇게 쓴다.

    {"product_meta": await ensure(state.get("product_meta") or {}, ids)}

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없이는 이 모듈을
불러오지도 못한다.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# 한 번에 읽는 상품 수. id 목록이 요청 주소에 실리므로 너무 길게 보내지 않는다.
조회_묶음 = 100


def _가격(행: dict[str, Any]) -> int | None:
    """화면과 점수가 쓰는 가격. 최저가가 있으면 최저가, 없으면 정가."""
    if 행.get("lowest_price") is not None:
        return 행["lowest_price"]
    return 행.get("original_price")


async def ensure(meta: dict[str, dict], product_ids: Iterable[str]) -> dict[str, dict]:
    """meta 에 없는 상품만 읽어 합친 새 dict 를 돌려준다.

    meta 자체는 바꾸지 않는다. 노드는 바꾼 키만 돌려주고 빌더가 합치므로,
    받은 값을 직접 고치면 실패했을 때 어디까지 바뀌었는지 알 수 없다.
    DB 에 없는 상품은 담지 않는다.
    """
    from db.product_reader import get_products_full

    빠진: list[str] = []
    for pid in product_ids:
        if pid and pid not in meta and pid not in 빠진:
            빠진.append(pid)

    합친 = dict(meta)
    for 시작 in range(0, len(빠진), 조회_묶음):
        묶음 = 빠진[시작:시작 + 조회_묶음]
        읽은 = await asyncio.to_thread(get_products_full, 묶음)
        for pid, 행 in 읽은.items():
            합친[pid] = {**행, "price": _가격(행)}

    없는 = [pid for pid in 빠진 if pid not in 합친]
    if 없는:
        logger.warning("상품 %d 개를 찾지 못했다: %s", len(없는), 없는[:5])
    return 합친
