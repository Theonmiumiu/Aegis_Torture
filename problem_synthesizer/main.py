import os
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

# 导入我们之前构建的核心模块与工具
from core.local_extractor import LocalBankExtractor
from core.llm_coder import MathShellCoder
from core.mcq_generator import MCQGenerator
from utils.llm_client import LLMClient


def generate_daily_problem_set(config_from_a: Dict[str, Any], local_bank_path: str) -> Dict[str, Any]:
    """
    功能：构建完整的每日题目集。
    输入：
        config_from_a: A 模块 get_mcq_config 的输出字典。
        local_bank_path: 本地算法题库路径。
    输出：
        符合 API 规范的题目集字典。
    """
    # 1. 初始化依赖 (实际生产环境中 API Key 应通过环境变量传入)
    api_key = os.environ.get("LLM_API_KEY", "mock-api-key")
    llm_client = LLMClient(api_key=api_key, max_retries=3)

    # 2. 初始化各个生成引擎
    extractor = LocalBankExtractor(local_bank_path)
    coder = MathShellCoder(llm_client)
    mcq_gen = MCQGenerator(llm_client)

    coding_problems = []

    print("[System] 开始生成每日题目包...")

    # 3.1 执行“2+1”策略：本地提取 (2 道算法题)
    try:
        print("[System] -> 正在从本地题库抽取基础算法题 (O(1) 抽样)...")
        local_problems = extractor.sample_problems(count=2)
        coding_problems.extend(local_problems)
    except ValueError as e:
        print(f"[Error] 本地题库抽取异常: {e}")
        # 在实际系统中，此处可以加入降级逻辑，比如全部由 LLM 生成
    except Exception as e:
        print(f"[Error] 本地题库读取失败: {e}")

    # 3.2 执行“2+1”策略：大模型编纂 (1 道带数学/业务外壳的算法题)
    print("[System] -> 正在驱动 LLM 编纂高阶 Math-Shell 算法题...")
    try:
        math_shell_problem = coder.generate_problem(config_from_a)
        coding_problems.append(math_shell_problem)
    except Exception as e:
        print(f"[Error] LLM 算法题编纂失败: {e}")

    # 3.3 多选题定向生成
    print("[System] -> 正在根据 Target Tags 生成多项选择题 (MCQ)...")
    mcqs = mcq_gen.generate_mcqs(config_from_a)

    # 4. 构建并格式化最终输出
    # 按照要求，基于北京时间 (UTC+8) 生成独一无二的试卷 ID
    beijing_tz = timezone(timedelta(hours=8))
    date_str = datetime.now(beijing_tz).strftime("%Y%m%d")
    exam_id = f"EXAM-{date_str}-{str(uuid.uuid4())[:8].upper()}"

    final_exam_set = {
        "exam_id": exam_id,
        "coding_problems": coding_problems,
        "mcqs": mcqs
    }

    print(f"[System] 每日试卷 {exam_id} 组装完毕！")
    return final_exam_set


if __name__ == "__main__":
    # ==========================================
    # 模拟测试入口
    # ==========================================

    # 模拟 Sub-project A 传递过来的配置参数，加入了你熟悉的统计学和高并发场景
    mock_config_from_a = {
        "target_tags": ["高频交易撮合引擎", "马尔可夫链蒙特卡洛(MCMC)"],
        "difficulty": "hard",
        "constraints": {
            "exclusion_list": ["二叉树", "基础排序"]
        }
    }

    # 假设本地题库路径
    mock_local_bank_path = "mock_local_bank"

    # 防御性代码：为了让测试脚本能直接跑通，如果没有题库则动态创建占位文件
    if not os.path.exists(mock_local_bank_path):
        os.makedirs(mock_local_bank_path)
        for i in range(2):
            with open(os.path.join(mock_local_bank_path, f"dummy_problem_{i}.py"), "w", encoding="utf-8") as f:
                f.write(f'"""\nExample:\nInput: {i}\nOutput: {i}\n"""\ndef solve(): pass')

    # 运行主流程
    result = generate_daily_problem_set(mock_config_from_a, mock_local_bank_path)

    # 打印最终生成的字典
    print("\n" + "=" * 50)
    print(" 最终生成的试卷 JSON 结构：")
    print("=" * 50)
    print(json.dumps(result, indent=4, ensure_ascii=False))