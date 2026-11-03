"""광고 판별 1차 → 2차 연결. LLM 은 가짜로 바꿔 끼운다."""
import pytest

from services.ad_classifier import (
    LLM_TIMEOUT_S,
    LLM_VERSION,
    REASON_CODES,
    build_user_message,
    classify_post,
    parse_judgement,
)
from rules.ad_disclosure import RULE_VERSION

OWNED = [{"brand": "LOVEFLEUR", "aliases": ["러브플레르", "러플"]}]
UNSURE_CAPTION = "잠시후 자정부터 올리브영에서 립라이너 런칭이랑 동시에 오특 할인이에요\n17,000원 ⤏ 11,900원"


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.timeouts = []

    async def chat_json(self, system: str, user: str, timeout: float | None = None):
        self.calls.append(user)
        self.timeouts.append(timeout)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_1차에서_정해지면_LLM_을_부르지_않는다():
    llm = FakeLLM({"reason_code": "PERSONAL_REVIEW", "is_ad": False})
    result = await classify_post("#광고 신상 쿠션 리뷰", "u", llm=llm)

    assert result["is_ad"] is True
    assert result["labeled_by"] == "RULE"
    assert result["version"] == RULE_VERSION
    assert llm.calls == []


@pytest.mark.asyncio
async def test_1차가_넘긴_것만_LLM_이_판정한다():
    llm = FakeLLM({"reason_code": "OWN_BRAND", "is_ad": True,
                   "evidence": ["립라이너 런칭"], "reason": "본인 브랜드 신제품 런칭과 할인 안내"})
    result = await classify_post(UNSURE_CAPTION, "hyangxbabe", OWNED, llm=llm)

    assert result["is_ad"] is True
    assert result["labeled_by"] == "LLM"
    assert result["version"] == LLM_VERSION
    assert result["reason_code"] == "OWN_BRAND"
    assert result["evidence"] == ["립라이너 런칭"]
    assert any(h["rule"].startswith("commercial.") for h in result["rule_hits"])
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_근거가_부족하면_비광고다():
    llm = FakeLLM({"reason_code": "INSUFFICIENT_EVIDENCE", "is_ad": False, "evidence": [], "reason": "판단 근거 없음"})
    result = await classify_post(UNSURE_CAPTION, "u", llm=llm)

    assert result["is_ad"] is False
    assert result["reason_code"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    None,
    {"reason_code": "SPONSORED", "is_ad": True},
    ["OWN_BRAND"],
    {"reason_code": [], "is_ad": True},
    {"reason_code": {"code": "OWN_BRAND"}, "is_ad": True},
    {"reason_code": "OWN_BRAND", "is_ad": False},
    {"reason_code": "PERSONAL_REVIEW", "is_ad": True},
])
async def test_쓸_수_없는_응답이면_판정하지_않은_것으로_남긴다(response):
    result = await classify_post(UNSURE_CAPTION, "u", llm=FakeLLM(response))

    assert result["is_ad"] is None
    assert result["labeled_by"] == "LLM"
    assert result["reason_code"] is None


@pytest.mark.asyncio
async def test_LLM_호출에_시간_제한을_건다():
    llm = FakeLLM({"reason_code": "OWN_BRAND", "is_ad": True})
    await classify_post(UNSURE_CAPTION, "u", llm=llm)

    assert llm.timeouts == [LLM_TIMEOUT_S]


@pytest.mark.asyncio
async def test_LLM_호출이_실패하면_판정_불가로_덮지_않고_예외를_올린다():
    with pytest.raises(TimeoutError):
        await classify_post(UNSURE_CAPTION, "u", llm=FakeLLM(TimeoutError("timed out")))


def test_is_ad_를_빠뜨리면_판정_코드의_권장_결과를_쓴다():
    assert parse_judgement({"reason_code": "PRODUCT_GIVEAWAY"})["is_ad"] is True
    assert parse_judgement({"reason_code": "SALE_SHARING"})["is_ad"] is False


def test_판정_코드는_광고_다섯_비광고_넷이다():
    assert sum(REASON_CODES.values()) == 5
    assert len(REASON_CODES) == 9


def test_LLM_에_계정의_운영_브랜드와_1차_신호를_넘긴다():
    msg = build_user_message("캡션", "hyangxbabe", OWNED, [{"rule": "commercial.sale", "text": "오특"}])
    assert "LOVEFLEUR(러브플레르, 러플)" in msg
    assert "오특" in msg
    assert build_user_message("캡션", "u", None, []).count("없음") == 2
