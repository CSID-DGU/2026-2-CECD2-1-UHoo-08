"""Gemini(Vertex AI) 호출의 설정을 본다. 실제로 부르지 않고 만든 설정만 확인한다."""
from types import SimpleNamespace

import pytest

genai = pytest.importorskip("google.genai")

from services.llm import vertex  # noqa: E402


class _가짜_클라이언트:
    def __init__(self, **값):
        self.만든_값 = 값
        self.보낸 = []
        self.models = SimpleNamespace(generate_content=self._보내기)

    def _보내기(self, **값):
        self.보낸.append(값)
        return SimpleNamespace(candidates=[], usage_metadata=None)


@pytest.fixture
def 클라이언트(monkeypatch):
    monkeypatch.setattr(genai, "Client", _가짜_클라이언트)
    chat = vertex.VertexChat("gemini-3.8-flash", project="p", location="global")
    return chat, chat._client


def test_기다리는_시간을_주지_않아도_끝없이_기다리지_않는다(클라이언트):
    _, 가짜 = 클라이언트
    옵션 = 가짜.만든_값["http_options"]
    assert 옵션.timeout == 600_000
    assert 옵션.retry_options.attempts == 3


def test_부르는_쪽이_준_시간이_먼저다(클라이언트):
    chat, 가짜 = 클라이언트
    chat.call("s", "u", timeout=5)
    assert 가짜.보낸[0]["config"].http_options.timeout == 5000
