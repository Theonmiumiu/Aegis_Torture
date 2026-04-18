from unittest.mock import MagicMock


def _make_gen():
    from problem_synthesizer.core.mcq_generator import MCQGenerator
    mock_client = MagicMock()
    return MCQGenerator(mock_client), mock_client


def test_three_correct_options_not_truncated():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "关于 Python GIL？",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "B", "C"],
        "explanation": "解析..."
    }]'''

    mcqs = gen.generate_mcqs({"target_tags": ["Concurrency"]})

    assert len(mcqs) == 1
    assert len(mcqs[0]["correct_options"]) == 3, "3 个正确答案不应被截断"


def test_four_correct_options_clamped_to_three():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "Q?",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "B", "C", "D"],
        "explanation": "..."
    }]'''

    mcqs = gen.generate_mcqs({"target_tags": ["TCP"]})

    assert len(mcqs[0]["correct_options"]) == 3


def test_fallback_tags_used_when_target_tags_empty():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "Q?",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "B"],
        "explanation": "..."
    }]'''

    mcqs = gen.generate_mcqs({"target_tags": []})

    assert len(mcqs) > 0


def test_uses_template_for_prompt():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "Q?",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "C"],
        "explanation": "..."
    }]'''

    gen.generate_mcqs({"target_tags": ["RAG"]})

    call_args = mock_client.generate_text.call_args
    prompt = call_args[0][0]
    assert "RAG" in prompt
    assert "2 到 3 个正确选项" in prompt


def test_generate_batch_returns_correct_count():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[
        {"tag": "TCP", "text": "Q1?", "options": {"A":"a","B":"b","C":"c","D":"d"}, "correct_options": ["A","B"], "explanation": "..."},
        {"tag": "RAG", "text": "Q2?", "options": {"A":"a","B":"b","C":"c","D":"d"}, "correct_options": ["B","C"], "explanation": "..."},
        {"tag": "TCP", "text": "Q3?", "options": {"A":"a","B":"b","C":"c","D":"d"}, "correct_options": ["A","C"], "explanation": "..."},
        {"tag": "RAG", "text": "Q4?", "options": {"A":"a","B":"b","C":"c","D":"d"}, "correct_options": ["C","D"], "explanation": "..."}
    ]'''

    result = gen.generate_batch(["TCP", "RAG"], count=4)

    assert len(result) == 4
    for item in result:
        assert "question_id" in item
        assert "tag" in item
        assert "correct_options" in item


def test_generate_batch_uses_llm_provided_tag():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "tag": "RAG",
        "text": "Q?", "options": {"A":"a","B":"b","C":"c","D":"d"},
        "correct_options": ["A","B"], "explanation": "..."
    }]'''

    result = gen.generate_batch(["TCP", "RAG"], count=1)

    assert result[0]["tag"] == "RAG"


def test_generate_batch_fallback_tag_when_missing():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "Q?", "options": {"A":"a","B":"b","C":"c","D":"d"},
        "correct_options": ["A","B"], "explanation": "..."
    }]'''

    result = gen.generate_batch(["TCP", "RAG"], count=1)

    assert result[0]["tag"] == "TCP"


def test_generate_batch_prompt_contains_all_tags():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "tag": "TCP", "text": "Q?", "options": {"A":"a","B":"b","C":"c","D":"d"},
        "correct_options": ["A","B"], "explanation": "..."
    }]'''

    gen.generate_batch(["TCP", "RAG", "Concurrency"], count=3)

    prompt = mock_client.generate_text.call_args[0][0]
    assert "TCP" in prompt
    assert "RAG" in prompt
    assert "Concurrency" in prompt


def test_generate_batch_empty_tags_uses_fallback():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "tag": "并发与多线程 (Concurrency)", "text": "Q?",
        "options": {"A":"a","B":"b","C":"c","D":"d"},
        "correct_options": ["A","B"], "explanation": "..."
    }]'''

    result = gen.generate_batch([], count=1)

    assert len(result) == 1
    mock_client.generate_text.assert_called_once()
