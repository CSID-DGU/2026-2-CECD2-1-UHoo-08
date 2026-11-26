"""후보 모델을 역할에 바꿔 끼우는 동작을 본다. LLM 은 부르지 않는다."""
from unittest.mock import patch

import pytest

from eval.model_candidates import use_candidate


@pytest.fixture
def 설정(monkeypatch):
    """역할 설정을 비우고 후보가 가리키는 값을 가짜로 채운다. 끝나면 원래대로 돌아간다."""
    from services.llm import client

    값들 = {
        "LLM_NORMALIZE_MODEL": "",
        "LLM_NORMALIZE_BASE_URL": "",
        "LLM_NORMALIZE_API_KEY": "",
        "LLM_COMPOSE_MODEL": "",
        "QWEN_TEXT_MODEL": "qwen-plus",
        "QWEN_TEXT_BASE_URL": "https://dashscope.example/v1",
        "DASHSCOPE_API_KEY": "dashscope-key",
        "ANTHROPIC_API_KEY": "anthropic-key",
        "GOOGLE_CLOUD_PROJECT": "my-project",
        "QWEN_GATEWAY_BASE_URL": "https://gateway.example/v1",
        "QWEN_GATEWAY_API_KEY": "gateway-key",
    }
    for 이름, 값 in 값들.items():
        monkeypatch.setattr(client.settings, 이름, 값)
    client.get_llm.cache_clear()
    yield client.settings
    client.get_llm.cache_clear()


@pytest.mark.parametrize("model, 부르는_곳, 기대", [
    ("qwen-plus", "DashScope", ("qwen-plus", "https://dashscope.example/v1", "dashscope-key")),
    ("qwen3.8-flash", "동국 AI Gateway", ("qwen3.8-flash", "https://gateway.example/v1", "gateway-key")),
    ("claude-haiku-5-5", "Anthropic API", ("claude-haiku-5-5", "https://api.anthropic.com", "anthropic-key")),
    # 주소가 빈 Gemini 는 Vertex AI 로 간다
    ("gemini-3.8-flash", "Vertex AI", ("gemini-3.8-flash", "", "")),
])
def test_끼운_동안_역할이_후보의_모델과_주소와_키를_쓴다(설정, model, 부르는_곳, 기대):
    from services.llm.client import LLMRole, _설정

    with use_candidate(LLMRole.NORMALIZE, model) as 후보:
        assert 후보.place == 부르는_곳
        assert _설정(LLMRole.NORMALIZE) == 기대


def test_범위를_벗어나면_원래_설정으로_돌아온다(설정):
    from services.llm.client import LLMRole

    with use_candidate(LLMRole.NORMALIZE, "qwen3.8-flash"):
        pass

    assert (설정.LLM_NORMALIZE_MODEL, 설정.LLM_NORMALIZE_BASE_URL, 설정.LLM_NORMALIZE_API_KEY) == ("", "", "")


def test_안에서_오류가_나도_원래_설정으로_돌아온다(설정):
    from services.llm.client import LLMRole

    with pytest.raises(RuntimeError):
        with use_candidate(LLMRole.NORMALIZE, "claude-haiku-5-5"):
            raise RuntimeError("boom")

    assert 설정.LLM_NORMALIZE_MODEL == ""


def test_다른_역할의_설정은_건드리지_않는다(설정):
    from services.llm.client import LLMRole

    with use_candidate(LLMRole.NORMALIZE, "claude-haiku-5-5"):
        assert 설정.LLM_COMPOSE_MODEL == ""


@patch("anthropic.Anthropic")
@patch("services.llm.client.OpenAI")
def test_끼울_때와_뺄_때_클라이언트를_새로_만든다(_openai, _anthropic, 설정):
    """역할마다 클라이언트를 하나 만들어 두고 다시 쓴다. 비우지 않으면 예전 모델을 계속 부른다."""
    from services.llm.client import LLMRole, get_llm

    def 부르는_방법() -> str:
        return type(get_llm(LLMRole.NORMALIZE)._호출).__name__

    assert 부르는_방법() == "_OpenAIChat"
    with use_candidate(LLMRole.NORMALIZE, "claude-haiku-5-5"):
        assert 부르는_방법() == "ClaudeChat"
    assert 부르는_방법() == "_OpenAIChat"


def test_후보가_가리키는_설정이_비어_있으면_끼우지_않고_멈춘다(설정, monkeypatch):
    """빈 키로 부르면 인증 오류가 문제 수만큼 쌓인 뒤에야 알게 된다."""
    from services.llm.client import LLMRole

    monkeypatch.setattr(설정, "QWEN_GATEWAY_API_KEY", "")

    with pytest.raises(RuntimeError, match="QWEN_GATEWAY_API_KEY"):
        with use_candidate(LLMRole.NORMALIZE, "qwen3.8-flash"):
            pass
    assert 설정.LLM_NORMALIZE_MODEL == ""


def test_후보에_없는_모델은_끼우지_않는다(설정):
    from services.llm.client import LLMRole

    with pytest.raises(KeyError, match="qwen3.8-max"):
        with use_candidate(LLMRole.NORMALIZE, "qwen3.8-max"):
            pass
