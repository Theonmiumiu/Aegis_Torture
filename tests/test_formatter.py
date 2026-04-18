import tempfile
import os


PROBLEM_SET = {
    "exam_id": "EXAM-20260418-TEST",
    "exam_date": "2026-04-18",
    "target_tags": ["Concurrency", "RAG"],
    "algorithm_section": [
        {
            "id": "algo-01",
            "title": "环形二进制串",
            "desc": "给定长度为 $n$ 的串...",
            "constraints": "1 <= n <= 2*10^5",
            "sample_io": [{"input": "3\n8\n11001001", "output": "4"}],
            "io_spec": {"type": "multi_test_case"},
            "std_solution": "def solve(): pass  # 绝不能出现在生成的 md 中",
        }
    ],
    "mcq_section": [
        {
            "id": "mcq-01",
            "tag": "Concurrency",
            "text": "关于 asyncio，以下说法正确的是？",
            "options": {"A": "单线程并发", "B": "多线程并发", "C": "阻塞I/O", "D": "依赖回调"},
            "correct_options": ["A"],
            "explanation": "因为 asyncio 是单线程...",
        }
    ],
}


def test_build_daily_exam_creates_file():
    with tempfile.TemporaryDirectory() as d:
        from exam_formatter.services.formatter import build_daily_exam
        path = build_daily_exam(PROBLEM_SET, d)

        assert os.path.exists(path)
        assert path.endswith("Exam_20260418.md")


def test_build_daily_exam_excludes_answers():
    with tempfile.TemporaryDirectory() as d:
        from exam_formatter.services.formatter import build_daily_exam
        path = build_daily_exam(PROBLEM_SET, d)

        with open(path, encoding="utf-8") as f:
            content = f.read()

    assert "correct_options" not in content
    assert "std_solution" not in content
    assert "绝不能出现在生成的 md 中" not in content
    assert "因为 asyncio 是单线程" not in content


def test_build_daily_exam_includes_answer_placeholder():
    with tempfile.TemporaryDirectory() as d:
        from exam_formatter.services.formatter import build_daily_exam
        path = build_daily_exam(PROBLEM_SET, d)

        with open(path, encoding="utf-8") as f:
            content = f.read()

    assert "你的答案: [ ]" in content


def test_build_daily_exam_injects_boilerplate_multi_test_case():
    with tempfile.TemporaryDirectory() as d:
        from exam_formatter.services.formatter import build_daily_exam
        path = build_daily_exam(PROBLEM_SET, d)

        with open(path, encoding="utf-8") as f:
            content = f.read()

    assert "for _ in range(T)" in content
    assert "algo-01" in content
