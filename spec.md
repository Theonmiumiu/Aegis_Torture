Sub-project A: Profiler & Memory (状态追踪器)A_spec.md1. 服务需求与功能需求： 解决学习的“盲目性”与“过拟合（Bootstrap问题）”。核心功能：维护一个结构化的状态库（推荐使用 status.json + history.md）。Anti-Bootstrap 算法： 基于知识点覆盖率和遗忘曲线，计算今日考察权重。权重计算公式应包含：错误频率、距离上次考察时间、知识点关联度 以及一个 15% 的随机探索因子（防止永远陷入旧错题）。提取当前薄弱项（Weakness Tags）。2. 外部 API (函数签名)Pythondef get_daily_objectives(storage_path: str) -> dict:
    """
    输入：存储路径
    输出：{
        "target_tags": ["RAG", "Concurrency", "Dynamic Programming"],
        "strategy": "revisit_weakness" | "explore_new"
    }
    """

def update_profile(report_data: dict, storage_path: str) -> bool:
    """
    输入：Sub-project D 生成的批改报告
    功能：解析得分与错误类型，更新权重模型并写入存储。
    """
3. 算法复杂度要求时间复杂度：$O(K \cdot \log K)$，其中 $K$ 为维护的知识点标签总数。空间复杂度：$O(K + H)$，其中 $H$ 为历史记录条数。Sub-project B: Problem Synthesizer (题目合成器)B_spec.md1. 服务需求与功能需求： 获取高质量、符合“ACM + 复杂业务逻辑”风格的题目。核心功能：2+1 逻辑： 从 local_bank/ 随机挑选 2 道算法题；通过 LLM 联网搜索/生成 1 道包含复杂工程背景的原创题（如：模拟异步任务调度系统）。智能选择题生成： 调用 LLM 生成 5-10 道选择题，题目需围绕 Sub-project A 给出的 target_tags，且必须包含混淆选项和原理深度。数据清洗： 确保所有题目符合统一的 JSON 交换格式。2. 外部 API (函数签名)Pythondef fetch_coding_problems(tags: list, local_bank_path: str) -> list[dict]:
    """
    输出：包含 3 个字典的列表，每个字典含：title, description, constraint, sample_io, solution_code。
    """

def generate_mcqs(tags: list, profile_context: str) -> list[dict]:
    """
    输出：选择题列表，每个字典含：question, options, correct_answer, explanation。
    """
3. 算法复杂度要求时间复杂度：取决于 LLM API 响应。本地筛选应为 $O(N)$，其中 $N$ 为题库文件数。IO 复杂度：涉及联网 IO，需具备重试机制。Sub-project C: Exam Formatter (试卷排版引擎)C_spec.md1. 服务需求与功能需求： 将原始题目转化为人类可读且可直接编写代码的本地文件。核心功能：Markdown 渲染： 生成带目录、时间戳、难度标识的 .md 试卷。脚手架注入： 为每道算法题自动生成 if __name__ == "__main__": 的输入读取模板，方便用户直接运行自测。隐藏答案： 答案与解析应放在文档底部或单独的文件中。2. 外部 API (函数签名)Pythondef build_exam_md(coding_data: list, mcq_data: list, output_dir: str) -> str:
    """
    输入：B项目输出的题目数据
    输出：生成的 .md 文件路径
    """
3. 算法复杂度要求时间复杂度：$O(T + L)$，其中 $T$ 为题目字符数，$L$ 为模板长度。Sub-project D: Intelligent Grader (智能批改系统)D_spec.md1. 服务需求与功能需求： 模拟面试官的深度反馈。核心功能：静态分析： 检查用户提交的代码是否有语法错误。LLM 逻辑判分： 将用户代码与标准解法对比，评估：1. 逻辑正确性；2. 时间/空间复杂度是否达标；3. 工程健壮性（如并发处理是否稳健）。生成反馈报告： 输出一份包含得分、改进建议、涉及知识点掌握情况的 JSON 报告。2. 外部 API (函数签名)Pythondef evaluate_submission(user_code_map: dict, exam_data: dict) -> dict:
    """
    输入：{题目ID: 用户代码字符串}，以及试卷元数据
    输出：{
        "total_score": int,
        "detail_feedback": str,
        "knowledge_update": {"RAG": -5, "Concurrency": +10} # 调整分值
    }
    """
3. 算法复杂度要求时间复杂度：$O(Code\_Length + LLM\_Response\_Time)$。统筹层汇报：Theon，以上 4 份 spec.md 已经确立了项目的骨架。A 负责大脑。B 负责内容。C 负责外壳。D 负责考核。