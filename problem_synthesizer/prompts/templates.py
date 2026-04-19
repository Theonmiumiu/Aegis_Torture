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

CODE_SNIPPET_PROMPT_TEMPLATE = """
Role: 顶级 AI/ML 及算法工程师面试官。
Style: 严格、实践导向，考察候选人是否能从零手写核心模块代码。

Task:
请生成 {count} 道【算法模块手撕】题，考察以下领域的代码实现能力：{domains}

每道题要求候选人从零手写一个核心算法模块的 Python 代码实现。
题目应覆盖：LLM/Transformer架构模块、深度学习基础组件、强化学习基础算法、经典排序/搜索算法底层实现。

Constraint (必须严格遵守):
1. 题目必须要求候选人手写完整的可运行 Python 函数/类，不能只填空。
2. reference_impl 必须是正确的、可运行的 Python 代码（用 NumPy/PyTorch 或纯 Python）。
3. hint 字段提供关键思路提示（不能直接给答案），帮助候选人构建思路。
4. 必须输出合法的 JSON 数组格式，不要用 Markdown 代码块包裹。

JSON 数组格式如下：
[
    {{
        "title": "多头注意力机制 (Multi-Head Attention)",
        "desc": "请用 NumPy 手动实现多头注意力机制。函数签名：def multi_head_attention(Q, K, V, num_heads, d_model)，其中 Q/K/V 为 shape (seq_len, d_model) 的 numpy 数组。要求：1) 将 Q/K/V 分割为 num_heads 个头 2) 计算每个头的缩放点积注意力 3) 拼接所有头的输出。",
        "hint": "思路：d_k = d_model // num_heads，将矩阵 reshape 成 (seq_len, num_heads, d_k)，对每个头独立计算 softmax(QK^T/sqrt(d_k))V，最后 reshape 拼接。",
        "reference_impl": "import numpy as np\\n\\ndef softmax(x):\\n    e = np.exp(x - x.max(axis=-1, keepdims=True))\\n    return e / e.sum(axis=-1, keepdims=True)\\n\\ndef multi_head_attention(Q, K, V, num_heads, d_model):\\n    d_k = d_model // num_heads\\n    seq_len = Q.shape[0]\\n    Q = Q.reshape(seq_len, num_heads, d_k).transpose(1, 0, 2)\\n    K = K.reshape(seq_len, num_heads, d_k).transpose(1, 0, 2)\\n    V = V.reshape(seq_len, num_heads, d_k).transpose(1, 0, 2)\\n    scores = Q @ K.transpose(0, 2, 1) / np.sqrt(d_k)\\n    attn = softmax(scores)\\n    out = attn @ V\\n    return out.transpose(1, 0, 2).reshape(seq_len, d_model)",
        "tag": "LLM架构手撕",
        "difficulty": "hard"
    }}
]
"""

MCQ_BATCH_PROMPT_TEMPLATE = """你是一名顶级技术面试出题官。

【输出格式要求 — 最高优先级，任何情况下不得违反】
1. 你的回复必须是且仅是一个合法 JSON 数组，第一个字符是 [，最后一个字符是 ]，中间没有任何其他内容。
2. 绝对禁止在 JSON 前后添加任何说明文字、标题、markdown 代码块（```）、序号。
3. 所有字符串值内部如需换行，必须用 \\n 转义；如需双引号，必须用 \\" 转义。禁止出现裸换行符。
4. 所有 key 和 string value 必须使用英文双引号，禁止使用中文引号「」或单引号。
5. 每个对象末尾不得有多余逗号（trailing comma）。
6. explanation 字段长度不得超过 200 字，必须用单段落（无换行）输出。

【出题任务】
从以下技术领域中出题，尽量覆盖所有标签：【{tags_str}】
共生成 {count} 道高难度多项选择题。

题型分布（严格执行）：
- {academic_count} 道【学术知识考察题】(question_type: "academic")：考察纯理论、底层原理、协议细节。
- {business_count} 道【业务情景应用题】(question_type: "business_scenario")：设定真实工程场景，考察技术决策判断。

出题约束：
- 每道题固定 4 个选项（A B C D），正确选项恰好 2 或 3 个，不能全对也不能单选。
- 必须包含一个"看似正确但违背底层原理"的陷阱选项。
- 每道题必须含 "tag" 字段（取自上述标签列表原文）和 "question_type" 字段。

【JSON Schema（严格按此结构输出，字段顺序不限）】
[
  {{
    "tag": "标签原文",
    "question_type": "academic",
    "text": "题目描述",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct_options": ["A", "C"],
    "explanation": "不超过200字的单段落解析，说明正确选项原因及陷阱所在"
  }}
]"""