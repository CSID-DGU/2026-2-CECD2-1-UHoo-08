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