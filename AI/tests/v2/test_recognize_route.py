"""사진 인식 경로가 결과와 실패를 BE 에 어떻게 알리는지 본다.

실패를 빈 결과로 돌려주면 BE 는 읽을 글자가 없는 사진으로 읽고 이름으로 찾으라고
안내한다. 사진 주소에는 접근 토큰이 붙을 수 있어 로그와 응답에 남으면 안 된다.
"""
import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.internal.v2 import router
from contracts.internal_api import ProductCandidate, RecognizePhotosResponse
from services import photo_recognizer
from services.photo_loader import PhotoError
from services.photo_recognizer import RecognizeError

app = FastAPI()
app.include_router(router, prefix="/internal")
client = TestClient(app)

_경로 = "/internal/products/recognize-photos"
_이름_사진 = "https://storage.example.com/user-product-photos/u1/name.jpg?token=secret"
_기한_사진 = "https://storage.example.com/user-product-photos/u1/date.jpg?token=secret"
_예시 = Path(__file__).resolve().parents[3] / "docs" / "internal-api-fixtures" / "recognize-photos.response.json"

_읽은_결과 = RecognizePhotosResponse(
    candidates=[ProductCandidate(
        product_id="p1", name="라네즈 네오 쿠션 뮤이", brand="LANEIGE",
        image_url="https://img.example.com/p1.jpg", confidence=0.93,
    )],
    expiry_date="2028-03-30",
    pao_months=12,
    mfg_date="2026-03-31",
    raw={"readText": "LANEIGE NEO CUSHION MUI"},
)


@pytest.fixture
def 인식(monkeypatch):
    """인식 서비스를 가짜로 둔다. 결과를 주면 돌려주고 예외를 주면 던진다. 받은 값을 남긴다."""
    받은: list[tuple] = []

    def 세우기(결과):
        async def recognize(name_image, date_image):
            받은.append((name_image, date_image))
            if isinstance(결과, Exception):
                raise 결과
            return 결과

        monkeypatch.setattr(photo_recognizer, "recognize", recognize)
        return 받은

    return 세우기


def test_인식_결과를_계약의_모양으로_돌려준다(인식):
    인식(_읽은_결과)

    응답 = client.post(_경로, json={"nameImage": _이름_사진, "dateImage": _기한_사진})

    assert 응답.status_code == 200
    assert 응답.json() == {
        "candidates": [{
            "productId": "p1", "name": "라네즈 네오 쿠션 뮤이", "brand": "LANEIGE",
            "imageUrl": "https://img.example.com/p1.jpg", "confidence": 0.93,
        }],
        "expiryDate": "2028-03-30",
        "paoMonths": 12,
        "mfgDate": "2026-03-31",
        "raw": {"readText": "LANEIGE NEO CUSHION MUI"},
        "stub": False,
    }
    # BE 와 함께 보는 예시와 같은 키다
    assert set(응답.json()) == set(json.loads(_예시.read_text(encoding="utf-8")))


@pytest.mark.parametrize("본문, 기대", [
    ({"nameImage": _이름_사진}, (_이름_사진, None)),
    ({"nameImage": None, "dateImage": _기한_사진}, (None, _기한_사진)),
    ({"nameImage": _이름_사진, "dateImage": _기한_사진}, (_이름_사진, _기한_사진)),
])
def test_받은_면의_사진_주소만_넘긴다(인식, 본문, 기대):
    받은 = 인식(RecognizePhotosResponse())

    assert client.post(_경로, json=본문).status_code == 200
    assert 받은 == [기대]


def test_읽은_것이_없어도_오류가_아니고_stub도_아니다(인식):
    인식(RecognizePhotosResponse())

    응답 = client.post(_경로, json={"nameImage": _이름_사진})

    assert 응답.status_code == 200
    assert 응답.json() == {
        "candidates": [], "expiryDate": None, "paoMonths": None, "mfgDate": None,
        "raw": {}, "stub": False,
    }


@pytest.mark.parametrize("실패, 코드, 알림", [
    (PhotoError("사진을 받지 못했다 (응답 404)"), 422, "사진을 받지 못했다 (응답 404)"),
    (PhotoError("사진을 열지 못했다 (UnidentifiedImageError)"), 422, "사진을 열지 못했다 (UnidentifiedImageError)"),
    (RecognizeError("사진 모델의 답을 읽지 못했다"), 502, "사진 모델의 답을 읽지 못했다"),
    (TimeoutError("모델이 답하지 않았다"), 500, "사진을 인식하지 못했다"),
    (RuntimeError("상품 목록을 읽지 못했다"), 500, "사진을 인식하지 못했다"),
], ids=["사진을 받지 못함", "사진을 열지 못함", "모델의 답을 쓸 수 없음", "모델 호출 실패", "그 밖의 실패"])
def test_실패는_빈_결과가_아니라_상태_코드로_알린다(인식, 실패, 코드, 알림):
    인식(실패)

    응답 = client.post(_경로, json={"nameImage": _이름_사진})

    assert 응답.status_code == 코드
    assert 응답.json() == {"detail": 알림}


@pytest.mark.parametrize("실패", [
    PhotoError("사진을 받지 못했다 (응답 404)"),
    RecognizeError("사진 모델의 답을 읽지 못했다"),
    RuntimeError("모델 호출 실패"),
], ids=["사진", "모델의 답", "그 밖"])
def test_실패해도_사진_주소는_응답과_로그에_남지_않는다(인식, 실패, caplog):
    인식(실패)

    with caplog.at_level(logging.DEBUG):
        응답 = client.post(_경로, json={"nameImage": _이름_사진, "dateImage": _기한_사진})

    assert 응답.status_code >= 400
    for 남은 in (응답.text, caplog.text):
        assert "secret" not in 남은 and "storage.example.com" not in 남은
    # 어느 면을 읽다가 실패했는지는 남긴다
    assert "제품명 면, 기한 면" in caplog.text


@pytest.mark.parametrize("본문, 면", [
    ({"nameImage": _이름_사진}, "(제품명 면)"),
    ({"dateImage": _기한_사진}, "(기한 면)"),
])
def test_실패_로그에_읽던_면을_남긴다(인식, 본문, 면, caplog):
    인식(RecognizeError("사진 모델의 답을 읽지 못했다"))

    with caplog.at_level(logging.WARNING):
        client.post(_경로, json=본문)

    assert 면 in caplog.text


def test_예상하지_못한_실패는_스택과_함께_남긴다(인식, caplog):
    인식(RuntimeError("모델 호출 실패"))

    with caplog.at_level(logging.ERROR):
        client.post(_경로, json={"nameImage": _이름_사진})

    [기록] = [기록 for 기록 in caplog.records if 기록.levelno == logging.ERROR]
    assert 기록.exc_info is not None and "모델 호출 실패" in caplog.text
