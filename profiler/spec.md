1. 需求背景与功能定义

本模块是整个“拷打机器”的决策大脑，专门负责管理多项选择题的知识点覆盖逻辑。其核心目标是通过分析历史得分，自动生成每日练习的“知识点配比”，确保在强化弱项的同时，避免因“引导过载”而产生的过拟合（Bootstrap）问题。

核心功能

知识建模：对大模型开发、工程架构、网络协议、强化学习等领域进行标签化管理。

状态追踪：基于特殊的 MCQ 评分规则（全对 1 分、少选 1/3 分、错选 0 分）动态更新掌握度。

权重决策：利用 Epsilon-Greedy 算法平衡“弱项专项突破”与“广度随机探索”。

持久化存储：维护结构化的 mcq_stats.json 以及可供用户阅读的 learning_progress.md。

2. 评分逻辑与状态转移

系统根据 Sub-project D 返回的批改数据进行状态更新。

2.1 掌握度（Mastery Level）计算

掌握度 $L$ 的范围为 $[0, 100]$，初始值为 $50$。

全对 (1.0分)：$L_{new} = \min(100, L_{old} + 10)$。标记该知识点为“已掌握”，降低后续出现频率。

少选 (1/3分)：$L_{new} = L_{old} + 2$。标记为“模糊”，权重保持平稳或小幅上调。

错选/多选 (0分)：$L_{new} = \max(0, L_{old} - 15)$。标记为“严重弱项”，下次测试权重显著提升。

2.2 抽样权重（Sampling Weight）公式

今日某知识点被抽中的概率权重 $W$ 计算如下：

$$W = (100 - L) \times (1 + \text{FailCount} \times 0.5) + \text{RecencyBonus}$$

FailCount: 该知识点连续得 0 分的次数。

RecencyBonus: 距离上次考察该知识点的时间越长，奖励分越高（模拟遗忘曲线）。

3. 抗过拟合策略 (Anti-Bootstrap)

为防止 LLM 陷入“只考错题”的循环，执行以下逻辑：

探索性抽样：每日生成的题目中，固定有 $15\%$ 的比例（Epsilon）从掌握度 $L > 80$ 或从未测试过的标签中随机抽取。

上下文隔离：维护一个 history_buffer，记录过去 3 天生成的具体题目描述，防止 LLM 生成逻辑雷同的题目。

4. API 接口规范 (Python)

4.1 获取今日题目配置

def get_mcq_config(storage_path: str) -> dict:
    """
    功能：计算并生成今日 MCQ 的考察指令。
    输入：storage_path (存储文件夹路径)
    输出：{
        "target_tags": ["Race Condition", "RAG Pipeline", "TCP"],
        "difficulty": "hard",
        "constraints": {
            "num_questions": 10,
            "exclusion_list": ["昨日已考过的具体知识点描述"]
        }
    }
    """


4.2 更新知识库状态

def update_mcq_stats(report_data: list, storage_path: str) -> bool:
    """
    功能：解析批改报告，执行掌握度状态转移。
    输入：report_data (Sub-project D 提供的标准化报告列表), storage_path
    输出：True/False (更新是否成功)
    """


5. 数据存储结构 (mcq_stats.json)

{
  "tags": {
    "Concurrency": {"level": 42, "fail_streak": 2, "last_seen": "2026-04-17"},
    "RAG_Retrieval": {"level": 85, "fail_streak": 0, "last_seen": "2026-04-15"}
  },
  "global_config": {
    "epsilon": 0.15,
    "total_exams_taken": 12
  }
}


6. 算法复杂度

时间复杂度：$O(T)$，$T$ 为标签总数。

空间复杂度：$O(T + H)$，$H$ 为近期的题目描述缓存。

7. 外部依赖：Sub-project D 输出规范

为了让 update_mcq_stats 正确运行，Sub-project D (Intelligent Grader) 在完成批改后必须返回以下格式的 report_data 列表：

7.1 报告项数据结构

[
  {
    "question_id": "uuid-string",
    "tag": "Concurrency",      // 必须对应 A 项目中的标签名
    "score": 0.33,             // 取值范围: [0, 0.33, 1.0]
    "is_correct": false,
    "user_feedback": "少选了 GIL 相关的两个正确选项",
    "brief_description": "关于 Python 并发中 GIL 对多线程性能影响的多选题" // 用于历史缓存隔离
  },
  {
    "question_id": "uuid-string-2",
    "tag": "TCP_Protocol",
    "score": 0,
    "is_correct": false,
    "user_feedback": "多选了 UDP 相关的错误选项",
    "brief_description": "TCP 三次握手过程中的状态机转换"
  }
]


7.2 字段约束

score: A 项目将严格根据此数值判断掌握度增量。D 项目需确保计算逻辑为：全对=1.0，漏选=0.33，错选/多选=0.0。

tag: 必须是 A 项目知识图谱中定义的合法标签。

brief_description: 此字段将被存入 A 项目的 history_buffer，用于在未来 3 天内过滤掉语义重复的题目生成请求。