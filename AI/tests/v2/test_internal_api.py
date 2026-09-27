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
    assert set(나감) == {"jobId", "userId", "rawQuery", "basis", "targetProfile", "parentJobId"}


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
        lambda: FeedbackApplyRequest(user_id=""),
    ],
)
def test_빈_문자열을_거부한다(만들기):
    with pytest.raises(ValidationError):
        만들기()


def test_모르는_필드를_거부한다():
    """BE 가 옛 이름으로 보내면 조용히 무시되는 대신 400 이 난다."""
    with pytest.raises(ValidationError):
        AgentRunV2Request(job_id="j1", user_id="u1", raw_query="q", baseProductId="p1")


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
