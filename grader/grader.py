# src/grader.py
import json
from typing import List, Dict, Any
from .parser import parse_markdown_submission
from .evaluator import score_mcq, evaluate_algorithm_with_llm


def grade_submission(md_file_path: str, problem_set_json_path: str, llm_client=None) -> List[Dict[str, Any]]:
    """
    D 模块主接口：解析试卷并生成判分报告。

    :param md_file_path: 用户编辑后的 .md 文件路径
    :param problem_set_json_path: B 模块生成的原始 JSON 路径
    :return: 报告列表，每个元素包含 {tag, score, brief_description}
    """
    # 1. 加载题目元数据
    with open(problem_set_json_path, 'r', encoding='utf-8') as f:
        problem_set = json.load(f)

    # 2. 读取并解析 Markdown
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # 从 Markdown 中提取答案
    expected_mcq_count = len(problem_set.get("mcq_section", []))
    mcq_answers, code_blocks = parse_markdown_submission(md_content, expected_mcq_count)

    report_data = []

    # 3. 评定多选题
    for idx, mcq_meta in enumerate(problem_set.get("mcq_section", [])):
        raw_ans = mcq_answers[idx]
        score = score_mcq(raw_ans, mcq_meta["correct_options"])

        report_data.append({
            "tag": mcq_meta["tag"],
            "score": score,
            "brief_description": mcq_meta.get("brief_description", f"MCQ-{idx + 1}")
        })

    # 4. 评定算法题
    for algo_meta in problem_set.get("algorithm_section", []):
        algo_id = algo_meta["id"]
        user_code = code_blocks.get(algo_id, "")

        score = evaluate_algorithm_with_llm(
            problem_desc=algo_meta.get("desc", algo_meta.get("description", "")),
            std_solution=algo_meta.get("std_solution", ""),
            user_code=user_code,
            llm_client=llm_client,
        )

        report_data.append({
            "tag": algo_meta.get("tag", "Algorithm"),
            "score": score,
            "brief_description": algo_meta.get(
                "brief_description",
                algo_meta.get("desc", f"Algo-{algo_id}")[:50]
            ),
        })

    return report_data