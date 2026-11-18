"""LLM 클라이언트 단위 테스트. OpenAI SDK 호출 모킹."""
from unittest.mock import MagicMock, patch

import pytest


class TestLLMClient:
    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    async def test_chat_returns_content(self, mock_openai_cls):
        from services.llm.client import LLMClient

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="hello"))]
        )
        mock_openai_cls.return_value = client_mock

        c = LLMClient(model="m", base_url="http://x", api_key="k")
        out = await c.chat(system="s", user="u")
        assert out == "hello"

    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    async def test_chat_json_parses(self, mock_openai_cls):
        from services.llm.client import LLMClient

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"a": 1}'))]
        )
        mock_openai_cls.return_value = client_mock

        c = LLMClient(model="m", base_url="http://x", api_key="k")
        out = await c.chat_json(system="s", user="u")
        assert out == {"a": 1}

    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    async def test_chat_json_handles_code_fence(self, mock_openai_cls):
        from services.llm.client import LLMClient

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='```json\n{"a": 1}\n```'))]
        )
        mock_openai_cls.return_value = client_mock

        c = LLMClient(model="m", base_url="http://x", api_key="k")
        out = await c.chat_json(system="s", user="u")
        assert out == {"a": 1}

    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    async def test_chat_json_returns_none_on_parse_error(self, mock_openai_cls):
        from services.llm.client import LLMClient

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json"))]
        )
        mock_openai_cls.return_value = client_mock

        c = LLMClient(model="m", base_url="http://x", api_key="k")
        out = await c.chat_json(system="s", user="u")
        assert out is None

class TestLLMCallRecord:
    """호출마다 모델, 토큰 수, 걸린 시간이 기록되는지 본다."""

    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    async def test_records_model_tokens_and_time(self, mock_openai_cls):
        from services.llm.client import LLMClient, LLMRole
        from services.llm.usage import collect_calls

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="hello"))],
            usage=MagicMock(prompt_tokens=120, completion_tokens=30),
        )
        mock_openai_cls.return_value = client_mock

        c = LLMClient(model="m", base_url="http://x", api_key="k", role=LLMRole.NORMALIZE)
        with collect_calls() as calls:
            await c.chat(system="s", user="u")

        assert len(calls) == 1
        call = calls[0]
        assert (call.role, call.model) == ("normalize", "m")
        assert (call.input_tokens, call.output_tokens) == (120, 30)
        assert call.seconds >= 0
        assert call.ok is True

    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    async def test_missing_usage_counts_as_zero(self, mock_openai_cls):
        from services.llm.client import LLMClient
        from services.llm.usage import collect_calls

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="hello"))],
            usage=None,
        )
        mock_openai_cls.return_value = client_mock

        c = LLMClient(model="m", base_url="http://x", api_key="k")
        with collect_calls() as calls:
            out = await c.chat(system="s", user="u")

        assert out == "hello"
        assert (calls[0].input_tokens, calls[0].output_tokens) == (0, 0)
        assert calls[0].role == ""

    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    async def test_failed_call_is_recorded_and_raised(self, mock_openai_cls):
        from services.llm.client import LLMClient
        from services.llm.usage import collect_calls

        client_mock = MagicMock()
        client_mock.chat.completions.create.side_effect = RuntimeError("timeout")
        mock_openai_cls.return_value = client_mock

        c = LLMClient(model="m", base_url="http://x", api_key="k")
        with collect_calls() as calls:
            with pytest.raises(RuntimeError):
                await c.chat(system="s", user="u")

        assert len(calls) == 1
        assert calls[0].ok is False

    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    async def test_concurrent_calls_are_collected_together(self, mock_openai_cls):
        import asyncio

        from services.llm.client import LLMClient
        from services.llm.usage import collect_calls

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="hello"))],
            usage=MagicMock(prompt_tokens=10, completion_tokens=2),
        )
        mock_openai_cls.return_value = client_mock

        c = LLMClient(model="m", base_url="http://x", api_key="k")
        with collect_calls() as calls:
            await asyncio.gather(*(c.chat(system="s", user="u") for _ in range(5)))

        assert len(calls) == 5

    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    async def test_nothing_collected_outside_scope(self, mock_openai_cls):
        from services.llm.client import LLMClient
        from services.llm.usage import collect_calls

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="hello"))],
            usage=MagicMock(prompt_tokens=10, completion_tokens=2),
        )
        mock_openai_cls.return_value = client_mock

        c = LLMClient(model="m", base_url="http://x", api_key="k")
        with collect_calls() as calls:
            pass
        await c.chat(system="s", user="u")

        assert calls == []
