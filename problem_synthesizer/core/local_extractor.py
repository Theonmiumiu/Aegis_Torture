import os
import random
import glob
import ast
from typing import List, Dict, Any


_TAG_PREFIXES = {
    "dp_": "DP",
    "graph_": "Graph",
    "tree_": "Tree",
    "sort_": "Sorting",
    "search_": "Search",
    "string_": "String",
    "math_": "Math",
    "greedy_": "Greedy",
    "binary_": "BinarySearch",
}


def _infer_tag(filename: str) -> str:
    lower = filename.lower()
    for prefix, tag in _TAG_PREFIXES.items():
        if lower.startswith(prefix):
            return tag
    return "Algorithm"


def _parse_example_block(example_text: str) -> Dict[str, str]:
    """将 Example 块解析为 {"input": ..., "output": ...}。"""
    text = example_text.strip()
    if "Input:" in text and "Output:" in text:
        after_input = text.split("Input:", 1)[1]
        parts = after_input.split("Output:", 1)
        return {
            "input": parts[0].strip(),
            "output": parts[1].strip(),
        }
    return {"input": text, "output": ""}


class LocalBankExtractor:
    """从指定目录无偏见地随机抽取已有算法题。"""

    def __init__(self, local_bank_path: str):
        self.local_bank_path = local_bank_path
        self.file_pool = glob.glob(
            os.path.join(self.local_bank_path, "**", "*.py"), recursive=True
        )

    def _parse_algorithm_file(self, file_path: str, problem_id: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        filename = os.path.basename(file_path).replace(".py", "")

        try:
            tree = ast.parse(content)
            docstring = ast.get_docstring(tree) or ""
        except Exception:
            docstring = ""

        title = filename
        desc = ""
        constraints = ""
        sample_io = []

        if docstring:
            lines = docstring.split("\n")
            first_line = lines[0].strip()

            # 提取题目名称
            for prefix in ("题目名称：", "题目名称:"):
                if first_line.startswith(prefix):
                    title = first_line[len(prefix):].strip()
                    break

            # 分割 Example 块
            if "Example:" in docstring:
                before_example, example_part = docstring.split("Example:", 1)
                sample = _parse_example_block(example_part)
                if sample["input"] or sample["output"]:
                    sample_io = [sample]
            else:
                before_example = docstring

            # 提取约束条件
            for marker in ("约束条件：", "约束条件:"):
                if marker in before_example:
                    desc_part, rest = before_example.split(marker, 1)
                    constraints = rest.strip().split("\n")[0].strip()
                    desc = desc_part.strip()
                    break
            else:
                desc = before_example.strip()

            # 去掉 desc 开头的题目名称行
            if desc.startswith(first_line):
                desc = "\n".join(desc.split("\n")[1:]).strip()

        tag = _infer_tag(filename)
        brief_description = (desc[:50] if desc else filename)

        return {
            "id": problem_id,
            "title": title,
            "desc": desc,
            "constraints": constraints,
            "sample_io": sample_io,
            "io_spec": {"type": "single_test_case"},
            "std_solution": content,
            "tag": tag,
            "brief_description": brief_description,
            "source": "local",
        }

    def sample_problems(self, count: int = 2) -> List[Dict[str, Any]]:
        """完全随机抽样，保证每题被选中概率为 count/N。"""
        total = len(self.file_pool)
        if total < count:
            raise ValueError(
                f"本地题库数量不足！需要 {count} 题，但仅找到 {total} 题。"
            )

        selected = random.sample(self.file_pool, count)
        return [
            self._parse_algorithm_file(fp, f"algo-{i+1:02d}")
            for i, fp in enumerate(selected)
        ]
