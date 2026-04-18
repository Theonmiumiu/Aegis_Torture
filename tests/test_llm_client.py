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

        with patch("time.sleep"):
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=3)
            result = client.generate_text("hello")

    assert result == "ok after retry"
    assert create_mock.call_count == 2


def test_generate_text_raises_after_max_retries():
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        create_mock = mock_openai_cls.return_value.chat.completions.create
        create_mock.side_effect = ConnectionError("always fails")

        with patch("time.sleep"):
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=2)
            try:
                client.generate_text("hello")
                assert False, "应该抛出 RuntimeError"
            except RuntimeError as e:
                assert "多次调用失败" in str(e)
