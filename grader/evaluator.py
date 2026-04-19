# src/evaluator.py
import logging
from typing import List, Set, Optional
from .exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)


def score_mcq(user_ans_str: str, correct_options: List[str]) -> float:
    """
    实现多选题核心判分逻辑：
    - 全对: 1.0
    - 少选 (U ⊂ G): 0.33
    - 错选/多选 (U ⊈ G): 0
    - 未选: 0
    """
    # 格式化用户选项：去除空格，转为集合 (U)
    u_ans: Set[str] = {ans.strip() for ans in user_ans_str.split(",") if ans.strip()}
    # 正确选项集合 (G)
    g_ans: Set[str] = set(correct_options)

    if not u_ans:
        return 0.0

    # 错选/多选判定：只要用户选了任何一个不在正确答案里的，直接 0 分
    if not u_ans.issubset(g_ans):
        return 0.0

    # 全对判定
    if u_ans == g_ans:
        return 1.0

    # 少选判定 (此时已知 U 是 G 的子集且不相等)
    return 0.33


def evaluate_algorithm_with_llm(
        problem_desc: str,
        std_solution: str,
        user_code: str,
        llm_client: Optional[any] = None
) -> float:
    """
    驱动 LLM 对算法题进行智能化评判。
    """
    if not user_code.strip():
        return 0.0

    # 构造 Prompt
    prompt = f"""
    你是一位严谨的算法面试官。请评测以下 Python 代码：

    【题目描述】: {problem_desc}
    【标准解法】: {std_solution}
    【用户提交】: {user_code}

    【评分要求】:
    1. 逻辑正确性 (0-60分)
    2. 时间复杂度是否达到 O(N) 或 O(N log N) (0-20分)
    3. 工程实践与代码整洁度 (0-20分)

    请直接输出一个 0-100 的整数分值，不要包含任何解释。
    """

    try:
        # 这里预留 LLM 调用接口。如果是 mock 状态，我们模拟一个分数
        if llm_client:
            response = llm_client.generate_text(prompt)
            score = float(response.strip())
        else:
            # 开发环境下的 Mock 分数
            score = 80.0

            # 按比例折算回 0.0 - 1.0 范围
        return round(score / 100.0, 2)

    except Exception as e:
        logger.error(f"LLM 评测异常: {e}")
        raise LLMUnavailableError("LLM 评测服务响应超时，请保留现场并重试。")


def evaluate_code_snippet_with_llm(
        title: str,
        desc: str,
        reference_impl: str,
        user_code: str,
        llm_client: Optional[any] = None
) -> float:
    """
    使用 LLM 对手撕代码题进行评判，关注正确性与实现思路。
    """
    if not user_code.strip() or user_code.strip() == "# 在此处手写你的实现代码":
        return 0.0

    prompt = f"""
    你是一位资深 AI/算法工程师，正在面试评审候选人的手写代码。

    【题目】: {title}
    【要求】: {desc}
    【参考实现】: {reference_impl}
    【候选人提交】: {user_code}

    【评分维度】:
    1. 算法逻辑正确性：实现是否能正确完成题目要求 (0-50分)
    2. 关键步骤完整性：关键计算步骤是否都有体现，无明显遗漏 (0-30分)
    3. 代码质量：可读性、变量命名、无冗余错误代码 (0-20分)

    请直接输出一个 0-100 的整数分值，不要包含任何解释。
    """

    try:
        if llm_client:
            response = llm_client.generate_text(prompt)
            score = float(response.strip())
        else:
            score = 70.0
        return round(score / 100.0, 2)
    except Exception as e:
        logger.error(f"手撕题 LLM 评测异常: {e}")
        return 0.0