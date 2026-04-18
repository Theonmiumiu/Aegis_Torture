from grader.evaluator import score_mcq


def test_score_mcq_perfect():
    assert score_mcq("A, C", ["A", "C"]) == 1.0


def test_score_mcq_partial_one_of_two():
    assert score_mcq("A", ["A", "C"]) == 0.33


def test_score_mcq_wrong_selection():
    assert score_mcq("B", ["A", "C"]) == 0.0


def test_score_mcq_mixed_wrong_and_right():
    assert score_mcq("A, B", ["A", "C"]) == 0.0


def test_score_mcq_empty_answer():
    assert score_mcq("", ["A", "C"]) == 0.0


def test_score_mcq_all_options_wrong():
    assert score_mcq("D", ["A", "B", "C"]) == 0.0


def test_evaluate_algorithm_calls_generate_text():
    from unittest.mock import MagicMock
    from grader.evaluator import evaluate_algorithm_with_llm

    mock_client = MagicMock()
    mock_client.generate_text.return_value = "85"

    score = evaluate_algorithm_with_llm(
        problem_desc="题目描述",
        std_solution="def solve(): pass",
        user_code="def solve(): return 1",
        llm_client=mock_client,
    )

    assert score == 0.85
    mock_client.generate_text.assert_called_once()
    prompt_used = mock_client.generate_text.call_args[0][0]
    assert "题目描述" in prompt_used
