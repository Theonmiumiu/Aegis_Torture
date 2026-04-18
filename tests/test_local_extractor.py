import tempfile
import os
import pytest


PROBLEM_CONTENT = '''\
"""
题目名称：环形前缀和

给定一个长度为 $n$ 的整数数组，对每个查询 $[l, r]$ 输出区间和。
输入数据量大，需使用前缀和优化。

约束条件：1 <= n <= 2 * 10^5，1 <= q <= 10^5

Example:
Input:
5 3
1 2 3 4 5
1 3
2 4
1 5
Output:
6
9
15
"""
import sys

def solve():
    pass

if __name__ == "__main__":
    solve()
'''

PROBLEM_NO_CONSTRAINTS = '''\
"""
简单的两数之和。

Example:
Input:
2
Output:
3
"""
def solve(): pass
'''


def _make_bank(tmpdir, files):
    for name, content in files.items():
        with open(os.path.join(tmpdir, name), "w", encoding="utf-8") as f:
            f.write(content)


def test_sample_problems_returns_correct_count():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {
            "prob_a.py": PROBLEM_CONTENT,
            "prob_b.py": PROBLEM_CONTENT,
            "prob_c.py": PROBLEM_CONTENT,
        })
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=2)

    assert len(problems) == 2


def test_sample_problems_has_required_fields():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {"p1.py": PROBLEM_CONTENT, "p2.py": PROBLEM_CONTENT})
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=2)

    for i, p in enumerate(problems):
        assert p["id"] == f"algo-{i+1:02d}"
        assert p["source"] == "local"
        assert isinstance(p["sample_io"], list)
        assert "input" in p["sample_io"][0]
        assert "output" in p["sample_io"][0]
        assert p["constraints"] != ""
        assert "io_spec" in p
        assert "tag" in p
        assert "brief_description" in p


def test_sample_problems_extracts_title():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {"p1.py": PROBLEM_CONTENT, "p2.py": PROBLEM_CONTENT})
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=1)

    assert problems[0]["title"] == "环形前缀和"


def test_sample_problems_without_constraints():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {"p1.py": PROBLEM_NO_CONSTRAINTS, "p2.py": PROBLEM_NO_CONSTRAINTS})
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=1)

    assert problems[0]["constraints"] == ""


def test_sample_problems_raises_when_bank_too_small():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {"p1.py": PROBLEM_CONTENT})
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        with pytest.raises(ValueError, match="本地题库数量不足"):
            extractor.sample_problems(count=2)


def test_tag_inferred_from_filename_prefix():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {
            "dp_coin_change.py": PROBLEM_CONTENT,
            "dp_other.py": PROBLEM_CONTENT,
        })
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=2)

    for p in problems:
        assert p["tag"] == "DP"
