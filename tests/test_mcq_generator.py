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
