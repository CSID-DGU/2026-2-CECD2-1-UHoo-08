"""사진 인식 서비스가 지켜야 할 성질.

모델의 답은 그대로 나가지 않는다. 후보는 상품 목록과 견줘 고르고, 기한은 확인을 통과한
값만 채운다. 모델을 부르지 못한 것과 읽을 글자가 없는 것은 다른 결과여야 한다.
"""
import json
import sys
import types
from datetime import date, datetime, timezone

import pytest

from contracts.internal_api import RecognizePhotosResponse
from prompts.photo_recognize import DATE_FACE_SYSTEM, NAME_FACE_SYSTEM
from rules import date_reading
from services import photo_loader, photo_recognizer
from services.photo_loader import PhotoError
from services.photo_recognizer import RecognizeError, recognize

오늘 = date(2026, 11, 22)
_이름_사진 = "https://storage.example.com/user-product-photos/u1/name.jpg?token=secret"
_기한_사진 = "https://storage.example.com/user-product-photos/u1/date.jpg?token=secret"

_상품들 = [
    {"id": "neo-mui", "name": "라네즈 네오 쿠션 뮤이", "brand": "LANEIGE", "category": "base",
     "image_url": "https://img.example.com/neo-mui.jpg", "price": 30000},
    {"id": "neo-glow", "name": "네오 쿠션 글로우", "brand": "LANEIGE", "category": "base",
     "image_url": None, "price": 30000},
    {"id": "juicy", "name": "쥬시 래스팅 틴트", "brand": "ROM&ND", "category": "lip",
     "image_url": None, "price": 9000},
    {"id": "naming", "name": "네이밍 퍼펙테일 아이 펜슬", "brand": None, "category": "eye",
     "image_url": None, "price": 12000},
]

_이름_답 = {
    "read_text": "LANEIGE NEO CUSHION MUI 15g",
    "brand": "LANEIGE", "brand_en": "LANEIGE", "brand_ko": "라네즈",
    "product_name": "NEO CUSHION MUI", "product_name_ko": "네오 쿠션 뮤이",
}
_기한_답 = {
    "read_text": "EXP 2028.03.30 MFG 2026.03.31 12M",
    "expiry_date": "2028-03-30", "expiry_text": "EXP 2028.03.30",
    "mfg_date": "2026-03-31", "mfg_text": "MFG 2026.03.31",
    "pao_months": 12, "pao_text": "12M",
}


class 가짜LLM:
    """면마다 정해 둔 답을 돌려준다. 답이 예외면 던진다. 받은 호출을 남긴다."""

    def __init__(self, 이름=None, 기한=None):
        self.답 = {NAME_FACE_SYSTEM: 이름, DATE_FACE_SYSTEM: 기한}
        self.호출: list[dict] = []

    async def chat(self, system, user, **값):
        self.호출.append({"system": system, "user": user, **값})
        답 = self.답[system]
        if isinstance(답, Exception):
            raise 답
        return json.dumps(답, ensure_ascii=False) if isinstance(답, dict) else 답


@pytest.fixture
def 세우기(monkeypatch):
    """모델, 상품 목록, 사진 받기를 가짜로 둔다. 부른 기록을 함께 돌려준다."""
    import db
    import services

    기록 = types.SimpleNamespace(받은_사진=[], 상품_조회=0, 고른_역할=[], llm=None)

    def 세우기(이름=None, 기한=None, 상품들=_상품들):
        기록.llm = 가짜LLM(이름, 기한)

        def get_llm(역할):
            기록.고른_역할.append(역할)
            return 기록.llm

        llm_모듈 = types.SimpleNamespace(
            LLMImage=types.SimpleNamespace,
            LLMRole=types.SimpleNamespace(VLM="vlm"),
            get_llm=get_llm,
        )
        monkeypatch.setitem(sys.modules, "services.llm", llm_모듈)
        monkeypatch.setattr(services, "llm", llm_모듈, raising=False)

        def list_products_meta():
            기록.상품_조회 += 1
            return 상품들

        상품_모듈 = types.SimpleNamespace(list_products_meta=list_products_meta)
        monkeypatch.setitem(sys.modules, "db.product_reader", 상품_모듈)
        monkeypatch.setattr(db, "product_reader", 상품_모듈, raising=False)

        async def load(주소):
            기록.받은_사진.append(주소)
            return b"jpeg:" + 주소.encode()

        monkeypatch.setattr(photo_loader, "load", load)
        return 기록

    return 세우기


# ── 면마다 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_제품명_면만_보내면_후보를_찾고_기한은_비운다(세우기):
    기록 = 세우기(이름=_이름_답)

    응답 = await recognize(_이름_사진, None, today=오늘)

    assert isinstance(응답, RecognizePhotosResponse) and 응답.stub is False
    assert [후보.product_id for 후보 in 응답.candidates] == ["neo-mui", "neo-glow"]
    assert 응답.candidates[0].confidence == 1.0
    assert (응답.expiry_date, 응답.pao_months, 응답.mfg_date) == (None, None, None)
    assert 응답.raw == {
        "readText": "LANEIGE NEO CUSHION MUI 15g",
        "brand": "LANEIGE", "brandEn": "LANEIGE", "brandKo": "라네즈",
        "productName": "NEO CUSHION MUI", "productNameKo": "네오 쿠션 뮤이",
    }
    assert 기록.받은_사진 == [_이름_사진]
    assert [호출["system"] for 호출 in 기록.llm.호출] == [NAME_FACE_SYSTEM]


@pytest.mark.asyncio
async def test_기한_면만_보내면_확인한_값을_채우고_후보는_없다(세우기):
    기록 = 세우기(기한=_기한_답)

    응답 = await recognize(None, _기한_사진, today=오늘)

    assert 응답.candidates == []
    assert (응답.expiry_date, 응답.pao_months, 응답.mfg_date) == ("2028-03-30", 12, "2026-03-31")
    assert 응답.raw == {
        "readText": "EXP 2028.03.30 MFG 2026.03.31 12M",
        "expiryDate": "2028-03-30", "expiryText": "EXP 2028.03.30",
        "mfgDate": "2026-03-31", "mfgText": "MFG 2026.03.31",
        "paoMonths": 12, "paoText": "12M",
        "dropped": {},
    }
    assert 기록.받은_사진 == [_기한_사진]
    assert [호출["system"] for 호출 in 기록.llm.호출] == [DATE_FACE_SYSTEM]
    # 제품명을 읽지 않으므로 상품 목록도 읽지 않는다
    assert 기록.상품_조회 == 0


@pytest.mark.asyncio
async def test_두_면을_함께_보내면_둘_다_읽는다(세우기):
    기록 = 세우기(이름=_이름_답, 기한=_기한_답)

    응답 = await recognize(_이름_사진, _기한_사진, today=오늘)

    assert 응답.candidates[0].product_id == "neo-mui"
    assert (응답.expiry_date, 응답.pao_months, 응답.mfg_date) == ("2028-03-30", 12, "2026-03-31")
    assert sorted(기록.받은_사진) == sorted([_이름_사진, _기한_사진])
    assert {호출["system"] for 호출 in 기록.llm.호출} == {NAME_FACE_SYSTEM, DATE_FACE_SYSTEM}
    # 제품명 면의 원본은 그대로 두고 기한 면의 원본을 옆에 붙인다. BE 가 따로 받은 원본을 합칠 때와 같다
    assert 응답.raw["readText"] == "LANEIGE NEO CUSHION MUI 15g"
    assert 응답.raw["expiry"]["readText"] == "EXP 2028.03.30 MFG 2026.03.31 12M"
    assert 응답.raw["expiry"]["expiryDate"] == "2028-03-30"


# ── 모델 호출 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_다듬은_사진을_면에_맞는_프롬프트와_함께_보낸다(세우기):
    기록 = 세우기(이름=_이름_답, 기한=_기한_답)

    await recognize(_이름_사진, _기한_사진, today=오늘)

    호출 = {호출["system"]: 호출 for 호출 in 기록.llm.호출}
    for 프롬프트, 주소 in ((NAME_FACE_SYSTEM, _이름_사진), (DATE_FACE_SYSTEM, _기한_사진)):
        [사진] = 호출[프롬프트]["images"]
        assert (사진.data, 사진.mime_type) == (b"jpeg:" + 주소.encode(), "image/jpeg")
        assert 호출[프롬프트]["timeout"] == photo_recognizer.MODEL_TIMEOUT_S
    # 표시 없이 찍힌 날짜를 가리려면 모델이 오늘을 알아야 한다
    assert "2026-11-22" in 호출[DATE_FACE_SYSTEM]["user"]


@pytest.mark.asyncio
async def test_모델을_주지_않으면_사진_역할의_모델을_쓴다(세우기):
    기록 = 세우기(이름=_이름_답)

    await recognize(_이름_사진, None, today=오늘)

    assert 기록.고른_역할 == ["vlm"]


@pytest.mark.asyncio
async def test_모델을_주면_그_모델을_쓴다(세우기):
    기록 = 세우기()
    다른 = 가짜LLM(이름=_이름_답)

    응답 = await recognize(_이름_사진, None, llm=다른, today=오늘)

    assert 응답.candidates[0].product_id == "neo-mui"
    assert 기록.고른_역할 == [] and len(다른.호출) == 1


@pytest.mark.asyncio
async def test_오늘을_주지_않으면_한국_시간의_오늘이다(세우기, monkeypatch):
    기록 = 세우기(기한=_기한_답)

    class 가짜시계:
        @staticmethod
        def now(시간대):
            # UTC 로는 21일 16시, 한국 시간으로는 22일 1시
            return datetime(2026, 11, 21, 16, 0, tzinfo=timezone.utc).astimezone(시간대)

    monkeypatch.setattr(photo_recognizer, "datetime", 가짜시계)

    await recognize(None, _기한_사진)

    assert "2026-11-22" in 기록.llm.호출[0]["user"]


# ── 모델의 답 ─────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("감싸기", [
    lambda 답: f"```json\n{답}\n```",
    lambda 답: f"사진에서 읽은 결과입니다.\n{답}\n이상입니다.",
    lambda 답: f"  \n{답}  ",
])
async def test_답_앞뒤에_다른_말이_붙어도_JSON을_꺼낸다(세우기, 감싸기):
    세우기(이름=감싸기(json.dumps(_이름_답, ensure_ascii=False)))

    응답 = await recognize(_이름_사진, None, today=오늘)

    assert 응답.candidates[0].product_id == "neo-mui"


@pytest.mark.asyncio
@pytest.mark.parametrize("답", ["", "글자를 읽을 수 없습니다.", "[1, 2]", '{"brand": "LANEIGE"', "} {", None])
async def test_답이_JSON_객체가_아니면_오류다(세우기, 답):
    """읽은 값이 없다는 답과 다르다. 빈 결과로 덮으면 읽을 글자가 없는 사진으로 보인다."""
    세우기(이름=답, 기한=답)

    with pytest.raises(RecognizeError):
        await recognize(_이름_사진, None, today=오늘)
    with pytest.raises(RecognizeError):
        await recognize(None, _기한_사진, today=오늘)


@pytest.mark.asyncio
async def test_모델_호출이_실패하면_예외를_그대로_올린다(세우기):
    세우기(이름=TimeoutError("시간 초과"), 기한=TimeoutError("시간 초과"))

    with pytest.raises(TimeoutError):
        await recognize(_이름_사진, None, today=오늘)
    with pytest.raises(TimeoutError):
        await recognize(None, _기한_사진, today=오늘)


@pytest.mark.asyncio
async def test_사진을_받지_못하면_모델을_부르지_않는다(세우기, monkeypatch):
    기록 = 세우기(이름=_이름_답)

    async def load(주소):
        raise PhotoError("사진을 받지 못했다 (응답 404)")

    monkeypatch.setattr(photo_loader, "load", load)

    with pytest.raises(PhotoError):
        await recognize(_이름_사진, None, today=오늘)
    assert 기록.llm.호출 == []


# ── 제품명 면 ─────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("답", [
    {"read_text": "", "brand": None, "brand_en": None, "brand_ko": None,
     "product_name": None, "product_name_ko": None},
    {},
])
async def test_읽은_글자가_없으면_후보_없이_돌려준다(세우기, 답):
    """오류가 아니다. 화면이 이름으로 찾기를 안내한다."""
    세우기(이름=답)

    응답 = await recognize(_이름_사진, None, today=오늘)

    assert 응답.candidates == []
    assert 응답.raw["readText"] == ""
    assert 응답.raw["productNameKo"] is None


@pytest.mark.asyncio
async def test_후보는_계약의_모양으로_나간다(세우기):
    세우기(이름={"brand": "NAMING", "brand_ko": "네이밍", "product_name_ko": "퍼펙테일 아이 펜슬"})

    응답 = await recognize(_이름_사진, None, today=오늘)

    assert 응답.model_dump(by_alias=True)["candidates"] == [{
        "productId": "naming",
        "name": "네이밍 퍼펙테일 아이 펜슬",
        # 상품에 브랜드가 없으면 빈 글자로 나간다
        "brand": "",
        "imageUrl": None,
        "confidence": 1.0,
    }]


@pytest.mark.asyncio
async def test_후보는_일치도가_높은_순으로_세_개까지다(세우기):
    크림들 = [
        {"id": f"c{번호}", "name": 이름, "brand": "AESTURA", "category": "skincare",
         "image_url": None, "price": None}
        for 번호, 이름 in enumerate([
            "아토베리어 365 크림 미스트", "아토베리어 365 크림", "아토베리어 365 하이드로 크림",
            "아토베리어 365 크림 80ml 기획", "아토베리어 365 로션",
        ])
    ]
    세우기(이름={"brand": "AESTURA", "product_name_ko": "아토베리어 365 크림"}, 상품들=크림들)

    응답 = await recognize(_이름_사진, None, today=오늘)

    assert len(응답.candidates) == 3
    assert 응답.candidates[0].product_id == "c1"
    일치도 = [후보.confidence for 후보 in 응답.candidates]
    assert 일치도 == sorted(일치도, reverse=True) and all(0 <= 값 <= 1 for 값 in 일치도)


# ── 기한 면 ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_확인을_통과하지_못한_값은_비우고_이유를_원본에_남긴다(세우기):
    세우기(기한={
        "read_text": "20270101 30ml",
        "expiry_date": None, "expiry_text": None,
        "mfg_date": "2027-01-01", "mfg_text": "제조 20270101",   # 오늘보다 뒤의 제조일
        "pao_months": 30, "pao_text": "30ml",                    # 용량을 개월 수로 읽었다
    })

    응답 = await recognize(None, _기한_사진, today=오늘)

    assert (응답.expiry_date, 응답.pao_months, 응답.mfg_date) == (None, None, None)
    # 모델이 읽은 값은 그대로 남는다. 사용자가 고친 값과 견줄 근거다
    assert (응답.raw["mfgDate"], 응답.raw["paoMonths"]) == ("2027-01-01", 30)
    assert 응답.raw["dropped"] == {
        "mfgDate": date_reading.미래_제조일,
        "paoMonths": date_reading.근거_없음,
    }


@pytest.mark.asyncio
async def test_연월만_찍힌_사용기한은_그_달_마지막_날로_나가고_원본은_읽은_대로_남는다(세우기):
    세우기(기한={"read_text": "EXP 03/2027", "expiry_date": "2027-03", "expiry_text": "EXP 03/2027"})

    응답 = await recognize(None, _기한_사진, today=오늘)

    assert 응답.expiry_date == "2027-03-31"
    assert 응답.raw["expiryDate"] == "2027-03"


@pytest.mark.asyncio
async def test_아무것도_읽지_못한_기한_면은_빈_값으로_돌려준다(세우기):
    세우기(기한={"read_text": "", "expiry_date": None, "mfg_date": None, "pao_months": None})

    응답 = await recognize(None, _기한_사진, today=오늘)

    assert (응답.expiry_date, 응답.pao_months, 응답.mfg_date) == (None, None, None)
    assert 응답.raw["dropped"] == {}


# ── 인식 원본 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_원본의_글은_길이를_자르고_양식에_없는_모양은_남기지_않는다(세우기):
    세우기(
        이름={**_이름_답, "read_text": "가" * 1000, "brand_en": ["LANEIGE"], "product_name": "  NEO  "},
        기한={**_기한_답, "read_text": "나" * 1000, "expiry_text": {"글자": "EXP"}},
    )

    응답 = await recognize(_이름_사진, _기한_사진, today=오늘)

    assert len(응답.raw["readText"]) == photo_recognizer.RAW_TEXT_MAX
    assert (응답.raw["brandEn"], 응답.raw["productName"]) == (None, "NEO")
    assert len(응답.raw["expiry"]["readText"]) == photo_recognizer.RAW_TEXT_MAX
    assert 응답.raw["expiry"]["expiryText"] is None


@pytest.mark.asyncio
async def test_원본에_사진_주소가_남지_않는다(세우기):
    세우기(이름=_이름_답, 기한=_기한_답)

    응답 = await recognize(_이름_사진, _기한_사진, today=오늘)

    남은 = json.dumps(응답.model_dump(by_alias=True), ensure_ascii=False)
    assert "secret" not in 남은 and "storage.example.com" not in 남은
