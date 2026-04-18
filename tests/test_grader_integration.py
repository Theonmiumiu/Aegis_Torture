import tempfile
import os
import json


MOCK_PROBLEM_SET = {
    "mcq_section": [
        {
            "question_id": "q1",
            "tag": "TCP",
            "text": "关于 TCP 三次握手？",
            "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "correct_options": ["A", "C"],
            "explanation": "解析...",
            "brief_description": "TCP 握手题",
        }
    ],
    "algorithm_section": [],
}

MD_WITH_CORRECT_ANSWER = """\
## 第一部分：多项选择题 (MCQs)

### 1. 关于 TCP 三次握手？ [标签: TCP]
- **A**: a
- **B**: b
- **C**: c
- **D**: d

**你的答案: [A, C]**

"""

MD_WITH_WRONG_ANSWER = """\
## 第一部分：多项选择题 (MCQs)

### 1. 关于 TCP 三次握手？ [标签: TCP]
- **A**: a

**你的答案: [B]**

"""


def _write_temp(d, ps, md):
    ps_path = os.path.join(d, "ps.json")
    md_path = os.path.join(d, "exam.md")
    with open(ps_path, "w", encoding="utf-8") as f:
        json.dump(ps, f)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    return md_path, ps_path


def test_grade_submission_correct_answer():
    with tempfile.TemporaryDirectory() as d:
        md_path, ps_path = _write_temp(d, MOCK_PROBLEM_SET, MD_WITH_CORRECT_ANSWER)
        from grader.grader import grade_submission
        report = grade_submission(md_path, ps_path)

    assert len(report) == 1
    assert report[0]["score"] == 1.0
    assert report[0]["tag"] == "TCP"


def test_grade_submission_wrong_answer():
    with tempfile.TemporaryDirectory() as d:
        md_path, ps_path = _write_temp(d, MOCK_PROBLEM_SET, MD_WITH_WRONG_ANSWER)
        from grader.grader import grade_submission
        report = grade_submission(md_path, ps_path)

    assert report[0]["score"] == 0.0
