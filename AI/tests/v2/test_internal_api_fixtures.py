"""내부 API 예시 JSON 이 AI 계약을 통과하는지 본다.

BE 는 같은 파일을 자기 DTO 와 비교한다(AiContractTest). 계약을 바꾸면 여기서
예시를 고치라고 걸리고, 예시를 고치면 BE 테스트가 DTO 를 고치라고 걸린다.
"""
import inspect
import json
import pathlib

import pytest

from contracts import internal_api
from contracts.internal_api import (
    Accepted,
    AgentClarifyRequest,
    AgentRunV2Request,
    CompatibilityCheckRequest,
    CompatibilityCheckResponse,
    FeedbackApplyRequest,
    HomeRunRequest,
    RecognizePhotosRequest,
    RecognizePhotosResponse,
    WireModel,
)

FIXTURES = pathlib.Path(__file__).resolve().parents[3] / "docs" / "internal-api-fixtures"

모델 = {
    "accepted.response": Accepted,
    "agent-run-v2.request": AgentRunV2Request,
    "agent-clarify.request": AgentClarifyRequest,
    "recognize-photos.request": RecognizePhotosRequest,
    "recognize-photos.response": RecognizePhotosResponse,
    "home-run.request": HomeRunRequest,
    "feedback-apply.request": FeedbackApplyRequest,
    "compatibility-check.request": CompatibilityCheckRequest,
    "compatibility-check.response": CompatibilityCheckResponse,
}


def _읽기(이름: str) -> dict:
    return json.loads((FIXTURES / f"{이름}.json").read_text(encoding="utf-8"))


def test_예시_파일과_모델이_짝이_맞다():
    파일 = {경로.stem for 경로 in FIXTURES.glob("*.json")}
    assert 파일 == set(모델), f"모델만 있음: {set(모델) - 파일}, 파일만 있음: {파일 - set(모델)}"


def test_요청과_응답_계약마다_예시가_있다():
    """새 계약에 예시를 빠뜨리면 BE 와 비교할 자리가 없다."""
    계약 = {
        값 for 이름, 값 in vars(internal_api).items()
        if inspect.isclass(값) and issubclass(값, WireModel)
        and (이름.endswith(("Request", "Response")) or 값 is Accepted)
    }
    assert 계약 - set(모델.values()) == set()


@pytest.mark.parametrize("이름", sorted(모델))
def test_예시가_계약을_통과한다(이름):
    모델[이름].model_validate(_읽기(이름))
