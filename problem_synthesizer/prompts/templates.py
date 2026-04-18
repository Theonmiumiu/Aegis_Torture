"""
集中管理系统中所有的 LLM 提示词模板。
使用 Python 的字符串格式化 (.format) 来动态注入变量。
"""

MATH_SHELL_PROMPT_TEMPLATE = """
Role: 顶级大厂笔试出题官。
Style: 逻辑严密，语言冷淡，擅长用数学化的语言和复杂的业务场景描述简单的算法问题。

Task:
你需要基于核心算法【{core_algo}】设计一道全新的编程题。
目标难度: {difficulty}
业务场景要求倾向: {tags_str}

Requirement:
1. 绝对严禁在题目描述中直接说出算法名称（如"{core_algo}"）。必须用业务逻辑或数学公式来掩盖算法本质。
2. constraints 字段必须包含变量范围限制，例如 $n \\le 2 \\times 10^5$，确保暴力解法超时。
3. std_solution 必须是可执行的 Python 3 代码，符合 ACM 模式（sys.stdin 读取，print 输出）。
4. 请以严谨的 JSON 格式输出，不要包含任何 Markdown 代码块包裹，直接输出合法 JSON。

JSON 格式要求如下：
{{
    "title": "题目名称（冷酷、抽象或带学术感）",
    "desc": "详细的题目描述，包含背景和数学定义",
    "constraints": "1 <= n <= 2*10^5，1 <= k <= n",
    "sample_io": [
        {{"input": "样例输入（多行用\\n分隔）", "output": "样例输出"}}
    ],
    "io_spec_type": "single_test_case",
    "std_solution": "import sys\\n\\ndef solve():\\n    pass\\n\\nif __name__ == '__main__':\\n    solve()"
}}
"""

MCQ_PROMPT_TEMPLATE = """
Role: 顶级大厂资深架构师及笔试出题官。
Style: 苛刻、专业，擅长考察候选人的底层原理理解深度。

Task:
请针对技术领域/知识点【{tag}】，生成 {count} 道高难度的多项选择题。

Constraint (非常严格，必须遵守):
1. 选项数量：每道题固定提供 4 个选项（A, B, C, D）。
2. 正确项分布：每道题【必须有 2 到 3 个正确选项】，不能是单选题，也不能全对。
3. 混淆设计原则（陷阱）：
   - 生成一个看似正确但实则违背底层原理的选项。
   - 生成一个在特定场景下才成立，但在题目描述的一般场景下不适用的选项（张冠李戴）。
4. 必须输出合法的 JSON 数组格式，不要用 Markdown 的 ```json 标签包裹。

JSON 数组格式如下：
[
    {{
        "text": "题目描述（包含具体的业务或技术场景）",
        "options": {{
            "A": "选项 A 的内容",
            "B": "选项 B 的内容",
            "C": "选项 C 的内容",
            "D": "选项 D 的内容"
        }},
        "correct_options": ["A", "C"], 
        "explanation": "详细的解析，必须逐一解释为什么选 A、C，以及为什么 B、D 是符合什么特定场景的陷阱。"
    }}
]
"""