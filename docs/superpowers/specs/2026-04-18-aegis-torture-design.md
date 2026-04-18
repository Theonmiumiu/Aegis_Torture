# Aegis Torture — 完整系统设计文档

**日期**: 2026-04-18  
**方案**: 方案 B（Schema 统一 + 干净集成）

---

## 1. 项目概述

Aegis Torture（拷打机器）是一个 AI 驱动的每日编程考试闭环系统，由四个子模块组成：

```
A(Profiler) → B(题目合成) → C(试卷排版) → 用户作答 → D(智能批改) → A(更新画像)
```

**目标**：通过 Epsilon-Greedy 算法动态调整知识点权重，在强化弱项的同时防止"刷题过拟合"，每日生成一套包含算法题和多选题的个性化试卷。

---

## 2. 整体架构

### 2.1 目录结构

```
aegis_torture/
├── .env                        # API Key、base_url、路径配置（不入库）
├── .env.example                # 配置模板（入库）
├── main.py                     # 唯一入口
├── config.py                   # 读取 .env，暴露全局 Settings 对象
├── schema.py                   # 所有模块共用的 TypedDict 数据契约
├── pyproject.toml              # 依赖声明
│
├── local_bank/                 # 用户存放 .py 算法题文件（见第 7 节）
├── data/                       # 自动生成：mcq_stats.json、problem_set_*.json
├── output/                     # 自动生成：Exam_*.md 试卷文件
│
├── profiler/
│   └── core/
│       ├── __init__.py
│       ├── profiler.py         # get_mcq_config, update_mcq_stats
│       └── report_gen.py       # generate_report
│
├── problem_synthesizer/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── local_extractor.py  # 本地题库抽取
│   │   ├── llm_coder.py        # Math-Shell 算法题生成
│   │   └── mcq_generator.py    # 多选题生成
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── templates.py        # 所有 LLM Prompt 模板（统一维护）
│   └── utils/
│       ├── __init__.py
│       └── llm_client.py       # 真实 OpenAI-compatible 客户端
│
├── exam_formatter/
│   └── services/
│       ├── __init__.py
│       └── formatter.py        # build_daily_exam
│
└── grader/
    ├── __init__.py
    ├── grader.py               # grade_submission
    ├── parser.py               # Markdown 答案提取
    ├── evaluator.py            # 判分逻辑
    └── exceptions.py
```

### 2.2 运行流程

**生成试卷**：
```
python main.py run
  1. 读取 .env 配置
  2. A: get_mcq_config(data/) → mcq_config
  3. B: generate_daily_problem_set(mcq_config, local_bank/) → problem_set
  4. 将 problem_set 存档到 data/problem_set_{YYYYMMDD}.json
  5. C: build_daily_exam(problem_set, output/) → exam_path
  6. 打印：试卷路径，提示填完后运行 grade
```

**批改试卷**：
```
python main.py grade
  1. 自动找 output/ 下最新 .md 及对应 data/problem_set_*.json
  2. D: grade_submission(md_path, problem_set_path) → report
  3. A: update_mcq_stats(report, data/)
  4. A: generate_report(data/) → data/learning_progress.md
  5. 打印本次得分摘要
```

**辅助命令**：
```
python main.py report   # 单独重新生成 learning_progress.md
```

---

## 3. 统一数据契约（schema.py）

所有模块通过此契约通信，消除接口错位。

```python
from typing import TypedDict, List, Dict

class IOSpec(TypedDict):
    type: str  # "single_test_case" | "multi_test_case"

class SampleIO(TypedDict):
    input: str
    output: str

class AlgorithmProblem(TypedDict):
    id: str                        # "algo-01", "algo-02", "algo-03"
    title: str
    desc: str
    constraints: str
    sample_io: List[SampleIO]
    io_spec: IOSpec
    std_solution: str              # 存入 JSON，不渲染进 Markdown
    tag: str                       # 供 D 模块反馈给 A（本地题从文件名推断）
    brief_description: str         # 供 A 模块 history_buffer 去重
    source: str                    # "local" | "llm_generated"

class MCQProblem(TypedDict):
    question_id: str
    tag: str
    text: str
    options: Dict[str, str]        # {"A": "...", "B": "...", "C": "...", "D": "..."}
    correct_options: List[str]     # ["A", "C"]，存入 JSON，不渲染进 Markdown
    explanation: str               # 存入 JSON，不渲染进 Markdown

class ProblemSet(TypedDict):
    exam_id: str
    exam_date: str                 # "2026-04-18"
    target_tags: List[str]
    algorithm_section: List[AlgorithmProblem]   # 统一键名
    mcq_section: List[MCQProblem]               # 统一键名
```

### 3.1 键名统一对照（修复前 → 修复后）

| 位置 | 修复前 | 修复后 |
|------|--------|--------|
| B 输出算法题列表 | `coding_problems` | `algorithm_section` |
| B 输出多选题列表 | `mcqs` | `mcq_section` |
| C 读取多选题 | `mcq_section` ✓ | 不变 |
| D 读取算法题 | `algorithm_section` ✓ | 不变 |
| D 读取多选题 | `mcqs` ✗ | 改为 `mcq_section` |

---

## 4. LLMClient 实现

### 4.1 .env 配置

```ini
# .env
LLM_API_KEY=sk-xxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 路径（可选，有默认值）
LOCAL_BANK_PATH=./local_bank
DATA_PATH=./data
OUTPUT_PATH=./output
```

### 4.2 config.py

用 `python-dotenv` 加载 .env，暴露全局 `Settings` 对象：

```python
from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))
    local_bank_path: str = field(default_factory=lambda: os.getenv("LOCAL_BANK_PATH", "./local_bank"))
    data_path: str = field(default_factory=lambda: os.getenv("DATA_PATH", "./data"))
    output_path: str = field(default_factory=lambda: os.getenv("OUTPUT_PATH", "./output"))

settings = Settings()
```

### 4.3 LLMClient 核心实现

基于 `openai` SDK，保留现有指数退避 + Jitter 逻辑，替换底层 HTTP 实现：

```python
from openai import OpenAI

class LLMClient:
    def __init__(self, api_key, base_url, model, max_retries=3):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_retries = max_retries

    def generate_text(self, prompt: str, temperature: float = 0.5) -> str:
        # 指数退避重试逻辑保留（见现有实现），底层改为：
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=2048,
        )
        return response.choices[0].message.content
```

---

## 5. Bug 修复清单

| # | 文件 | 行号 | 问题描述 | 修复方式 |
|---|------|------|----------|----------|
| 1 | `grader/evaluator.py` | L69 | `llm_client.ask(prompt)` 方法不存在 | 改为 `llm_client.generate_text(prompt)` |
| 2 | `grader/grader.py` | L46 | 调用 `evaluate_algorithm_with_llm` 未传 `llm_client` | 在 `grade_submission` 签名中接收并传入 `llm_client` |
| 3 | `grader/` | — | 无 `__init__.py`，相对 import 失败 | 新增 `grader/__init__.py` |
| 4 | `problem_synthesizer/core/` | — | 无 `__init__.py` | 新增 `problem_synthesizer/core/__init__.py` |
| 5 | `mcq_generator.py` | L98 | 强制 `correct_options[:2]` 截断，破坏 3 正确答案题目 | 改为仅记录警告，不截断；保持 2-3 个正确选项的校验逻辑 |
| 6 | `pyproject.toml` | — | 无依赖声明 | 添加 `openai >= 1.0`, `python-dotenv >= 1.0` |
| 7 | `llm_coder.py` / `mcq_generator.py` | — | Prompt 内嵌，与 `templates.py` 重复 | 改为从 `templates.py` 导入使用 |
| 8 | `problem_synthesizer/main.py` | L65 | 输出键 `coding_problems`/`mcqs` | 统一改为 `algorithm_section`/`mcq_section` |
| 9 | `local_extractor.py` | — | 本地题目缺 `id`、`tag`、`brief_description` 字段 | 抽样后自动补充：`id` 按序号，`tag` 从文件名推断，`brief_description` 取 desc 前 50 字 |
| 10 | `grader/grader.py` | L42 | 读取 `problem_set.get("algorithm_section")` 中字段 `algo_meta["tag"]` 可能不存在 | schema 统一后字段必存在，加默认值兜底 |
| 11 | `local_extractor.py` | L40 | `io_spec` 存为 `{"example": "raw text"}`，不符合 schema 的 `List[SampleIO]` | 解析 Example 块，拆分为 `{"input": ..., "output": ...}` 列表；`io_spec.type` 默认 `"single_test_case"` |

---

## 6. 编排入口（main.py）

```python
# main.py（根目录）
import sys
from config import settings
# ... 导入各模块

COMMANDS = ["run", "grade", "report"]

def cmd_run(): ...
def cmd_grade(): ...
def cmd_report(): ...

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":    cmd_run()
    elif cmd == "grade": cmd_grade()
    elif cmd == "report": cmd_report()
    else:
        print(f"用法: python main.py [run|grade|report]")
```

`grade` 的自动匹配逻辑：扫描 `output/` 找最新 `.md`，从文件名提取日期（`Exam_YYYYMMDD.md`），在 `data/` 找 `problem_set_YYYYMMDD.json`。

---

## 7. 本地题库格式规范

文件存放路径：`local_bank/*.py`

每个文件格式：

```python
"""
题目名称：两数之和变体

给定一个整数数组 nums 和目标值 target，在数组中找出和为目标值的两个整数下标。
每种输入只对应一个答案，且同一元素不能重复使用。

约束条件：2 <= nums.length <= 10^4，-10^9 <= nums[i] <= 10^9

Example:
Input:
4 9
2 7 11 15
Output:
0 1
"""
import sys

def solve():
    line1 = sys.stdin.readline().split()
    n, target = int(line1[0]), int(line1[1])
    nums = list(map(int, sys.stdin.readline().split()))
    seen = {}
    for i, v in enumerate(nums):
        if target - v in seen:
            print(seen[target - v], i)
            return
        seen[v] = i

if __name__ == "__main__":
    solve()
```

**解析规则**：
- 文件名（去 `.py`）作为题目标识符
- Docstring 第一行（`题目名称：...`）作为 `title`；若无该前缀，整个第一行作为 title
- `Example:` 之前、`约束条件：` 之前的内容作为 `desc`
- `约束条件：` 所在行的内容作为 `constraints`；若不存在则为空字符串
- `Example:` 之后的内容解析为 `sample_io`：按 `Input:` / `Output:` 拆分，构造 `List[{"input": str, "output": str}]`
- `io_spec.type` 默认为 `"single_test_case"`
- 整个文件内容作为 `std_solution`
- `tag` 默认为 `"Algorithm"`（未来可通过文件名前缀约定扩展，如 `dp_coin_change.py` → tag `"DP"`）

---

## 8. 依赖清单

```toml
# pyproject.toml
dependencies = [
    "openai>=1.0",
    "python-dotenv>=1.0",
]
```

---

*本文档由 Claude Code 辅助生成，经用户逐节确认。*
