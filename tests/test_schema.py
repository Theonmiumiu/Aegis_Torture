def test_schema_imports():
    from schema import ProblemSet, AlgorithmProblem, MCQProblem, IOSpec, SampleIO
    assert ProblemSet is not None

def test_algorithm_problem_has_required_fields():
    from schema import AlgorithmProblem
    p: AlgorithmProblem = {
        "id": "algo-01",
        "title": "Test",
        "desc": "description",
        "constraints": "1 <= n <= 100",
        "sample_io": [{"input": "3", "output": "6"}],
        "io_spec": {"type": "single_test_case"},
        "std_solution": "def solve(): pass",
        "tag": "Algorithm",
        "brief_description": "short desc",
        "source": "local",
    }
    assert p["id"] == "algo-01"
    assert p["source"] == "local"

def test_mcq_problem_has_required_fields():
    from schema import MCQProblem
    q: MCQProblem = {
        "question_id": "uuid-1",
        "tag": "Concurrency",
        "text": "关于 asyncio？",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "C"],
        "explanation": "解析...",
    }
    assert q["correct_options"] == ["A", "C"]
