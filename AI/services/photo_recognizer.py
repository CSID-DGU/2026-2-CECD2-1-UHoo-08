"""사진 두 장으로 보유 제품을 인식한다.

    제품명 면   사진 모델이 브랜드와 제품 이름을 읽는다 → 상품 목록과 견줘 후보를 고른다
    기한 면     사진 모델이 사용기한, 제조일, 개봉 후 사용 기간을 읽는다 → 규칙으로 확인한다

모델의 답은 그대로 쓰지 않는다. 후보는 일치도와 함께 내고 사용자가 고른다
(rules/name_matching.py). 기한은 확인을 통과한 값만 채우고 나머지는 비운다
(rules/date_reading.py). 틀린 날짜를 채우면 사용자가 그대로 믿고 등록한다.

인식 원본(raw)에는 모델이 읽은 값과, 확인에서 버린 값의 이유를 남긴다. BE 가 등록할 때 함께
저장해, 사용자가 고친 최종값과 견줘 인식 정확도를 잰다.

모델이 답을 JSON 으로 쓰지 않았으면 RecognizeError 를 낸다. 읽은 값이 없다는 답과는 다르다.
그쪽은 모델이 사진을 보고 비운 것이다. 사진을 받지 못했거나(PhotoError) 모델 호출이
실패하면 예외를 그대로 올린다. 빈 결과로 덮으면 장애가 "읽을 글자가 없는 사진"으로 보인다.

config, LLM SDK, DB 모듈은 함수 안에서 가져온다. 키 없이 테스트할 수 있어야 한다.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from contracts.internal_api import ProductCandidate, RecognizePhotosResponse
from prompts.photo_recognize import (
    DATE_FACE_SYSTEM,
    NAME_FACE_SYSTEM,
    NAME_FACE_USER,
    date_face_user,
)
from rules import date_reading, name_matching
from services import photo_loader

logger = logging.getLogger(__name__)

# 사진 한 장에 모델의 답을 기다리는 최대 시간(초). SDK 기본값(10분)에 맡기지 않는다.
# BE 는 인식 호출을 60초에 끊는다
MODEL_TIMEOUT_S = 20.0

# 인식 원본에 남기는 글 하나의 최대 길이. 모델이 작은 글씨까지 길게 옮겨 적는 일이 있다
RAW_TEXT_MAX = 300

# 사용자가 있는 곳의 오늘을 정하는 시간대. 제조일이 오늘보다 뒤인지를 이 날짜로 본다
KST = timezone(timedelta(hours=9))

# 다듬은 사진의 형식. photo_loader 가 JPEG 로 바꿔 돌려준다
_사진_형식 = "image/jpeg"

# 기한 면의 인식 원본에서, 모델의 답 키 → 원본에 남기는 이름
_기한_원본_키 = {
    "expiry_date": "expiryDate",
    "expiry_text": "expiryText",
    "mfg_date": "mfgDate",
    "mfg_text": "mfgText",
    "pao_months": "paoMonths",
    "pao_text": "paoText",
}
# 제품명 면의 인식 원본에서, 모델의 답 키 → 원본에 남기는 이름
_이름_원본_키 = {
    "brand": "brand",
    "brand_en": "brandEn",
    "brand_ko": "brandKo",
    "product_name": "productName",
    "product_name_ko": "productNameKo",
}
# 기한 면의 원본을 제품명 면의 원본 옆에 붙일 때 쓰는 키. BE 가 두 요청의 원본을 합칠 때와 같다
_기한_원본_자리 = "expiry"


class RecognizeError(Exception):
    """사진 모델의 답을 쓸 수 없다."""


def _답_읽기(글: Any) -> dict | None:
    """모델이 쓴 글에서 JSON 객체를 꺼낸다. 앞뒤에 붙은 말과 코드블록 표시는 버린다."""
    if not isinstance(글, str):
        return None
    시작, 끝 = 글.find("{"), 글.rfind("}")
    if 시작 < 0 or 끝 < 시작:
        return None
    try:
        값 = json.loads(글[시작:끝 + 1])
    except json.JSONDecodeError:
        return None
    return 값 if isinstance(값, dict) else None


def _원본_값(값: Any) -> Any:
    """인식 원본에 남길 값. 글은 앞뒤 공백을 떼고 길이를 자르며, 빈 글은 None 이다.

    숫자는 그대로 두고, 목록이나 객체처럼 양식에 없는 모양은 남기지 않는다.
    """
    if isinstance(값, str):
        return 값.strip()[:RAW_TEXT_MAX] or None
    if isinstance(값, (bool, int, float)):
        return 값
    return None


def _읽은_글자(답: dict) -> str:
    값 = _원본_값(답.get("read_text"))
    return 값 if isinstance(값, str) else ""


async def _모델에_묻기(system: str, user: str, 사진: bytes, llm: Any) -> dict:
    """사진 한 장을 모델에 보내고 답을 JSON 으로 읽는다. 읽지 못하면 RecognizeError."""
    # 부를 일이 생긴 뒤에 가져온다. 최상단에 두면 설정과 SDK 를 통째로 불러온다
    from services.llm import LLMImage, LLMRole, get_llm

    if llm is None:
        llm = get_llm(LLMRole.VLM)
    # JSON 응답 옵션은 켜지 않는다. 사진 모델마다 받는 옵션이 달라, 프롬프트로 JSON 만 쓰게 하고
    # 답에서 직접 꺼낸다
    글 = await llm.chat(
        system=system,
        user=user,
        images=[LLMImage(data=사진, mime_type=_사진_형식)],
        timeout=MODEL_TIMEOUT_S,
    )
    답 = _답_읽기(글)
    if 답 is None:
        logger.warning("사진 인식: 모델의 답이 JSON 이 아니다 %r", 글[:200] if isinstance(글, str) else 글)
        raise RecognizeError("사진 모델의 답을 읽지 못했다")
    return 답


async def recognize_name(photo: bytes, *, llm: Any = None) -> tuple[list[name_matching.Candidate], dict]:
    """제품명 면 사진에서 상품 후보를 찾는다. 후보와 인식 원본을 돌려준다.

    photo 는 다듬은 JPEG 바이트다. 후보가 없어도 오류가 아니다. 화면이 이름 검색으로 안내한다.
    """
    from db.product_reader import list_products_meta

    # 모델이 읽는 동안 상품 목록을 읽어 둔다
    답, 상품들 = await asyncio.gather(
        _모델에_묻기(NAME_FACE_SYSTEM, NAME_FACE_USER, photo, llm),
        asyncio.to_thread(list_products_meta),
    )
    후보들 = name_matching.match(답, 상품들)
    logger.info(
        "사진 인식(제품명 면): 후보 %d개, 가장 높은 일치도 %.2f",
        len(후보들), 후보들[0].confidence if 후보들 else 0.0,
    )

    원본: dict[str, Any] = {"readText": _읽은_글자(답)}
    원본.update({이름: _원본_값(답.get(키)) for 키, 이름 in _이름_원본_키.items()})
    return 후보들, 원본


async def recognize_dates(
    photo: bytes, today: date, *, llm: Any = None,
) -> tuple[date_reading.DateReading, dict]:
    """기한 면 사진에서 사용기한, 제조일, 개봉 후 사용 기간을 읽는다. 확인한 값과 인식 원본을 돌려준다.

    photo 는 다듬은 JPEG 바이트다. 읽지 못했거나 확인을 통과하지 못한 값은 None 이다.
    """
    답 = await _모델에_묻기(DATE_FACE_SYSTEM, date_face_user(today), photo, llm)
    읽은 = date_reading.verify(답, today)
    logger.info(
        "사진 인식(기한 면): 사용기한 %s, 제조일 %s, 개봉 후 사용 기간 %s, 버린 값 %s",
        "읽음" if 읽은.expiry_date else "없음",
        "읽음" if 읽은.mfg_date else "없음",
        "읽음" if 읽은.pao_months else "없음",
        읽은.dropped or "없음",
    )

    원본: dict[str, Any] = {"readText": _읽은_글자(답)}
    원본.update({이름: _원본_값(답.get(키)) for 키, 이름 in _기한_원본_키.items()})
    # 모델이 값을 줬지만 확인에서 버린 것과 그 이유
    원본["dropped"] = {_기한_원본_키[키]: 이유 for 키, 이유 in 읽은.dropped.items()}
    return 읽은, 원본


def _후보로(후보: name_matching.Candidate) -> ProductCandidate:
    상품 = 후보.product
    return ProductCandidate(
        product_id=상품["id"],
        name=상품.get("name") or "",
        brand=상품.get("brand") or "",
        image_url=상품.get("image_url"),
        confidence=후보.confidence,
    )


async def recognize(
    name_image: str | None,
    date_image: str | None,
    *,
    llm: Any = None,
    today: date | None = None,
) -> RecognizePhotosResponse:
    """받은 면만 인식해 응답을 만든다. 두 면을 함께 받으면 동시에 읽는다.

    name_image, date_image 는 사진 주소다. 보내지 않은 면의 값은 비어 있다.
    today 를 주지 않으면 한국 시간의 오늘이다.
    """
    오늘 = today or datetime.now(KST).date()

    async def 이름_면() -> tuple[list[name_matching.Candidate], dict]:
        return await recognize_name(await photo_loader.load(name_image), llm=llm)

    async def 기한_면() -> tuple[date_reading.DateReading, dict]:
        return await recognize_dates(await photo_loader.load(date_image), 오늘, llm=llm)

    if name_image and date_image:
        (후보들, 이름_원본), (읽은, 기한_원본) = await asyncio.gather(이름_면(), 기한_면())
        원본 = {**이름_원본, _기한_원본_자리: 기한_원본}
    elif name_image:
        후보들, 원본 = await 이름_면()
        읽은 = date_reading.DateReading()
    else:
        읽은, 원본 = await 기한_면()
        후보들 = []

    return RecognizePhotosResponse(
        candidates=[_후보로(후보) for 후보 in 후보들],
        expiry_date=읽은.expiry_date,
        pao_months=읽은.pao_months,
        mfg_date=읽은.mfg_date,
        raw=원본,
    )
