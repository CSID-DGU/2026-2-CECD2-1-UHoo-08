"""BE 와 주고받는 계약이 지켜야 할 성질.

BE 는 이 스키마를 보고 Java DTO 를 만든다. 이름이 하나만 달라도 값이 조용히
빠지고, 빠진 자리는 기본값으로 채워져 정상처럼 보인다.
"""
import pytest
from pydantic import ValidationError

from contracts.internal_api import (
    AgentClarifyRequest,
    AgentRunV2Request,
    BundleSwapRequest,
    CompatibilityCheckRequest,
    CompatibilityCheckResponse,
    FeedbackApplyRequest,
    HomeKind,
    HomeRunRequest,
    JobStatus,
    RecognizePhotosRequest,
    RecognizePhotosResponse,
)


def test_BE로_나갈_때_camelCase가_된다():
    요청 = AgentRunV2Request(job_id="j1", user_id="u1", raw_query="여름 쿠션")
    나감 = 요청.model_dump(mode="json", by_alias=True)
    assert set(나감) == {
        "jobId", "userId", "rawQuery", "baseProductId", "basis", "targetProfile", "parentJobId",
    }


def test_job_상태값이_컬럼_길이에_들어간다():
    """recommendation_jobs.status 는 VARCHAR(20) 이다. 넘으면 저장 시점에
    잘리거나 터지는데, 그때는 어느 상태였는지도 남지 않는다."""
    너무_긴 = [s.value for s in JobStatus if len(s.value) > 20]
    assert 너무_긴 == []


def test_되묻기는_실패가_아니다():
    """BE 가 이 상태를 실패로 묶으면 답을 기다리는 job 이 정리된다."""
    assert JobStatus.NEEDS_CLARIFICATION not in (JobStatus.FAILED, JobStatus.COMPLETED)


@pytest.mark.parametrize(
    "만들기",
    [
        lambda: AgentRunV2Request(job_id="", user_id="u1", raw_query="q"),
        lambda: AgentRunV2Request(job_id="j1", user_id="u1", raw_query=""),
        lambda: AgentClarifyRequest(job_id="j1", answer=""),
        lambda: RecognizePhotosRequest(name_image=""),
        lambda: RecognizePhotosRequest(date_image=""),
        lambda: RecognizePhotosRequest(name_image="", date_image="https://x/d.jpg"),
        lambda: FeedbackApplyRequest(user_id=""),
        lambda: CompatibilityCheckRequest(user_id="", product_id="p1"),
        lambda: CompatibilityCheckRequest(user_id="u1", product_id=""),
    ],
)
def test_빈_문자열을_거부한다(만들기):
    with pytest.raises(ValidationError):
        만들기()


@pytest.mark.parametrize(
    "본문",
    [
        {"nameImage": "https://x/n.jpg"},
        {"dateImage": "https://x/d.jpg"},
        {"nameImage": "https://x/n.jpg", "dateImage": "https://x/d.jpg"},
        # BE 는 비어 있는 값도 null 로 함께 보낸다
        {"nameImage": None, "dateImage": "https://x/d.jpg"},
        {"nameImage": "https://x/n.jpg", "dateImage": None},
    ],
)
def test_사진은_한_면만_있어도_받는다(본문):
    RecognizePhotosRequest.model_validate(본문)


@pytest.mark.parametrize("본문", [{}, {"nameImage": None, "dateImage": None}])
def test_사진이_하나도_없으면_거부한다(본문):
    with pytest.raises(ValidationError):
        RecognizePhotosRequest.model_validate(본문)


def test_모르는_필드를_거부한다():
    """BE 가 옛 이름으로 보내면 조용히 무시되는 대신 400 이 난다."""
    with pytest.raises(ValidationError):
        AgentRunV2Request(job_id="j1", user_id="u1", raw_query="q", productCode="p1")


@pytest.mark.parametrize("값", [
    {"rawQuery": "여름 쿠션"},
    {"baseProductId": "p1"},
    {"rawQuery": None, "baseProductId": "p1"},
    {"rawQuery": "이 제품 어때", "baseProductId": "p1"},
])
def test_질의나_기준_상품_중_하나면_받는다(값):
    AgentRunV2Request.model_validate({"jobId": "j1", "userId": "u1", **값})


@pytest.mark.parametrize("값", [
    {},
    {"rawQuery": None, "baseProductId": None},
    {"rawQuery": ""},
    {"baseProductId": ""},
    {"rawQuery": "여름 쿠션", "baseProductId": ""},
])
def test_질의와_기준_상품이_모두_없거나_빈_값이면_거부한다(값):
    with pytest.raises(ValidationError):
        AgentRunV2Request.model_validate({"jobId": "j1", "userId": "u1", **값})


def test_궁합_요청은_camelCase로_받는다():
    요청 = CompatibilityCheckRequest.model_validate({"userId": "u1", "productId": "p1"})
    assert 요청.model_dump(by_alias=True) == {"userId": "u1", "productId": "p1"}


def test_궁합_응답을_왕복한다():
    본문 = {
        "level": "SEPARATE",
        "pairs": [{
            "userProductId": "up1",
            "ingredientA": "레티놀",
            "ingredientB": "AHA",
            "level": "SEPARATE",
            "advice": "시간을 나눠 쓰세요",
            "schedule": "레티놀은 저녁에 쓰세요",
        }],
        "stub": False,
    }
    결과 = CompatibilityCheckResponse.model_validate(본문)
    assert 결과.model_dump(mode="json", by_alias=True) == 본문


def test_궁합_안내는_비어_있어도_된다():
    쌍 = {"userProductId": "up1", "ingredientA": "레티놀", "ingredientB": "AHA", "level": "AVOID"}
    결과 = CompatibilityCheckResponse.model_validate({"level": "AVOID", "pairs": [쌍]})
    assert 결과.pairs[0].advice is None and 결과.pairs[0].schedule is None


@pytest.mark.parametrize("본문", [
    {},
    {"level": "GOOD"},
    {"level": "OK", "pairs": [{"userProductId": "up1", "ingredientA": "레티놀",
                               "ingredientB": "AHA", "level": "GOOD"}]},
    {"level": "AVOID", "pairs": [{"userProductId": "up1", "ingredientA": "",
                                  "ingredientB": "AHA", "level": "AVOID"}]},
])
def test_잘못된_궁합_응답을_거부한다(본문):
    with pytest.raises(ValidationError):
        CompatibilityCheckResponse.model_validate(본문)


def test_홈은_두_종류만_받는다():
    assert {k.value for k in HomeKind} == {"ROUTINE", "ENV"}
    with pytest.raises(ValidationError):
        HomeRunRequest(user_id="u1", kind="TREND")


def test_세트_교체_위치는_음수가_될_수_없다():
    with pytest.raises(ValidationError):
        BundleSwapRequest(job_id="j1", bundle_index=-1, slot=0, product_id="p1")


def test_인식_결과는_모르는_값을_비워_둔다():
    """추측해서 채우면 사용자가 확인하지 않고 넘기고, 잘못된 기한이
    소진 알림으로 이어진다."""
    응답 = RecognizePhotosResponse()
    assert 응답.candidates == []
    assert 응답.expiry_date is None
    assert 응답.pao_months is None
