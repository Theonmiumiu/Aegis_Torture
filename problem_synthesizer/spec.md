1. 需求背景与功能定义

本模块负责根据 Sub-project A 的配置指令，生产出一套完整的“每日试卷”原始数据。它需要协调本地文件系统、联网搜索 API 以及 LLM 的生成能力。

核心功能

本地算法抽样 (2/3)：从指定的本地题库目录中，通过完全随机的方式抽取 2 道已有的算法题及其标准解法。

硬核算法编纂 (1/3)：驱动 LLM 编造成 1 道具有“数学外壳”或“复杂业务场景”的原创算法题，并生成对应的 Standard Solution。

多选题定向生成：根据 A 模块提供的 target_tags，生成具有高度迷惑性的多项选择题。

题目质量校验：确保生成的题目符合 ACM 模式输入输出规范。

2. 核心逻辑：2+1 算法题合成策略

2.1 本地提取 (Local Extraction - 完全随机模式)

输入：local_bank_path (包含大量 .py 格式算法题的文件夹)。

逻辑：

文件扫描：使用 glob 或 os.walk 检索文件夹内所有以 .py 结尾的文件。

随机化洗牌：使用 Python 的 random.sample() 函数从文件列表中无偏见地抽取 2 个文件。

解析内容：对选中的文件进行文本解析，提取：

title: 题目名称。

description: 题目描述（通常位于文件开头的多行注释或 Docstring 中）。

std_solution: 文件的全部代码内容。

io_spec: 样例输入输出示例。

2.2 LLM 编纂 (The "Math-Shell" Engine)

设计意图：针对你提到的“看上去像数学题”的需求，通过特定的 Prompt Engineering 迫使 LLM 隐藏算法本质。

生成步骤：

随机采样核心算法：如滑动窗口、前缀和、动态规划等。

应用业务/数学外壳：例如将“滑动窗口”包装成“卫星信号覆盖”，将“前缀和”包装成“环形串的最短前缀长度”。

生成标准解：LLM 必须同步生成一份可执行的 Python 标准代码，用于后续 D 模块的对比。

3. 多选题生成逻辑 (MCQ Generation)

3.1 陷阱设计原则

为配合 A 模块的评分规则（少选得 1/3），生成器必须遵循：

选项数量：固定为 4 个选项。

正确项分布：每道题确保有 2-3 个正确选项。

混淆设计：

针对 tag（如并发），生成一个看似正确但实则违背原理的选项。

针对 tag（如 RAG），生成一个在特定场景下才成立但题目场景不适用的选项。

4. API 接口规范 (Python)

4.1 生成每日题目包

def generate_daily_problem_set(config_from_a: dict, local_bank_path: str) -> dict:
    """
    功能：构建完整的题目集。
    输入：
        config_from_a: A 模块 get_mcq_config 的输出。
        local_bank_path: 本地算法题库路径。
    输出：
        {
            "exam_id": "date-uuid",
            "coding_problems": [
                {"title": str, "desc": str, "io_spec": dict, "std_solution": str, "source": "local"},
                {"title": str, "desc": str, "io_spec": dict, "std_solution": str, "source": "local"},
                {"title": str, "desc": str, "io_spec": dict, "std_solution": str, "source": "llm_generated"}
            ],
            "mcqs": [
                {
                    "question_id": str,
                    "tag": str,
                    "text": str,
                    "options": {"A": str, "B": str, ...},
                    "correct_options": ["A", "C"],
                    "explanation": str
                }
            ]
        }
    """


5. 提示词工程 (Prompt Engineering) 指南

子项目开发人员需为 LLM 准备以下角色设定的 Prompt：

Role: 顶级大厂笔试出题官。

Style: 逻辑严密，语言冷淡，擅长用数学化的语言描述简单的算法问题。

Requirement:

“严禁直接说出算法名称”。

“必须包含变量范围限制（Constraints），如 $n \le 2 \times 10^5$”。

“必须符合 ACM 模式（读取 stdin，打印 stdout）”。

6. 算法复杂度与资源限制

抽样公平性：本地提取必须确保 $O(1)$ 的单次抽样成本（在文件列表生成后），且保证每个题目被选中的概率为 $2/N$。

网络依赖：需处理 LLM API 的超时与重试（Exponential Backoff）。

缓存机制：若文件读取失败或 LLM 生成失败，应具备回退机制。

7. 外部依赖：Sub-project A 输入规范

B 模块必须严格解析 A 模块 get_mcq_config 函数返回的字典，具体映射逻辑如下：

7.1 字段映射逻辑

target_tags:

MCQ 模块: 必须为列表中的每个 tag 至少生成 1-2 道题目。

算法编纂模块: LLM 应优先尝试将这些 tag 中的工程背景融入题目背景描述中。

difficulty:

影响 LLM 的 Temperature 参数以及题目约束范围。

constraints.exclusion_list:

去重逻辑: 明确要求 LLM：“禁止考察以下具体知识点”。

7.2 容错处理

若 A 模块返回的 target_tags 为空，B 模块应自动切换至“全领域随机抽样”模式。