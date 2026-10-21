"""stub 엔드포인트가 실제로 열려 있고 계약대로 응답하는지 본다.

BE 는 이 경로들을 보고 호출부를 만든다. 경로 이름이 하나 틀리면 BE 는
404 를 받는데, 그 시점은 AI 구현이 끝난 뒤라 원인을 찾는 데 시간이 든다.

app/main.py 전체가 아니라 v2 라우터만 올린다. 다른 라우터는 config 를
import 해서 API 키가 없으면 뜨지 않는다.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.internal.v2 import agent, router
from contracts.internal_api import RecognizePhotosResponse, TrendsResponse

app = FastAPI()
app.include_router(router, prefix="/internal")
client = TestClient(app)


@pytest.fixture(autouse=True)
def _실행하지_않는다(monkeypatch):
    """경로 테스트는 라우팅과 검증만 본다.

    TestClient 는 응답을 돌려준 뒤 배경 작업까지 실행한다. 추천 실행은 DB 를
    쓰므로 여기서 돌면 키가 필요해지고, CI 에서는 그것만으로 테스트가 깨진다.
    실행 자체는 test_agent_run.py 와 test_clarify.py 가 따로 본다.
    """
    async def 아무것도(req):
        return None

    monkeypatch.setattr(agent, "_실행", 아무것도)
    monkeypatch.setattr(agent, "_이어_돌리기", 아무것도)

# docs/internal-api.md 와 같은 목록이다.
POST_경로 = [
    ("/internal/agent/run/v2", {"jobId": "j1", "userId": "u1", "rawQuery": "여름 쿠션"}, 202),
    ("/internal/agent/clarify", {"jobId": "j1", "answer": "3만원"}, 202),
    ("/internal/products/recognize-photos", {"nameImage": "https://x/a.jpg"}, 200),
    ("/internal/home/run", {"userId": "u1", "kind": "ROUTINE"}, 202),
    ("/internal/bundle/swap",
     {"jobId": "j1", "bundleIndex": 0, "slot": 1, "productId": "p1"}, 200),
    ("/internal/feedback/apply", {"userId": "u1"}, 202),
]


@pytest.mark.parametrize("경로, 본문, 기대_코드", POST_경로, ids=lambda v: v if isinstance(v, str) else "")
def test_경로가_열려_있다(경로, 본문, 기대_코드):
    응답 = client.post(경로, json=본문)
    assert 응답.status_code == 기대_코드, 응답.text


def test_트렌드는_GET이다():
    응답 = client.get("/internal/trends")
    assert 응답.status_code == 200
    TrendsResponse.model_validate(응답.json())


@pytest.mark.parametrize("경로, 본문, _", POST_경로, ids=lambda v: v if isinstance(v, str) else "")
def test_아직_stub임을_알린다(경로, 본문, _):
    """표시가 없으면 빈 결과를 정상으로 읽고 다음 작업으로 넘어간다."""
    assert client.post(경로, json=본문).json()["stub"] is True


def test_잘못된_요청은_422다():
    """BE 가 옛 필드 이름으로 보내면 조용히 무시되지 않는다."""
    응답 = client.post("/internal/agent/run/v2",
                       json={"jobId": "j1", "userId": "u1", "baseProductId": "p1"})
    assert 응답.status_code == 422


def test_인식_응답이_계약과_같다():
    응답 = client.post("/internal/products/recognize-photos",
                       json={"nameImage": "https://x/a.jpg"})
    결과 = RecognizePhotosResponse.model_validate(응답.json())
    assert 결과.candidates == [] and 결과.expiry_date is None


_추천_경로 = [
    ("/internal/agent/run/v2", {"jobId": "j1", "userId": "u1", "rawQuery": "여름 쿠션"}, "_실행"),
    ("/internal/agent/clarify", {"jobId": "j1", "answer": "3만원"}, "_이어_돌리기"),
]


@pytest.fixture
def 실행_기록(monkeypatch):
    """배경 작업이 실제로 걸렸는지 남긴다."""
    걸린: list[str] = []

    for 이름 in ("_실행", "_이어_돌리기"):
        async def 기록(req, 이름=이름):
            걸린.append(이름)

        monkeypatch.setattr(agent, 이름, 기록)
    return 걸린


@pytest.mark.parametrize("경로, 본문, _", _추천_경로, ids=["run_v2", "clarify"])
def test_stub이면_실행을_걸지_않는다(경로, 본문, _, 실행_기록, monkeypatch):
    """돌리면 빈 결과로 완료되어 '추천 없음' 으로 읽힌다. job 은 PENDING 으로
    두고 멈춘 job 정리 배치가 FAILED 로 바꾸게 한다."""
    monkeypatch.setattr(agent, "_결과를_만들_수_있나", lambda: False)

    assert client.post(경로, json=본문).json()["stub"] is True
    assert 실행_기록 == []


@pytest.mark.parametrize("경로, 본문, 실행", _추천_경로, ids=["run_v2", "clarify"])
def test_결과를_만들_수_있으면_실행을_건다(경로, 본문, 실행, 실행_기록, monkeypatch):
    monkeypatch.setattr(agent, "_결과를_만들_수_있나", lambda: True)

    assert client.post(경로, json=본문).json()["stub"] is False
    assert 실행_기록 == [실행]
