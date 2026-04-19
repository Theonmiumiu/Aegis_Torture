1. 需求背景与功能定义

本模块是整个闭环系统的“质检员”。它负责解析用户在 Markdown 试卷中填写的答案，进行自动化与智能化的评判，并生成标准化的反馈报告，驱动 Sub-project A 进行下一次决策。

核心功能

答案解析提取：利用正则表达式从 Markdown 文件中提取多选题选项和算法代码块。

多选题自动化判分：执行“全对得 1 分，漏选得 1/3 分，错选/多选得 0 分”的逻辑。

代码智能化评测：驱动 LLM 作为审阅者，对比用户代码与标准解法（Standard Solution），评估正确性与时空复杂度。

反馈闭环生成：输出符合 A 模块接口规范的 JSON 报告。

2. 核心逻辑实现

2.1 答案提取逻辑 (Regex Extraction)

MCQ 提取：匹配模式 你的答案: \[([A-Z, ]*)\]。

代码块提取：匹配以 # --- 题目 ID: (.*) --- 开头的 Python 代码块。

2.2 多选题判分算法

对于每一道多选题，设 $G$ 为正确选项集合，$U$ 为用户选择集合：

错选/多选判定：若 $U \not\subseteq G$（即用户选了不该选的），得分 = 0。

全对判定：若 $U = G$，得分 = 1.0。

少选判定：若 $U \subset G$ 且 $U \neq \emptyset$，得分 = 0.33。

未选判定：若 $U = \emptyset$，得分 = 0。

2.3 算法题评测逻辑 (LLM Judge)

针对 3 道算法题，D 模块将组装一个特殊的 Prompt 给 LLM：

输入：题目描述、标准解法代码、用户提交代码。

要求：

检查逻辑正确性。

评估时间复杂度是否满足 $O(N)$ 或 $O(N \log N)$ 约束。

给出具体的工程改进建议。

输出一个 0-100 的分值，随后按比例折算。

3. API 接口规范 (Python)

模块路径：services/grader.py

grade_submission(md_file_path: str, problem_set_json_path: str) -> list

输入参数：

md_file_path: 用户编辑后的 .md 试卷路径。

problem_set_json_path: B 模块生成的原始题目 JSON 路径（包含答案）。

输出格式：
符合 A 模块 update_mcq_stats 要求的 report_data 列表。

4. 外部依赖与数据对齐

4.1 期待 Sub-project B 的输入

D 模块需要从 B 模块的 JSON 中读取：

mcqs[].correct_options: 用于比对。

algorithm_section[].std_solution: 用于 LLM Judge 参考。

mcqs[].tag: 用于反馈给 A 模块。

4.2 输出至 Sub-project A

生成的报告必须包含：

tag: 对应知识点。

score: 判分结果（0, 0.33, 1.0）。

brief_description: 题目核心逻辑简述（用于 A 模块的去重逻辑）。

5. 异常处理

正则失效：若用户破坏了 Markdown 的固定格式（如删除了 你的答案: []），D 模块应抛出明确的 UI 提示，引导用户恢复格式。

LLM 宕机：若 LLM Judge 无法响应，系统应保留用户代码，待恢复后重新批改，不得直接给 0 分。

6. 算法复杂度

解析复杂度：$O(M)$，$M$ 为 Markdown 文件字符数。

判分复杂度：$O(Q + L)$，$Q$ 为题目数量，$L$ 为 LLM 响应时间。