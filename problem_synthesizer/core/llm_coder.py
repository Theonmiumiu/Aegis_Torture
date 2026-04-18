import json
import random
from typing import Dict, Any, List

from problem_synthesizer.prompts.templates import MATH_SHELL_PROMPT_TEMPLATE


class MathShellCoder:
    """
    大模型算法编纂引擎 (The "Math-Shell" Engine)
    负责驱动 LLM 生成带有数学/业务外壳的原创算法题，隐藏核心算法意图，并生成标准解。
    """

    def __init__(self, llm_client):
        """
        :param llm_client: 封装好的 LLM 客户端实例（包含重试机制）
        """
        self.llm_client = llm_client

        # 预设的基础核心算法库，LLM 将在这些算法基础上进行“外壳包装”
        self.base_algorithms = [
            "滑动窗口 (Sliding Window)",
            "前缀和 (Prefix Sum)",
            "一维动态规划 (1D Dynamic Programming)",
            "二分查找 (Binary Search)",
            "单调栈 (Monotonic Stack)",
            "拓扑排序 (Topological Sort)",
            "并查集 (Disjoint Set Union)"
        ]

    def _sample_core_algorithm(self, exclusion_list: List[str]) -> str:
        """
        随机采样核心算法，并避开 A 模块传入的排除名单。
        """
        # 简单容错：如果 exclusion_list 中的词出现在基础算法名中，则剔除
        available_algos = [
            algo for algo in self.base_algorithms
            if not any(ex.lower() in algo.lower() for ex in exclusion_list)
        ]

        # 极端情况容错：如果全被排除了，降级为全量随机
        if not available_algos:
            available_algos = self.base_algorithms

        return random.choice(available_algos)

    def _build_prompt(self, core_algo: str, target_tags: list, difficulty: str) -> str:
        tags_str = (
            ", ".join(target_tags)
            if target_tags
            else "金融量化、统计数据处理、分布式系统等随机场景"
        )
        return MATH_SHELL_PROMPT_TEMPLATE.format(
            core_algo=core_algo,
            difficulty=difficulty,
            tags_str=tags_str,
        ).strip()

    def generate_problem(self, config_from_a: Dict[str, Any]) -> Dict[str, Any]:
        """
        对外主接口：生成一道原创算法题。
        """
        target_tags = config_from_a.get("target_tags", [])
        difficulty = config_from_a.get("difficulty", "medium")
        exclusion_list = config_from_a.get("constraints", {}).get("exclusion_list", [])

        # 1. 抽取底层算法
        core_algo = self._sample_core_algorithm(exclusion_list)

        # 2. 组装 Prompt
        prompt = self._build_prompt(core_algo, target_tags, difficulty)

        # 3. 调用 LLM 并解析 (依赖外部 client 的重试机制保证可用性)
        try:
            # 这里的 temperature 也可以根据难度动态调整，例如 hard 题给更高温度激发创意
            temperature = 0.7 if difficulty == "hard" else 0.3
            response_text = self.llm_client.generate_text(prompt, temperature=temperature)

            # 净化 LLM 输出，防止包含 ```json 标签
            clean_json_str = response_text.replace("```json", "").replace("```", "").strip()
            problem_data = json.loads(clean_json_str)

            # Convert io_spec_type to io_spec dict
            io_spec_type = problem_data.pop("io_spec_type", "single_test_case")
            problem_data["io_spec"] = {"type": io_spec_type}

            # Ensure required schema fields exist
            problem_data.setdefault("constraints", "")
            problem_data.setdefault("sample_io", [])

            # Set tag from config, brief_description from desc
            problem_data["tag"] = target_tags[0] if target_tags else "Algorithm"
            desc = problem_data.get("desc", "")
            problem_data["brief_description"] = desc[:50] if desc else problem_data.get("title", "")[:50]
            problem_data["source"] = "llm_generated"

            return problem_data

        except json.JSONDecodeError as e:
            # 容错处理：如果 LLM 输出的 JSON 损坏，返回特定的错误结构，交给上层决定是否重试或丢弃
            return {
                "title": "系统降级补偿题",
                "desc": f"大模型生成试题解析失败。JSON Decode Error: {str(e)}",
                "constraints": "",
                "sample_io": [],
                "io_spec": {"type": "single_test_case"},
                "std_solution": "print('Error')",
                "tag": target_tags[0] if target_tags else "Algorithm",
                "brief_description": "降级补偿题",
                "source": "fallback",
            }
        except Exception as e:
            raise RuntimeError(f"调用 LLM 生成试题时发生系统级异常: {str(e)}")