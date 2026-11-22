"""사진 인식 프롬프트와 그 답을 읽는 규칙이 같은 양식을 쓰는지 본다.

프롬프트의 키 이름이 규칙이 읽는 키와 하나만 달라도 그 값은 조용히 비어서 나간다.
"""
from datetime import date

import pytest

from prompts.photo_recognize import (
    DATE_FACE_SYSTEM,
    EXPIRY_MARKS,
    NAME_FACE_SYSTEM,
    date_face_user,
)
from rules import date_reading, name_matching

오늘 = date(2026, 11, 22)


@pytest.mark.parametrize("키", ["read_text", "brand", "brand_en", "brand_ko", "product_name", "product_name_ko"])
def test_제품명_면_프롬프트가_규칙이_읽는_키를_모두_받는다(키):
    assert f'"{키}"' in NAME_FACE_SYSTEM


@pytest.mark.parametrize("키", [
    "read_text", "expiry_date", "expiry_text", "mfg_date", "mfg_text", "pao_months", "pao_text",
])
def test_기한_면_프롬프트가_규칙이_읽는_키를_모두_받는다(키):
    assert f'"{키}"' in DATE_FACE_SYSTEM


def test_프롬프트의_예시_답을_규칙이_읽는다():
    """프롬프트에 적은 표기 예시대로 답하면 후보와 기한이 나온다."""
    상품 = [{"id": "p1", "brand": "LANEIGE", "name": "라네즈 네오 쿠션 매트"}]
    후보 = name_matching.match({
        "brand": "LANEIGE", "brand_en": "LANEIGE", "brand_ko": "라네즈",
        "product_name": "NEO CUSHION MATTE", "product_name_ko": "네오 쿠션 매트",
    }, 상품)
    assert 후보[0].confidence == 1.0

    읽은 = date_reading.verify({
        "expiry_date": "2027-03", "expiry_text": "EXP 03/2027",
        "mfg_date": "2026-03-31", "mfg_text": "제조 20260331",
        "pao_months": 12, "pao_text": "12M",
    }, 오늘)
    assert (읽은.expiry_date, 읽은.mfg_date, 읽은.pao_months) == ("2027-03-31", "2026-03-31", 12)


@pytest.mark.parametrize("표시", EXPIRY_MARKS)
def test_프롬프트가_알려_준_사용기한_표시를_규칙도_알아본다(표시):
    """모델이 표시와 함께 읽은 지난 날짜를 규칙이 표시가 없다며 버리면 안 된다."""
    assert 표시 in DATE_FACE_SYSTEM
    읽은 = date_reading.verify(
        {"expiry_date": "2025-01-31", "expiry_text": f"{표시} 2025.01.31"}, 오늘,
    )
    assert 읽은.expiry_date == "2025-01-31"


def test_기한_면에는_오늘을_함께_알려_준다():
    assert "2026-11-22" in date_face_user(오늘)


@pytest.mark.parametrize("프롬프트", [NAME_FACE_SYSTEM, DATE_FACE_SYSTEM], ids=["제품명 면", "기한 면"])
def test_읽지_못한_값은_비우라고_알린다(프롬프트):
    assert "null" in 프롬프트 and "JSON" in 프롬프트
    # f-string 으로 만든 프롬프트에 중괄호가 겹쳐 남지 않았다
    assert "{{" not in 프롬프트 and "}}" not in 프롬프트
