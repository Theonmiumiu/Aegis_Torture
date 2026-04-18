from unittest.mock import MagicMock, patch


def test_generate_text_success():
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "test response"
        mock_openai_cls.return_value.chat.completions.create.return_value = mock_response

        from problem_synthesizer.utils.llm_client import LLMClient
        client = LLMClient(api_key="test", base_url="http://test", model="test-model")
        result = client.generate_text("hello")

    assert result == "test response"


def test_generate_text_retries_on_failure():
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok after retry"
        create_mock = mock_openai_cls.return_value.chat.completions.create
        create_mock.side_effect = [ConnectionError("network fail"), mock_response]

        with patch("problem_synthesizer.utils.llm_client.time.sleep"):
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=3)
            result = client.generate_text("hello")

    assert result == "ok after retry"
    assert create_mock.call_count == 2


def test_generate_text_raises_after_max_retries():
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        create_mock = mock_openai_cls.return_value.chat.completions.create
        create_mock.side_effect = ConnectionError("always fails")

        with patch("problem_synthesizer.utils.llm_client.time.sleep"):
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=2)
            try:
                client.generate_text("hello")
                assert False, "应该抛出 RuntimeError"
            except RuntimeError as e:
                assert "多次调用失败" in str(e)

        assert create_mock.call_count == 3  # max_retries=2: 1 initial + 2 retries


def test_rate_limit_does_not_consume_retries():
    """Rate limit 错误不应消耗 max_retries 计数。"""
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "success"
        create_mock = mock_openai_cls.return_value.chat.completions.create
        # 两次 rate limit，第三次成功
        create_mock.side_effect = [
            Exception("429 rate limit exceeded"),
            Exception("too frequent, please try again"),
            mock_response,
        ]

        with patch("problem_synthesizer.utils.llm_client.time.sleep"):
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=1)
            result = client.generate_text("hello")

    assert result == "success"
    # max_retries=1 but 2 rate limit errors happened — should NOT have raised
    assert create_mock.call_count == 3


def test_rate_limit_sleeps_60_seconds():
    """Rate limit 错误必须等待 60 秒。"""
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        create_mock = mock_openai_cls.return_value.chat.completions.create
        create_mock.side_effect = [Exception("too frequent"), mock_response]

        with patch("problem_synthesizer.utils.llm_client.time.sleep") as mock_sleep:
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=3)
            client.generate_text("hello")

    assert mock_sleep.call_args_list[0][0][0] == 60
