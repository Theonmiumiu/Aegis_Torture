# DEV — 开发者文档

本文档详细描述各模块的实现逻辑、数据格式、设计决策及已知缺陷。读者应能据此理解完整数据流并独立修改任意模块。

---

## 整体数据流

```
[profiler] get_mcq_config()
       ↓ target_tags, difficulty, exclusion_list
[problem_synthesizer]
  ├── LocalBankExtractor      → 2 道本地算法题
  ├── MathShellCoder          → 1 道 LLM 原创算法题
  ├── MCQGenerator            → 20 道多选题（并发批次）
  └── CodeSnippetGenerator    → 3 道算法模块手撕题（并发）
       ↓ problem_set dict（含 code_snippet_section）
[exam_formatter] build_daily_exam()
       ↓ Exam_YYYYMMDD_HHMMSS.md
         第一部分：MCQ（20 道）
         第二部分：算法编程题（3 道）
         第三部分：算法模块手撕（预制类定义 + 3 道）
[用户作答]
       ↓ 已填写的 Markdown / Web 表单提交
[grader]
  ├── parser.parse_markdown_submission()
  ├── evaluator.score_mcq()                     → MCQ 判分
  ├── evaluator.evaluate_algorithm_with_llm()   → 算法题评分
  └── evaluator.evaluate_code_snippet_with_llm() → 手撕题评分
       ↓ report_data（含 section / question_text 字段）
[profiler] update_mcq_stats()  → 更新 tags 掌握度 + wrong_history
[profiler] generate_report()   → 输出知识点画像 + 综合评估 + 错题日历
```

运行时产生的文件：

| 文件 | 产生时机 | 用途 |
|---|---|---|
| `data/mcq_stats.json` | 每次 grade | Profiler 状态持久化（含 `wrong_history`） |
| `data/problem_set_YYYYMMDD_HHMMSS.json` | 每次 run | 题目元数据，批改时读取答案和标准解 |
| `data/learning_progress.md` | 每次 grade/report | 人类可读进度报告（含综合评估 + 错题日历） |
| `output/Exam_YYYYMMDD_HHMMSS.md` | 每次 run | 试卷，用户在此作答 |

文件名包含时间戳（精确到秒），同一天多次 `run` 不会互相覆盖。`grade` 命令通过 `sorted(glob(...))[-1]` 取字母序最后一份（即最新）试卷，并用其文件名中的时间戳反查对应的 `problem_set_*.json`，保证两者严格一一对应。

---

## 模块详解

### 1. Config — `config.py`

`Settings` 是一个 `dataclass`，通过 `python-dotenv` 从 `.env` 读取六个配置项：`api_key`、`base_url`、`model`、`local_bank_path`、`data_path`、`output_path`。

模块顶层实例化 `settings = Settings()`，其余模块直接 `from config import settings` 使用。没有任何验证逻辑，`api_key` 为空时只会在第一次实际 LLM 调用时报错。

---

### 2. Profiler — `profiler/core/profiler.py`

**职责**：维护每个知识点标签的掌握度状态，生成出题配置，接收批改报告更新状态。

**持久化格式** (`data/mcq_stats.json`)：

```json
{
  "tags": {
    "并发与多线程 (Concurrency)": {
      "level": 60,
      "fail_streak": 0,
      "last_seen": "2026-04-19"
    }
  },
  "global_config": {
    "epsilon": 0.15,
    "total_exams_taken": 5
  },
  "history_buffer": [
    {"date": "2026-04-19", "description": "asyncio 事件循环机制"}
  ],
  "wrong_history": [
    {
      "date": "2026-04-19",
      "tag": "大模型架构原理",
      "section": "mcq",
      "question_text": "以下关于多头注意力机制说法正确的是...",
      "score": 0.0
    }
  ]
}
```

`wrong_history` 记录近 30 天内所有 score < 1.0 的题目，保留字段：`date`、`tag`、`section`（`mcq` / `algorithm` / `code_snippet`）、`question_text`（前 150 字符）、`score`。超过 30 天的记录在每次 `update_mcq_stats` 时自动清理。

**权重计算公式**（`_calculate_weight`）：

```
W = (100 - level) × (1 + fail_streak × 0.5) + max(0, days_since_seen × 2.0)
```

掌握度越低、连续错误越多、越久没考察，权重越高。

**出题配置生成**（`get_mcq_config`）：

采用 Epsilon-Greedy 策略。`level > 80` 的标签进入"探索池"，其余进入"开发池"。按 `epsilon=0.15` 分配名额：15% 从探索池随机采样，85% 从开发池加权采样（A-Res 算法变体）。从 `history_buffer` 中提取最近题目描述作为 `exclusion_list` 传给 MathShellCoder，避免生成重题。

**状态转移**（`update_mcq_stats`）：

| 得分 | level 变化 | fail_streak |
|---|---|---|
| ≥ 0.99（全对）| +10，上限 100 | 清零 |
| ≥ 0.3（少选）| +2，上限 100 | 不变 |
| < 0.3（错/多选）| -15，下限 0 | +1 |

`history_buffer` 保留最近 3 天的题目描述，超期自动清理。`wrong_history` 保留最近 30 天的错题记录，超期自动清理。

**已知缺陷**：

- **冷启动问题**：`mcq_stats.json` 为空时，`get_mcq_config` 返回 `target_tags: []`，出题完全依赖 `MCQGenerator.fallback_tags` 的随机兜底，无任何个性化。需要做几次测试后 Profiler 才开始有效工作。
- **标签字符串不一致**：Profiler 存储的 tag key 来自 LLM 返回的 `tag` 字段，而 `fallback_tags` 是硬编码的中文长字符串。LLM 可能返回缩写或变体，导致同一知识点被拆成两个 key 分别追踪，画像碎片化。
- **`history_buffer` 仅防 3 天内重题**，更长时间后同类题会重复出现，没有语义去重。

---

### 3. Problem Synthesizer — `problem_synthesizer/`

#### 3a. LocalBankExtractor — `core/local_extractor.py`

递归扫描 `local_bank/` 目录下所有 `.py` 文件。通过 `ast.parse` 提取模块级 docstring，按约定格式解析题目名称、描述、约束条件和样例 IO。

Tag 推断完全基于文件名前缀（`dp_`、`graph_`、`tree_` 等），无前缀一律打 `"Algorithm"`。

**已知缺陷**：

- **Tag 推断极为脆弱**：中文命名的文件（如 `local_bank/士兵的任务2.py`）无任何前缀可匹配，全部归类为 `"Algorithm"`，Profiler 无法针对性追踪这些题目的知识点。
- **Docstring 格式依赖约定**：必须包含特定标记（`Example:`、`约束条件:`）才能正确解析。格式不符时静默降级，字段为空，不报错。
- `std_solution` 字段直接等于文件全部源码，包含 `import` 和辅助函数，并非纯粹的解题函数。

#### 3b. MathShellCoder — `core/llm_coder.py`

从 7 个预设核心算法（滑动窗口、前缀和、1D DP、二分、单调栈、拓扑排序、并查集）中随机抽取一个，结合 `target_tags` 构造 Prompt，驱动 LLM 生成一道用业务外壳包裹算法本质的原创题，并要求 LLM 同步输出 Python 标准解。

`difficulty=hard` 时 temperature=0.7，否则 0.3。

**已知缺陷**：

- **核心算法库仅 7 个**，长期使用后重复率较高（期望约 14 次后开始出现重复算法外壳）。
- **标准解未经执行验证**：LLM 输出的 `std_solution` 直接存入 JSON，未运行任何样例校验，存在逻辑错误或语法错误的风险。
- `exclusion_list` 的过滤逻辑（字符串包含匹配）非常宽松，可能误排除不相关算法。

#### 3c. CodeSnippetGenerator — `core/code_snippet_generator.py`

单次 LLM 请求生成 `count`（默认 3）道手撕题，题目领域覆盖：LLM/Transformer 架构模块（多头注意力、位置编码、LayerNorm、因果掩码、KV Cache）、深度学习基础（Softmax、交叉熵损失、BatchNorm、Dropout）、强化学习基础（ε-贪心、Q-learning、PPO clip）、经典排序算法（快排、归并、堆排序）、经典 ML 算法（K-means、逻辑回归、余弦相似度）。

每道题包含 `title`、`desc`（函数签名 + 详细要求）、`hint`（思路提示，不泄漏答案）、`reference_impl`（可运行的 Python 参考实现，仅用于 LLM 批改，不展示给用户）、`tag`、`difficulty`。

LLM 调用失败时自动使用内置 3 道兜底题（Softmax 数值稳定版、原地快速排序、因果注意力掩码），保证试卷始终有内容。

#### 3d. MCQGenerator — `core/mcq_generator.py`

**`generate_batch(tags, count)`**（主路径，`cmd_run` 调用）：单次 LLM 请求生成 `count` 道题，要求覆盖全部 `tags`。按 1:1 比例分配题型：`count//2` 道学术理论题（`question_type: "academic"`），`count - count//2` 道业务场景应用题（`question_type: "business_scenario"`）。若 LLM 返回的 `question_type` 非法，按位置顺序兜底修正。

**`generate_mcqs(config_from_a)`**（次路径，逐 tag 调用）：每个 tag 单独发一次请求，生成 1 道题。实际在 `cmd_run` 中不使用，是早期接口，保留备用。

`correct_options` 数量校验：LLM 返回 > 3 个时截断，< 2 个时补 `["A","B"]`。

**Fallback tags**（当 Profiler 无有效标签时，随机取 2 个，共 16 个）：

```
并发与多线程、分布式锁与事务、数据库索引与调优、
RAG 与大模型基础、统计推断与A/B测试、高频交易系统架构、
缓存一致性协议、微服务熔断与限流、
网络协议与传输层、分布式数据一致性与状态管理、
强化学习与RLHF、大模型架构原理、大模型微调技术、
深度学习经典模型与算法（CNN/RNN/LSTM/ResNet/BN/Dropout/优化器）、
经典自然语言处理应用与对比（N-gram/HMM/CRF/TF-IDF/LDA/LSA/
  词向量/BERT vs GPT/NER/文本分类/机器翻译/交叉熵/BPC/BPW/困惑度）、
经典机器学习算法（决策树/随机森林/SVM/梯度提升/XGBoost/K-means/PCA/正则化）
```

**已知缺陷**：

- **不同批次间无去重**：3 个并发批次独立生成，同一道题可能从不同角度重复出现，尤其是 tags 列表较短时。
- **`correct_options` 补偿逻辑过于简单**：硬补 `["A","B"]` 不保证 A、B 选项实际正确，会导致错误的 ground truth。
- **题型分布 1:1 是 prompt 约束，非代码强制**：LLM 可能忽略指令，`generate_batch` 的兜底修正只按位置推断类型，不验证内容是否真的符合该类型。

---

### 4. Exam Formatter — `exam_formatter/services/formatter.py`

**`build_daily_exam(problem_set, output_dir)`**：将 `problem_set` dict 渲染为 Markdown 文件。

文件名格式：`Exam_YYYYMMDD_HHMMSS.md`（北京时间）。日期来自 `problem_set["exam_date"]`，时间来自调用时刻的系统时间。

MCQ 渲染：每题输出`**你的答案: [ ]**` 占位符，并在标题行附带 `[🎓 学术]` 或 `[🏭 业务场景]` 标签。

算法题渲染：注入代码脚手架（`_inject_boilerplate`），根据 `io_spec.type` 决定主函数模板（`single_test_case` 或 `multi_test_case`）。答案和标准解不写入 Markdown，仅存于 JSON。

手撕题渲染（第三部分）：在 `## 第三部分：算法模块手撕` 标题下，先输出一个**预制类定义代码块**（`ListNode`、`DListNode`、`TreeNode`、`NTreeNode`、`defaultdict` 图模板），然后逐题输出题目要求、思路提示和空白代码块。代码块使用 `# --- 题目 ID: snippet-xxx ---` 头注释，与算法题共用同一套 `CODE_REGEX` 解析，无需修改 parser。

**已知缺陷**：

- **无法防止用户误删占位符**：`grader/parser.py` 在提取到的 MCQ 数量与预期不符时会直接抛 `MarkdownFormatError`，体验较差，无任何提示修复路径。
- **`exam_date` 字段驱动文件日期，而非生成时刻**：若 `problem_set["exam_date"]` 是过去的日期（如手动构造数据），生成的文件名会反映旧日期，可能被 `grade` 的 `sorted(glob)[-1]` 错误排序。
- **纯字符串拼接无模板引擎**：Markdown 结构散落在列表里，维护性较差。

---

### 5. Grader — `grader/`

#### 5a. Parser — `parser.py`

两个预编译正则：

```python
import re
MCQ_REGEX  = re.compile(r"你的答案:\s*\[([A-Z,\s]*)\]")
CODE_REGEX = re.compile(r"# ---\s*题目 ID:\s*(.*?)\s*---\n*```python\n(.*?)\n```", re.DOTALL)
```

`MCQ_REGEX` 匹配用户填写的选项字符串（如 `A, C`），`CODE_REGEX` 按题目 ID 提取代码块。若 MCQ 数量不匹配则抛 `MarkdownFormatError`。

#### 5b. Evaluator — `evaluator.py`

**`score_mcq(user_ans_str, correct_options)`**：

| 情况 | 分值 |
|---|---|
| 全对 | 1.0 |
| 少选（用户选项 ⊂ 正确答案） | 0.33 |
| 错选/多选（含不在正确答案中的选项） | 0.0 |
| 未作答 | 0.0 |

**`evaluate_algorithm_with_llm(problem_desc, std_solution, user_code, llm_client)`**：

构造 Prompt，要求 LLM 从逻辑正确性（60分）、时间复杂度（20分）、工程质量（20分）三维评分，直接输出 0-100 整数，折算为 0.0-1.0。

**`evaluate_code_snippet_with_llm(title, desc, reference_impl, user_code, llm_client)`**：

专为手撕题设计的评分函数。空代码或仅有占位注释时直接返回 0.0。否则构造 Prompt 从三个维度评分：算法逻辑正确性（50分）、关键步骤完整性（30分）、代码质量（20分），输出 0-100 整数折算为 0.0-1.0。LLM 不可用时返回 0.0（不抛异常，避免整批批改中断）。

**已知缺陷**：

- **算法题未进行实际运行测试**：完全依赖 LLM 主观判断，无沙盒执行，无测试用例验证。LLM 对逻辑错误的代码可能给出过高分数。
- **LLM 评分输出解析极脆弱**：`float(response.strip())` 假设 LLM 只输出数字，任何解释性文字都会导致 `ValueError` 并抛 `LLMUnavailableError`，没有正则提取兜底。
- **`score_mcq` 少选固定 0.33**：不管少选了几个选项，分数都相同（选对 2/3 和选对 1/3 都是 0.33），粒度粗糙。
- **`grader.py` 读取 `mcq_meta["correct_options"]`**：直接 key 访问，若该字段缺失会 `KeyError` 崩溃，没有 `.get()` 防御。

---

### 5c. Report Generator — `profiler/core/report_gen.py`

读取 `mcq_stats.json`，生成 `data/learning_progress.md`，包含四个部分：

1. **全局统计**：已完成测试次数、已追踪知识点数、全局平均掌握度
2. **知识点分层**：按掌握度分为核心弱项（L < 30 或连错 ≥ 2）、巩固提升（30 ≤ L ≤ 80）、已掌握（L > 80）三层表格
3. **综合掌握情况评估**：根据平均掌握度输出四级定性评语（优秀 / 良好 / 中等 / 需加强），并列出知识点分布统计和最需优先复习的 Top-3 弱项
4. **错题复习日历**：读取 `wrong_history`，按日期降序分组，每组输出表格（题型 / 标签 / 题目文本前 60 字 / 得分图标），score = 0 显示 ❌，score < 0.5 显示 ⚠️，score < 1.0 显示 🔶

---

### 6. LLM Client — `problem_synthesizer/utils/llm_client.py`

封装 OpenAI 兼容接口，支持 `max_retries` 次指数退避重试。`base_url` 可配置，理论上兼容任何 OpenAI 格式 API（DeepSeek、Qwen 等）。

---

### 7. Server — `server/app.py`

基于 Flask 的单文件 Web 应用，提供两个路由：

- `GET /`：加载最新 `problem_set_*.json`，渲染 `exam.html`
- `POST /grade`：接收 JSON 格式的作答数据，构造临时 Markdown（`_build_temp_md`），调用 `grade_submission`，渲染 `result.html`，然后删除临时文件

`_get_latest_problem_set` 取 `sorted(glob(...))[-1]`，与 `cmd_grade` 逻辑一致——永远批改最新试卷，不支持历史试卷回溯。

**已知缺陷**：

- **无任何认证机制**：绑定 `127.0.0.1` 提供了网络层隔离，但若被 SSRF 或本机其他进程访问，所有数据完全暴露。
- **不支持多用户/多会话**：`_get_latest_problem_set` 全局共享，并发作答会相互覆盖。
- **`serve` 命令使用 Flask 开发服务器**（`debug=False` 但仍是单线程）：生产环境不可用，尽管这是本地工具，仍需注意并发问题。

---

## 并发模型

`cmd_run` 使用 `ThreadPoolExecutor` 并发提交所有 LLM 请求：

```
ThreadPoolExecutor(max_workers = num_batches + 2)
  ├── MathShellCoder.generate_problem()        ← 1 个线程
  ├── CodeSnippetGenerator.generate(3)         ← 1 个线程
  ├── MCQGenerator.generate_batch(tags, 4)     ← 线程 1
  ├── MCQGenerator.generate_batch(tags, 4)     ← 线程 2
  ├── MCQGenerator.generate_batch(tags, 4)     ← 线程 3
  ├── MCQGenerator.generate_batch(tags, 4)     ← 线程 4
  └── MCQGenerator.generate_batch(tags, 4)     ← 线程 5（如有余量）
```

`num_batches = ceil(20 / 4) = 5`，实际最多 7 个并发 LLM 请求。所有 Future 在 `with` 块退出时等待完成，结果在主线程中按 key 聚合（`algo` / `snippets` / `mcq_N`）。LLM Client 的重试逻辑运行在各自的工作线程内，不阻塞其他批次。

---

## 本地题库规范

`local_bank/` 下每个 `.py` 文件是一道算法题，文件名建议使用算法类型前缀（`dp_`、`graph_` 等）以使 tag 推断生效。文件结构约定：

```python
"""
题目名称：XXX（可选）

题目描述...

约束条件：1 <= n <= 10^5

Example:
Input: ...
Output: ...
"""

def solve():
    pass

if __name__ == "__main__":
    solve()
```

不符合约定时，`LocalBankExtractor` 会以文件名作为 title，desc 和 constraints 留空，不报错。
