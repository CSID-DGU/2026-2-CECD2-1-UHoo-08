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
    async def test_cancelled_call_is_recorded_and_reraised(self, mock_openai_cls):
        import asyncio

        from services.llm.client import LLMClient
        from services.llm.usage import collect_calls

        mock_openai_cls.return_value = MagicMock()
        c = LLMClient(model="m", base_url="http://x", api_key="k")

        async def 취소된_스레드(*_args, **_kwargs):
            raise asyncio.CancelledError

        with patch("services.llm.client.asyncio.to_thread", 취소된_스레드):
            with collect_calls() as calls:
                with pytest.raises(asyncio.CancelledError):
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


class TestClaude:
    """모델 이름이 claude- 로 시작하면 Anthropic SDK 로 부르는지 본다."""

    @staticmethod
    def _응답(글='{"a": 1}', **토큰):
        토큰 = 토큰 or {"input_tokens": 100, "output_tokens": 20}
        return MagicMock(
            content=[MagicMock(type="thinking"), MagicMock(type="text", text=글)],
            usage=MagicMock(**토큰),
        )

    @pytest.mark.asyncio
    @patch("services.llm.client.OpenAI")
    @patch("anthropic.Anthropic")
    async def test_claude_model_goes_to_anthropic_sdk(self, mock_anthropic_cls, mock_openai_cls):
        from services.llm.client import LLMClient

        create = mock_anthropic_cls.return_value.messages.create
        create.return_value = self._응답()

        c = LLMClient(model="claude-haiku-5-5", base_url="https://proxy.example", api_key="k")
        out = await c.chat_json(system="s", user="u", temperature=0.0)

        assert out == {"a": 1}
        mock_openai_cls.assert_not_called()
        mock_anthropic_cls.assert_called_once_with(api_key="k", base_url="https://proxy.example")
        보낸 = create.call_args.kwargs
        assert 보낸["model"] == "claude-haiku-5-5"
        assert 보낸["system"] == "s"
        assert 보낸["messages"] == [{"role": "user", "content": "u"}]
        assert 보낸["max_tokens"] > 0
        # 받지 않는 옵션은 보내지 않는다
        assert "temperature" not in 보낸
        assert "response_format" not in 보낸
        assert "timeout" not in 보낸

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_empty_base_url_falls_back_to_official_address(self, mock_anthropic_cls):
        """비워 두면 SDK 가 환경 변수의 주소를 읽으므로 공식 주소를 직접 준다."""
        from services.llm.client import LLMClient

        LLMClient(model="claude-haiku-5-5", base_url="", api_key="k")

        assert mock_anthropic_cls.call_args.kwargs["base_url"] == "https://api.anthropic.com"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model, 생각", [
        ("claude-haiku-5-5", {"type": "disabled"}),
        ("claude-sonnet-5-5", {"type": "between_tools"}),
    ])
    @patch("anthropic.Anthropic")
    async def test_thinking_is_turned_off_per_model(self, mock_anthropic_cls, model, 생각):
        from services.llm.client import LLMClient

        create = mock_anthropic_cls.return_value.messages.create
        create.return_value = self._응답()

        c = LLMClient(model=model, base_url="", api_key="k")
        await c.chat(system="s", user="u")

        assert create.call_args.kwargs["thinking"] == 생각

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_unlisted_model_keeps_its_default_thinking(self, mock_anthropic_cls):
        """끄는 값을 모르는 모델에는 보내지 않는다. 잘못된 값은 오류가 난다."""
        from services.llm.client import LLMClient

        create = mock_anthropic_cls.return_value.messages.create
        create.return_value = self._응답()

        c = LLMClient(model="claude-opus-5-5", base_url="", api_key="k")
        await c.chat(system="s", user="u")

        assert "thinking" not in create.call_args.kwargs

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_timeout_is_passed(self, mock_anthropic_cls):
        from services.llm.client import LLMClient

        create = mock_anthropic_cls.return_value.messages.create
        create.return_value = self._응답()

        c = LLMClient(model="claude-haiku-5-5", base_url="", api_key="k")
        await c.chat(system="s", user="u", timeout=15.0)

        assert create.call_args.kwargs["timeout"] == 15.0

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_records_tokens_including_cached_input(self, mock_anthropic_cls):
        from services.llm.client import LLMClient, LLMRole
        from services.llm.usage import collect_calls

        mock_anthropic_cls.return_value.messages.create.return_value = self._응답(
            input_tokens=10, cache_creation_input_tokens=30, cache_read_input_tokens=60, output_tokens=5,
        )

        c = LLMClient(model="claude-haiku-5-5", base_url="", api_key="k", role=LLMRole.COMPOSE)
        with collect_calls() as calls:
            await c.chat(system="s", user="u")

        call = calls[0]
        assert (call.role, call.model, call.ok) == ("compose", "claude-haiku-5-5", True)
        assert (call.input_tokens, call.output_tokens) == (100, 5)

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_answer_without_text_is_empty(self, mock_anthropic_cls):
        """모델이 답을 거절하면 글 블록이 없다. 빈 답이 되고 JSON 으로는 None 이다."""
        from services.llm.client import LLMClient

        mock_anthropic_cls.return_value.messages.create.return_value = MagicMock(
            content=[], usage=MagicMock(input_tokens=5, output_tokens=0),
        )

        c = LLMClient(model="claude-haiku-5-5", base_url="", api_key="k")

        assert await c.chat(system="s", user="u") == ""
        assert await c.chat_json(system="s", user="u") is None

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_failed_call_is_recorded_and_raised(self, mock_anthropic_cls):
        from services.llm.client import LLMClient
        from services.llm.usage import collect_calls

        mock_anthropic_cls.return_value.messages.create.side_effect = RuntimeError("timeout")

        c = LLMClient(model="claude-haiku-5-5", base_url="", api_key="k")
        with collect_calls() as calls:
            with pytest.raises(RuntimeError):
                await c.chat(system="s", user="u")

        assert (calls[0].ok, calls[0].input_tokens, calls[0].output_tokens) == (False, 0, 0)

    def test_empty_key_is_rejected(self):
        """빈 키로 만들면 SDK 가 환경의 다른 인증 정보를 찾아 쓴다. 만들 때 막는다."""
        from services.llm.client import LLMClient

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            LLMClient(model="claude-haiku-5-5", base_url="", api_key="")


class TestRoleSettings:
    """역할의 모델을 보고 주소와 키의 기본값을 고르는지 본다."""

    @staticmethod
    def _역할_값(monkeypatch, 모델="", 주소="", 키=""):
        from services.llm import client

        monkeypatch.setattr(client.settings, "LLM_NORMALIZE_MODEL", 모델)
        monkeypatch.setattr(client.settings, "LLM_NORMALIZE_BASE_URL", 주소)
        monkeypatch.setattr(client.settings, "LLM_NORMALIZE_API_KEY", 키)
        monkeypatch.setattr(client.settings, "ANTHROPIC_API_KEY", "anthropic-key")
        monkeypatch.setattr(client.settings, "DASHSCOPE_API_KEY", "dashscope-key")
        return client

    def test_claude_model_gets_anthropic_address_and_key(self, monkeypatch):
        client = self._역할_값(monkeypatch, 모델="claude-haiku-5-5")

        assert client._설정(client.LLMRole.NORMALIZE) == (
            "claude-haiku-5-5", "https://api.anthropic.com", "anthropic-key",
        )

    def test_role_address_and_key_win(self, monkeypatch):
        client = self._역할_값(monkeypatch, 모델="claude-haiku-5-5", 주소="https://proxy.example", 키="role-key")

        assert client._설정(client.LLMRole.NORMALIZE) == (
            "claude-haiku-5-5", "https://proxy.example", "role-key",
        )

    def test_other_models_keep_qwen_defaults(self, monkeypatch):
        client = self._역할_값(monkeypatch)

        assert client._설정(client.LLMRole.NORMALIZE) == (
            client.settings.QWEN_TEXT_MODEL, client.settings.QWEN_TEXT_BASE_URL, "dashscope-key",
        )
