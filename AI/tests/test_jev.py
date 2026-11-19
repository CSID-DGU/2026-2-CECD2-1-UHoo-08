"""Jev 호출을 본다. 실제 서버 대신 httpx 의 가짜 전송을 쓴다."""
import httpx
import pytest

from services.llm import jev
from services.llm.usage import collect_calls


@pytest.fixture
def 가짜_서버(monkeypatch):
    def 끼우기(처리):
        monkeypatch.setattr(jev, "_클라이언트", httpx.AsyncClient(
            base_url="https://jev.test", transport=httpx.MockTransport(처리),
        ))
    return 끼우기


_답 = {
    "model": "jev-1.14.0",
    "answers": {"vague": {"type": "noul", "noul": 0.7}},
    "usage": {"input_tokens": 300, "output_tokens": 40},
}


@pytest.mark.asyncio
async def test_질문_이름별_답을_돌려주고_호출을_기록한다(가짜_서버):
    받은 = []

    def 처리(request: httpx.Request) -> httpx.Response:
        받은.append(request)
        return httpx.Response(200, json=_답)

    가짜_서버(처리)
    with collect_calls() as calls:
        답 = await jev.ask("추천해줘", {"vague": jev.noul("막연한가?")})

    assert 답 == {"vague": {"type": "noul", "noul": 0.7}}
    assert 받은[0].url.path == "/v1/systemone"
    assert (calls[0].role, calls[0].model) == ("jev", "jev-1.14.0")
    assert (calls[0].input_tokens, calls[0].output_tokens) == (300, 40)


@pytest.mark.asyncio
async def test_잠깐의_오류는_한_번_다시_보낸다(가짜_서버, monkeypatch):
    async def 안_기다림(_):
        return None

    monkeypatch.setattr(jev.asyncio, "sleep", 안_기다림)
    상태 = iter([503, 200])
    가짜_서버(lambda request: httpx.Response(next(상태), json=_답))

    답 = await jev.ask("추천해줘", {"vague": jev.noul("막연한가?")})
    assert 답["vague"]["noul"] == 0.7


@pytest.mark.asyncio
async def test_실패하면_기록을_남기고_예외를_올린다(가짜_서버):
    가짜_서버(lambda request: httpx.Response(400, json={"detail": "bad"}))

    with collect_calls() as calls:
        with pytest.raises(httpx.HTTPStatusError):
            await jev.ask("추천해줘", {"vague": jev.noul("막연한가?")})

    assert len(calls) == 1 and calls[0].ok is False


def test_질문을_만드는_함수():
    assert jev.choice("종류?", {"A": "가", "B": "나"}) == {
        "type": "choice", "instructions": "종류?", "criteria": {"A": "가", "B": "나"},
    }
    assert jev.noul("맞나?") == {"type": "noul", "instructions": "맞나?"}


@pytest.mark.asyncio
async def test_취소되어도_기록을_남기고_취소를_올린다(가짜_서버):
    import asyncio

    async def 끝나지_않는_처리(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(10)
        return httpx.Response(200, json=_답)

    가짜_서버(끝나지_않는_처리)
    with collect_calls() as calls:
        작업 = asyncio.create_task(jev.ask("추천해줘", {"vague": jev.noul("막연한가?")}))
        await asyncio.sleep(0.01)
        작업.cancel()
        with pytest.raises(asyncio.CancelledError):
            await 작업

    assert len(calls) == 1 and calls[0].ok is False


@pytest.mark.asyncio
async def test_답이_없는_응답은_실패로_한_번_기록하고_예외를_올린다(가짜_서버):
    가짜_서버(lambda request: httpx.Response(200, json={"usage": {}}))

    with collect_calls() as calls:
        with pytest.raises(ValueError):
            await jev.ask("추천해줘", {"vague": jev.noul("막연한가?")})

    assert len(calls) == 1 and calls[0].ok is False


@pytest.mark.asyncio
async def test_사용량을_읽지_못해도_답은_돌려주고_토큰은_0으로_기록한다(가짜_서버):
    가짜_서버(lambda request: httpx.Response(200, json={**_답, "usage": "unknown"}))

    with collect_calls() as calls:
        답 = await jev.ask("추천해줘", {"vague": jev.noul("막연한가?")})

    assert 답["vague"]["noul"] == 0.7
    assert len(calls) == 1 and calls[0].ok is True
    assert (calls[0].input_tokens, calls[0].output_tokens) == (0, 0)
