# src/parser.py
import re
from typing import Dict, List, Tuple
from .exceptions import MarkdownFormatError

# 预编译正则表达式以提升高并发下的解析性能
# 匹配: 你的答案: [A, B] 或 你的答案: []
MCQ_REGEX = re.compile(r"你的答案:\s*\[([A-Z,\s]*)\]")
# 匹配代码块，使用 re.DOTALL 允许跨越多行
CODE_REGEX = re.compile(r"# ---\s*题目 ID:\s*(.*?)\s*---\n*```python\n(.*?)\n```", re.DOTALL)


def parse_markdown_submission(md_content: str, expected_mcq_count: int) -> Tuple[List[str], Dict[str, str]]:
    """
    解析用户提交的 Markdown 试卷文本。

    :param md_content: Markdown 试卷的纯文本内容
    :param expected_mcq_count: 期望提取的多选题数量（用于校验格式是否被破坏）
    :return: 包含多选题答案列表和算法题代码字典的元组 (mcq_matches, code_matches)
    :raises MarkdownFormatError: 当提取到的多选题数量与预期不符时抛出
    """
    # 1. 提取多选题原始答案字符串
    mcq_matches = MCQ_REGEX.findall(md_content)

    # 严格校验：防止用户误删了多选题的填写格式
    if len(mcq_matches) != expected_mcq_count:
        raise MarkdownFormatError(
            f"Markdown 格式异常：预期找到 {expected_mcq_count} 道多选题答案占位符，"
            f"但实际仅提取到 {len(mcq_matches)} 道。请检查是否误删了 '你的答案: []'。"
        )

    # 2. 提取算法题代码，构建 { "题目ID": "用户代码" } 的映射字典
    code_matches = {
        match[0].strip(): match[1].strip()
        for match in CODE_REGEX.findall(md_content)
    }

    return mcq_matches, code_matches