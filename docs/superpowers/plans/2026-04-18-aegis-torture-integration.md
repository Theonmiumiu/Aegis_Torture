# Aegis Torture Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将四个已有的子模块（Profiler、Problem Synthesizer、Exam Formatter、Grader）通过统一的数据契约和根目录编排入口连接成一个可运行的闭环系统，同时修复所有已知 Bug 并接入真实 LLM。

**Architecture:** 根目录新增 `schema.py`（统一数据契约）、`config.py`（.env 配置加载）、`main.py`（run/grade/report 三命令编排）。各子模块在不重写的前提下做最小改动：修复 Bug、统一键名、补充缺失字段、用 `openai` SDK 替换 Mock。

**Tech Stack:** Python 3.13, `openai >= 1.0`（OpenAI-compatible client），`python-dotenv >= 1.0`，`pytest`（测试），`uv`（虚拟环境与依赖管理）

---

## 文件结构总览

**新建文件：**
- `schema.py` — 所有模块的 TypedDict 数据契约
- `config.py` — 从 .env 加载全局 Settings
- `.env.example` — 配置模板（入库）
- `main.py` — 根目录编排入口
- `grader/__init__.py` — 使相对 import 生效
- `problem_synthesizer/core/__init__.py` — 使包导入生效
- `profiler/__init__.py` — 使根目录绝对导入生效
- `profiler/tests/__init__.py` — pytest 发现测试用
- `tests/__init__.py` — 根目录测试包
- `tests/test_schema.py`
- `tests/test_config.py`
- `tests/test_llm_client.py`
- `tests/test_local_extractor.py`
- `tests/test_mcq_generator.py`
- `tests/test_evaluator.py`
- `tests/test_formatter.py`
- `tests/test_grader_integration.py`

**修改文件：**
- `pyproject.toml` — 添加 openai、python-dotenv 依赖
- `problem_synthesizer/utils/llm_client.py` — 替换 Mock 为真实 openai SDK
- `problem_synthesizer/core/local_extractor.py` — 修复 sample_io 解析，补充 id/tag/brief_description
- `problem_synthesizer/core/mcq_generator.py` — 修复 correct_options 截断 Bug，改用 templates.py
- `problem_synthesizer/core/llm_coder.py` — 更新输出 schema，改用 templates.py
- `problem_synthesizer/prompts/templates.py` — 更新 MATH_SHELL prompt 以输出新字段
- `grader/evaluator.py` — 修复 `llm_client.ask()` → `generate_text()`
- `grader/grader.py` — 修复 `"mcqs"` → `"mcq_section"`，接收并传递 llm_client

---

## Task 1: 项目基础设施

**Files:**
- Create: `pyproject.toml`（修改）
- Create: `.env.example`
- Create: `schema.py`
- Create: `config.py`
- Create: `grader/__init__.py`
- Create: `problem_synthesizer/core/__init__.py`
- Create: `profiler/__init__.py`
- Create: `profiler/tests/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_schema.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 更新 pyproject.toml 添加依赖**

将 `pyproject.toml` 改为：

```toml
[project]
name = "aegis-torture"
version = "0.1.0"
description = "AI-powered daily coding exam system"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "openai>=1.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]
```

- [ ] **Step 2: 安装依赖**

```bash
uv sync --extra dev
```

预期输出：包含 `Resolved ... packages` 并安装 openai、python-dotenv、pytest

- [ ] **Step 3: 创建 .env.example**

```ini
# .env.example
# 复制此文件为 .env 并填入真实值

# LLM 配置（必填）
LLM_API_KEY=sk-xxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 路径配置（可选，有默认值）
LOCAL_BANK_PATH=./local_bank
DATA_PATH=./data
OUTPUT_PATH=./output
```

- [ ] **Step 4: 写 test_schema.py 的失败测试**

创建 `tests/__init__.py`（空文件），然后创建 `tests/test_schema.py`：

```python
def test_schema_imports():
    from schema import ProblemSet, AlgorithmProblem, MCQProblem, IOSpec, SampleIO
    assert ProblemSet is not None

def test_algorithm_problem_has_required_fields():
    from schema import AlgorithmProblem
    p: AlgorithmProblem = {
        "id": "algo-01",
        "title": "Test",
        "desc": "description",
        "constraints": "1 <= n <= 100",
        "sample_io": [{"input": "3", "output": "6"}],
        "io_spec": {"type": "single_test_case"},
        "std_solution": "def solve(): pass",
        "tag": "Algorithm",
        "brief_description": "short desc",
        "source": "local",
    }
    assert p["id"] == "algo-01"
    assert p["source"] == "local"

def test_mcq_problem_has_required_fields():
    from schema import MCQProblem
    q: MCQProblem = {
        "question_id": "uuid-1",
        "tag": "Concurrency",
        "text": "关于 asyncio？",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "C"],
        "explanation": "解析...",
    }
    assert q["correct_options"] == ["A", "C"]
```

- [ ] **Step 5: 运行测试，确认失败（schema.py 不存在）**

```bash
uv run pytest tests/test_schema.py -v
```

预期：`ModuleNotFoundError: No module named 'schema'`

- [ ] **Step 6: 创建 schema.py**

```python
from typing import TypedDict, List, Dict


class IOSpec(TypedDict):
    type: str  # "single_test_case" | "multi_test_case"


class SampleIO(TypedDict):
    input: str
    output: str


class AlgorithmProblem(TypedDict):
    id: str
    title: str
    desc: str
    constraints: str
    sample_io: List[SampleIO]
    io_spec: IOSpec
    std_solution: str
    tag: str
    brief_description: str
    source: str  # "local" | "llm_generated"


class MCQProblem(TypedDict):
    question_id: str
    tag: str
    text: str
    options: Dict[str, str]
    correct_options: List[str]
    explanation: str


class ProblemSet(TypedDict):
    exam_id: str
    exam_date: str
    target_tags: List[str]
    algorithm_section: List[AlgorithmProblem]
    mcq_section: List[MCQProblem]
```

- [ ] **Step 7: 运行测试，确认通过**

```bash
uv run pytest tests/test_schema.py -v
```

预期：`3 passed`

- [ ] **Step 8: 写 test_config.py 的失败测试**

创建 `tests/test_config.py`：

```python
import os

def test_settings_has_default_values(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    import importlib
    import config as cfg
    importlib.reload(cfg)

    assert cfg.settings.base_url == "https://api.openai.com/v1"
    assert cfg.settings.model == "gpt-4o"
    assert cfg.settings.data_path == "./data"
    assert cfg.settings.output_path == "./output"
    assert cfg.settings.local_bank_path == "./local_bank"

def test_settings_reads_from_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")

    import importlib
    import config as cfg
    importlib.reload(cfg)

    assert cfg.settings.api_key == "sk-test-key"
    assert cfg.settings.base_url == "https://api.deepseek.com/v1"
    assert cfg.settings.model == "deepseek-chat"
```

- [ ] **Step 9: 运行测试，确认失败**

```bash
uv run pytest tests/test_config.py -v
```

预期：`ModuleNotFoundError: No module named 'config'`

- [ ] **Step 10: 创建 config.py**

```python
from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    )
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))
    local_bank_path: str = field(
        default_factory=lambda: os.getenv("LOCAL_BANK_PATH", "./local_bank")
    )
    data_path: str = field(default_factory=lambda: os.getenv("DATA_PATH", "./data"))
    output_path: str = field(
        default_factory=lambda: os.getenv("OUTPUT_PATH", "./output")
    )


settings = Settings()
```

- [ ] **Step 11: 创建所有缺失的 __init__.py 文件**

依次创建以下空文件：

```
grader/__init__.py
problem_synthesizer/core/__init__.py
profiler/__init__.py
profiler/tests/__init__.py
```

每个文件内容均为空（0 字节）。

- [ ] **Step 12: 运行所有测试，确认通过**

```bash
uv run pytest tests/test_schema.py tests/test_config.py -v
```

预期：`5 passed`

- [ ] **Step 13: Commit**

```bash
git add pyproject.toml .env.example schema.py config.py \
    grader/__init__.py problem_synthesizer/core/__init__.py \
    profiler/__init__.py profiler/tests/__init__.py \
    tests/__init__.py tests/test_schema.py tests/test_config.py
git commit -m "feat: add project foundation (schema, config, __init__ files)"
```

---

## Task 2: 真实 LLMClient 实现

**Files:**
- Modify: `problem_synthesizer/utils/llm_client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_llm_client.py`：

```python
from unittest.mock import MagicMock, patch


def test_generate_text_success():
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "test response"
        mock_openai_cls.return_value.chat.completions.create.return_value = mock_response

        from problem_synthesizer.utils.llm_client import LLMClient
        client = LLMClient(api_key="test", base_url="http://test", model="test-model")
        result = client.generate_text("hello")

    assert result == "test response"


def test_generate_text_retries_on_failure():
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok after retry"
        create_mock = mock_openai_cls.return_value.chat.completions.create
        create_mock.side_effect = [ConnectionError("network fail"), mock_response]

        with patch("time.sleep"):
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=3)
            result = client.generate_text("hello")

    assert result == "ok after retry"
    assert create_mock.call_count == 2


def test_generate_text_raises_after_max_retries():
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        create_mock = mock_openai_cls.return_value.chat.completions.create
        create_mock.side_effect = ConnectionError("always fails")

        with patch("time.sleep"):
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=2)
            try:
                client.generate_text("hello")
                assert False, "应该抛出 RuntimeError"
            except RuntimeError as e:
                assert "多次调用失败" in str(e)
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
uv run pytest tests/test_llm_client.py -v
```

预期：`ImportError` 或测试失败（因为当前 LLMClient 没有 `openai` 导入）

- [ ] **Step 3: 重写 problem_synthesizer/utils/llm_client.py**

```python
import time
import random
import logging
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM 客户端封装，支持所有 OpenAI-compatible 接口。
    内置带 Jitter 的指数退避重试机制。
    """

    def __init__(self, api_key: str, base_url: str, model: str, max_retries: int = 3):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_retries = max_retries

    def generate_text(self, prompt: str, temperature: float = 0.5) -> str:
        """发送 Prompt 并获取文本回复，包含指数退避重试逻辑。"""
        retries = 0
        base_delay = 2.0

        while retries <= self.max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=2048,
                )
                return response.choices[0].message.content

            except Exception as e:
                retries += 1
                if retries > self.max_retries:
                    logger.error(
                        f"LLM API 达到最大重试次数 ({self.max_retries})，任务最终失败。Error: {e}"
                    )
                    raise RuntimeError(f"LLM 接口多次调用失败: {str(e)}") from e

                delay = base_delay * (2 ** (retries - 1)) + random.uniform(0, 1.0)
                logger.warning(
                    f"LLM API 调用异常: {e}。等待 {delay:.2f}s 后进行第 {retries} 次重试..."
                )
                time.sleep(delay)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
uv run pytest tests/test_llm_client.py -v
```

预期：`3 passed`

- [ ] **Step 5: Commit**

```bash
git add problem_synthesizer/utils/llm_client.py tests/test_llm_client.py
git commit -m "feat: replace mock LLMClient with real openai-compatible implementation"
```

---

## Task 3: 修复 local_extractor

**Files:**
- Modify: `problem_synthesizer/core/local_extractor.py`
- Create: `tests/test_local_extractor.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_local_extractor.py`：

```python
import tempfile
import os
import pytest


PROBLEM_CONTENT = '''\
"""
题目名称：环形前缀和

给定一个长度为 $n$ 的整数数组，对每个查询 $[l, r]$ 输出区间和。
输入数据量大，需使用前缀和优化。

约束条件：1 <= n <= 2 * 10^5，1 <= q <= 10^5

Example:
Input:
5 3
1 2 3 4 5
1 3
2 4
1 5
Output:
6
9
15
"""
import sys

def solve():
    pass

if __name__ == "__main__":
    solve()
'''

PROBLEM_NO_CONSTRAINTS = '''\
"""
简单的两数之和。

Example:
Input:
2
Output:
3
"""
def solve(): pass
'''


def _make_bank(tmpdir, files):
    for name, content in files.items():
        with open(os.path.join(tmpdir, name), "w", encoding="utf-8") as f:
            f.write(content)


def test_sample_problems_returns_correct_count():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {
            "prob_a.py": PROBLEM_CONTENT,
            "prob_b.py": PROBLEM_CONTENT,
            "prob_c.py": PROBLEM_CONTENT,
        })
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=2)

    assert len(problems) == 2


def test_sample_problems_has_required_fields():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {"p1.py": PROBLEM_CONTENT, "p2.py": PROBLEM_CONTENT})
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=2)

    for i, p in enumerate(problems):
        assert p["id"] == f"algo-{i+1:02d}"
        assert p["source"] == "local"
        assert isinstance(p["sample_io"], list)
        assert "input" in p["sample_io"][0]
        assert "output" in p["sample_io"][0]
        assert p["constraints"] != ""
        assert "io_spec" in p
        assert "tag" in p
        assert "brief_description" in p


def test_sample_problems_extracts_title():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {"p1.py": PROBLEM_CONTENT, "p2.py": PROBLEM_CONTENT})
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=1)

    assert problems[0]["title"] == "环形前缀和"


def test_sample_problems_without_constraints():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {"p1.py": PROBLEM_NO_CONSTRAINTS, "p2.py": PROBLEM_NO_CONSTRAINTS})
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=1)

    assert problems[0]["constraints"] == ""


def test_sample_problems_raises_when_bank_too_small():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {"p1.py": PROBLEM_CONTENT})
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        with pytest.raises(ValueError, match="本地题库数量不足"):
            extractor.sample_problems(count=2)


def test_tag_inferred_from_filename_prefix():
    with tempfile.TemporaryDirectory() as d:
        _make_bank(d, {
            "dp_coin_change.py": PROBLEM_CONTENT,
            "dp_other.py": PROBLEM_CONTENT,
        })
        from problem_synthesizer.core.local_extractor import LocalBankExtractor
        extractor = LocalBankExtractor(d)
        problems = extractor.sample_problems(count=2)

    for p in problems:
        assert p["tag"] == "DP"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
uv run pytest tests/test_local_extractor.py -v
```

预期：多项失败（缺少 `id`, `sample_io` 为 dict 而非 list 等）

- [ ] **Step 3: 重写 problem_synthesizer/core/local_extractor.py**

```python
import os
import random
import glob
import ast
from typing import List, Dict, Any


_TAG_PREFIXES = {
    "dp_": "DP",
    "graph_": "Graph",
    "tree_": "Tree",
    "sort_": "Sorting",
    "search_": "Search",
    "string_": "String",
    "math_": "Math",
    "greedy_": "Greedy",
    "binary_": "BinarySearch",
}


def _infer_tag(filename: str) -> str:
    lower = filename.lower()
    for prefix, tag in _TAG_PREFIXES.items():
        if lower.startswith(prefix):
            return tag
    return "Algorithm"


def _parse_example_block(example_text: str) -> Dict[str, str]:
    """将 Example 块解析为 {"input": ..., "output": ...}。"""
    text = example_text.strip()
    if "Input:" in text and "Output:" in text:
        after_input = text.split("Input:", 1)[1]
        parts = after_input.split("Output:", 1)
        return {
            "input": parts[0].strip(),
            "output": parts[1].strip(),
        }
    return {"input": text, "output": ""}


class LocalBankExtractor:
    """从指定目录无偏见地随机抽取已有算法题。"""

    def __init__(self, local_bank_path: str):
        self.local_bank_path = local_bank_path
        self.file_pool = glob.glob(
            os.path.join(self.local_bank_path, "**", "*.py"), recursive=True
        )

    def _parse_algorithm_file(self, file_path: str, problem_id: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        filename = os.path.basename(file_path).replace(".py", "")

        try:
            tree = ast.parse(content)
            docstring = ast.get_docstring(tree) or ""
        except Exception:
            docstring = ""

        title = filename
        desc = ""
        constraints = ""
        sample_io = []

        if docstring:
            lines = docstring.split("\n")
            first_line = lines[0].strip()

            # 提取题目名称
            for prefix in ("题目名称：", "题目名称:"):
                if first_line.startswith(prefix):
                    title = first_line[len(prefix):].strip()
                    break

            # 分割 Example 块
            if "Example:" in docstring:
                before_example, example_part = docstring.split("Example:", 1)
                sample = _parse_example_block(example_part)
                if sample["input"] or sample["output"]:
                    sample_io = [sample]
            else:
                before_example = docstring

            # 提取约束条件
            for marker in ("约束条件：", "约束条件:"):
                if marker in before_example:
                    desc_part, rest = before_example.split(marker, 1)
                    constraints = rest.strip().split("\n")[0].strip()
                    desc = desc_part.strip()
                    break
            else:
                desc = before_example.strip()

            # 去掉 desc 开头的题目名称行
            if desc.startswith(first_line):
                desc = "\n".join(desc.split("\n")[1:]).strip()

        tag = _infer_tag(filename)
        brief_description = (desc[:50] if desc else filename)

        return {
            "id": problem_id,
            "title": title,
            "desc": desc,
            "constraints": constraints,
            "sample_io": sample_io,
            "io_spec": {"type": "single_test_case"},
            "std_solution": content,
            "tag": tag,
            "brief_description": brief_description,
            "source": "local",
        }

    def sample_problems(self, count: int = 2) -> List[Dict[str, Any]]:
        """完全随机抽样，保证每题被选中概率为 count/N。"""
        total = len(self.file_pool)
        if total < count:
            raise ValueError(
                f"本地题库数量不足！需要 {count} 题，但仅找到 {total} 题。"
            )

        selected = random.sample(self.file_pool, count)
        return [
            self._parse_algorithm_file(fp, f"algo-{i+1:02d}")
            for i, fp in enumerate(selected)
        ]
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
uv run pytest tests/test_local_extractor.py -v
```

预期：`6 passed`

- [ ] **Step 5: Commit**

```bash
git add problem_synthesizer/core/local_extractor.py tests/test_local_extractor.py
git commit -m "fix: rewrite local_extractor to output unified schema with id/tag/sample_io"
```

---

## Task 4: 修复 mcq_generator + 使用 templates

**Files:**
- Modify: `problem_synthesizer/core/mcq_generator.py`
- Modify: `problem_synthesizer/prompts/templates.py`（确认 MCQ_PROMPT_TEMPLATE 正确）
- Create: `tests/test_mcq_generator.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_mcq_generator.py`：

```python
from unittest.mock import MagicMock


def _make_gen():
    from problem_synthesizer.core.mcq_generator import MCQGenerator
    mock_client = MagicMock()
    return MCQGenerator(mock_client), mock_client


def test_three_correct_options_not_truncated():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "关于 Python GIL？",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "B", "C"],
        "explanation": "解析..."
    }]'''

    mcqs = gen.generate_mcqs({"target_tags": ["Concurrency"]})

    assert len(mcqs) == 1
    assert len(mcqs[0]["correct_options"]) == 3, "3 个正确答案不应被截断"


def test_four_correct_options_clamped_to_three():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "Q?",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "B", "C", "D"],
        "explanation": "..."
    }]'''

    mcqs = gen.generate_mcqs({"target_tags": ["TCP"]})

    assert len(mcqs[0]["correct_options"]) == 3


def test_fallback_tags_used_when_target_tags_empty():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "Q?",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "B"],
        "explanation": "..."
    }]'''

    mcqs = gen.generate_mcqs({"target_tags": []})

    assert len(mcqs) > 0


def test_uses_template_for_prompt():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "Q?",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_options": ["A", "C"],
        "explanation": "..."
    }]'''

    gen.generate_mcqs({"target_tags": ["RAG"]})

    call_args = mock_client.generate_text.call_args
    prompt = call_args[0][0]
    assert "RAG" in prompt
    assert "2 到 3 个正确选项" in prompt
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
uv run pytest tests/test_mcq_generator.py -v
```

预期：`test_three_correct_options_not_truncated` 失败（当前代码截断为 2 个）

- [ ] **Step 3: 确认 templates.py 中 MCQ_PROMPT_TEMPLATE 内容正确**

打开 `problem_synthesizer/prompts/templates.py`，确认 `MCQ_PROMPT_TEMPLATE` 包含 `{tag}` 和 `{count}` 占位符，且含有 `"2 到 3 个正确选项"` 文字。内容应与现有文件一致（无需修改）。

- [ ] **Step 4: 修改 problem_synthesizer/core/mcq_generator.py**

将 `_build_prompt` 方法改为从 templates 导入，并修复 `correct_options` 截断逻辑：

在文件顶部添加导入：
```python
from problem_synthesizer.prompts.templates import MCQ_PROMPT_TEMPLATE
```

将 `_build_prompt` 方法替换为：
```python
def _build_prompt(self, tag: str, count: int) -> str:
    return MCQ_PROMPT_TEMPLATE.format(tag=tag, count=count).strip()
```

将 `generate_mcqs` 方法中的截断逻辑（第 94-98 行附近）替换为：
```python
correct_count = len(mcq.get("correct_options", []))
if correct_count > 3:
    import logging
    logging.getLogger(__name__).warning(
        f"LLM 为 {tag} 返回了 {correct_count} 个正确选项（期望 2-3），截断至 3 个"
    )
    mcq["correct_options"] = mcq["correct_options"][:3]
elif correct_count < 2:
    import logging
    logging.getLogger(__name__).warning(
        f"LLM 为 {tag} 返回了 {correct_count} 个正确选项（期望 2-3），使用默认值"
    )
    mcq["correct_options"] = (mcq.get("correct_options") or []) + ["A", "B"]
    mcq["correct_options"] = mcq["correct_options"][:2]
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
uv run pytest tests/test_mcq_generator.py -v
```

预期：`4 passed`

- [ ] **Step 6: Commit**

```bash
git add problem_synthesizer/core/mcq_generator.py tests/test_mcq_generator.py
git commit -m "fix: correct_options truncation bug + use templates for MCQ prompt"
```

---

## Task 5: 修复 llm_coder + 更新 templates

**Files:**
- Modify: `problem_synthesizer/prompts/templates.py`
- Modify: `problem_synthesizer/core/llm_coder.py`

注意：此任务修改 Prompt 输出格式以匹配 schema，LLM 的实际输出不可完全预测，因此用 mock 测试解析逻辑，不测 LLM 内容。

- [ ] **Step 1: 更新 templates.py 中的 MATH_SHELL_PROMPT_TEMPLATE**

将 `MATH_SHELL_PROMPT_TEMPLATE` 的 JSON 格式要求部分替换为：

```python
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
```

- [ ] **Step 2: 修改 llm_coder.py 使用新 template 并补全输出字段**

在文件顶部添加导入：
```python
from problem_synthesizer.prompts.templates import MATH_SHELL_PROMPT_TEMPLATE
```

将 `_build_prompt` 方法替换为：
```python
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
```

在 `generate_problem` 方法的 `problem_data = json.loads(clean_json_str)` 之后，替换后续的字段补齐逻辑为：

```python
# 将 LLM 输出的 io_spec_type 转换为 schema 要求的 io_spec 字段
io_spec_type = problem_data.pop("io_spec_type", "single_test_case")
problem_data["io_spec"] = {"type": io_spec_type}

# 补齐 schema 必需字段
problem_data.setdefault("constraints", "")
problem_data.setdefault("sample_io", [])

# 从 target_tags 推断 tag（取第一个，若无则默认）
problem_data["tag"] = target_tags[0] if target_tags else "Algorithm"
desc = problem_data.get("desc", "")
problem_data["brief_description"] = desc[:50] if desc else problem_data.get("title", "")[:50]
problem_data["source"] = "llm_generated"
```

同时更新 fallback 返回值（json.JSONDecodeError 捕获块）：
```python
return {
    "id": "algo-03",
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
```

- [ ] **Step 3: 运行已有测试，确认无回归**

```bash
uv run pytest tests/ -v
```

预期：所有已通过的测试仍然通过

- [ ] **Step 4: Commit**

```bash
git add problem_synthesizer/prompts/templates.py problem_synthesizer/core/llm_coder.py
git commit -m "fix: update llm_coder to output unified schema + use MATH_SHELL_PROMPT_TEMPLATE"
```

---

## Task 6: 修复 grader 模块

**Files:**
- Modify: `grader/evaluator.py`
- Modify: `grader/grader.py`
- Create: `tests/test_evaluator.py`
- Create: `tests/test_grader_integration.py`

- [ ] **Step 1: 写 evaluator 的失败测试**

创建 `tests/test_evaluator.py`：

```python
from grader.evaluator import score_mcq


def test_score_mcq_perfect():
    assert score_mcq("A, C", ["A", "C"]) == 1.0


def test_score_mcq_partial_one_of_two():
    assert score_mcq("A", ["A", "C"]) == 0.33


def test_score_mcq_wrong_selection():
    assert score_mcq("B", ["A", "C"]) == 0.0


def test_score_mcq_mixed_wrong_and_right():
    assert score_mcq("A, B", ["A", "C"]) == 0.0


def test_score_mcq_empty_answer():
    assert score_mcq("", ["A", "C"]) == 0.0


def test_score_mcq_all_options_wrong():
    assert score_mcq("D", ["A", "B", "C"]) == 0.0


def test_evaluate_algorithm_calls_generate_text():
    from unittest.mock import MagicMock
    from grader.evaluator import evaluate_algorithm_with_llm

    mock_client = MagicMock()
    mock_client.generate_text.return_value = "85"

    score = evaluate_algorithm_with_llm(
        problem_desc="题目描述",
        std_solution="def solve(): pass",
        user_code="def solve(): return 1",
        llm_client=mock_client,
    )

    assert score == 0.85
    mock_client.generate_text.assert_called_once()
    prompt_used = mock_client.generate_text.call_args[0][0]
    assert "题目描述" in prompt_used
```

- [ ] **Step 2: 运行测试，确认 test_evaluate_algorithm_calls_generate_text 失败**

```bash
uv run pytest tests/test_evaluator.py -v
```

预期：`test_evaluate_algorithm_calls_generate_text` 失败（因 `llm_client.ask()` 不存在）

- [ ] **Step 3: 修复 grader/evaluator.py**

将 `evaluate_algorithm_with_llm` 函数中第 69 行附近的 `llm_client.ask(prompt)` 改为 `llm_client.generate_text(prompt)`：

```python
if llm_client:
    response = llm_client.generate_text(prompt)  # 修复：ask -> generate_text
    score = float(response.strip())
```

- [ ] **Step 4: 运行测试，确认 evaluator 全部通过**

```bash
uv run pytest tests/test_evaluator.py -v
```

预期：`7 passed`

- [ ] **Step 5: 写 grader 集成测试**

创建 `tests/test_grader_integration.py`：

```python
import tempfile
import os
import json
from unittest.mock import MagicMock


MOCK_PROBLEM_SET = {
    "mcq_section": [
        {
            "question_id": "q1",
            "tag": "TCP",
            "text": "关于 TCP 三次握手？",
            "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "correct_options": ["A", "C"],
            "explanation": "解析...",
            "brief_description": "TCP 握手题",
        }
    ],
    "algorithm_section": [],
}

MD_WITH_CORRECT_ANSWER = """\
## 第一部分：多项选择题 (MCQs)

### 1. 关于 TCP 三次握手？ [标签: TCP]
- **A**: a
- **B**: b
- **C**: c
- **D**: d

**你的答案: [A, C]**

"""

MD_WITH_WRONG_ANSWER = """\
## 第一部分：多项选择题 (MCQs)

### 1. 关于 TCP 三次握手？ [标签: TCP]
- **A**: a

**你的答案: [B]**

"""


def _write_temp(d, ps, md):
    ps_path = os.path.join(d, "ps.json")
    md_path = os.path.join(d, "exam.md")
    with open(ps_path, "w", encoding="utf-8") as f:
        json.dump(ps, f)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    return md_path, ps_path


def test_grade_submission_correct_answer():
    with tempfile.TemporaryDirectory() as d:
        md_path, ps_path = _write_temp(d, MOCK_PROBLEM_SET, MD_WITH_CORRECT_ANSWER)
        from grader.grader import grade_submission
        report = grade_submission(md_path, ps_path)

    assert len(report) == 1
    assert report[0]["score"] == 1.0
    assert report[0]["tag"] == "TCP"


def test_grade_submission_wrong_answer():
    with tempfile.TemporaryDirectory() as d:
        md_path, ps_path = _write_temp(d, MOCK_PROBLEM_SET, MD_WITH_WRONG_ANSWER)
        from grader.grader import grade_submission
        report = grade_submission(md_path, ps_path)

    assert report[0]["score"] == 0.0
```

- [ ] **Step 6: 运行测试，确认失败（grader.py 使用 "mcqs" 键）**

```bash
uv run pytest tests/test_grader_integration.py -v
```

预期：测试失败（`mcq_section` 下有数据，但 grader 读 `"mcqs"` 键，返回空列表）

- [ ] **Step 7: 修复 grader/grader.py**

1. 修改函数签名，接收可选的 `llm_client` 参数：
```python
def grade_submission(
    md_file_path: str,
    problem_set_json_path: str,
    llm_client=None,
) -> List[Dict[str, Any]]:
```

2. 将 `problem_set.get("mcqs", [])` 改为 `problem_set.get("mcq_section", [])`（第 31 行附近）：
```python
for idx, mcq_meta in enumerate(problem_set.get("mcq_section", [])):
```

3. 将 `evaluate_algorithm_with_llm` 调用改为传入 `llm_client`（第 46 行附近）：
```python
score = evaluate_algorithm_with_llm(
    problem_desc=algo_meta["description"] if "description" in algo_meta else algo_meta.get("desc", ""),
    std_solution=algo_meta.get("std_solution", ""),
    user_code=user_code,
    llm_client=llm_client,
)
```

4. 修复 `brief_description` 字段（算法题的 brief_description 可能用 `desc` 而非 `brief_description`）：
```python
report_data.append({
    "tag": algo_meta.get("tag", "Algorithm"),
    "score": score,
    "brief_description": algo_meta.get("brief_description", algo_meta.get("desc", f"Algo-{algo_id}")[:50]),
})
```

- [ ] **Step 8: 运行所有 grader 测试，确认通过**

```bash
uv run pytest tests/test_evaluator.py tests/test_grader_integration.py -v
```

预期：`9 passed`

- [ ] **Step 9: Commit**

```bash
git add grader/evaluator.py grader/grader.py \
    tests/test_evaluator.py tests/test_grader_integration.py
git commit -m "fix: grader mcq_section key + evaluator generate_text + llm_client passthrough"
```

---

## Task 7: Exam Formatter 测试 + 验证

**Files:**
- Create: `tests/test_formatter.py`
（exam_formatter/services/formatter.py 已使用正确的 `mcq_section` 键，只需补测试验证）

- [ ] **Step 1: 写 formatter 测试**

创建 `tests/test_formatter.py`：

```python
import tempfile
import os


PROBLEM_SET = {
    "exam_id": "EXAM-20260418-TEST",
    "exam_date": "2026-04-18",
    "target_tags": ["Concurrency", "RAG"],
    "algorithm_section": [
        {
            "id": "algo-01",
            "title": "环形二进制串",
            "desc": "给定长度为 $n$ 的串...",
            "constraints": "1 <= n <= 2*10^5",
            "sample_io": [{"input": "3\n8\n11001001", "output": "4"}],
            "io_spec": {"type": "multi_test_case"},
            "std_solution": "def solve(): pass  # 绝不能出现在 md 中",
        }
    ],
    "mcq_section": [
        {
            "id": "mcq-01",
            "tag": "Concurrency",
            "text": "关于 asyncio，以下说法正确的是？",
            "options": {"A": "单线程并发", "B": "多线程并发", "C": "阻塞I/O", "D": "依赖回调"},
            "correct_options": ["A"],
            "explanation": "因为 asyncio 是单线程...",
        }
    ],
}


def test_build_daily_exam_creates_file():
    with tempfile.TemporaryDirectory() as d:
        from exam_formatter.services.formatter import build_daily_exam
        path = build_daily_exam(PROBLEM_SET, d)

        assert os.path.exists(path)
        assert path.endswith("Exam_20260418.md")


def test_build_daily_exam_excludes_answers():
    with tempfile.TemporaryDirectory() as d:
        from exam_formatter.services.formatter import build_daily_exam
        path = build_daily_exam(PROBLEM_SET, d)

        with open(path, encoding="utf-8") as f:
            content = f.read()

    assert "correct_options" not in content
    assert "std_solution" not in content
    assert "绝不能出现在 md 中" not in content
    assert "因为 asyncio 是单线程" not in content


def test_build_daily_exam_includes_answer_placeholder():
    with tempfile.TemporaryDirectory() as d:
        from exam_formatter.services.formatter import build_daily_exam
        path = build_daily_exam(PROBLEM_SET, d)

        with open(path, encoding="utf-8") as f:
            content = f.read()

    assert "你的答案: [ ]" in content


def test_build_daily_exam_injects_boilerplate_multi_test_case():
    with tempfile.TemporaryDirectory() as d:
        from exam_formatter.services.formatter import build_daily_exam
        path = build_daily_exam(PROBLEM_SET, d)

        with open(path, encoding="utf-8") as f:
            content = f.read()

    assert "for _ in range(T)" in content
    assert "algo-01" in content
```

- [ ] **Step 2: 运行测试**

```bash
uv run pytest tests/test_formatter.py -v
```

预期：`4 passed`（formatter 的 mcq_section 键已经正确）

- [ ] **Step 3: Commit**

```bash
git add tests/test_formatter.py
git commit -m "test: add exam formatter test suite"
```

---

## Task 8: 根目录编排入口 main.py

**Files:**
- Create: `main.py`

- [ ] **Step 1: 创建 main.py**

```python
import sys
import os
import json
import glob
from datetime import datetime, timezone, timedelta

from config import settings
from profiler.core.profiler import get_mcq_config, update_mcq_stats
from profiler.core.report_gen import generate_report
from problem_synthesizer.core.local_extractor import LocalBankExtractor
from problem_synthesizer.core.llm_coder import MathShellCoder
from problem_synthesizer.core.mcq_generator import MCQGenerator
from problem_synthesizer.utils.llm_client import LLMClient
from exam_formatter.services.formatter import build_daily_exam
from grader.grader import grade_submission


def _get_llm_client() -> LLMClient:
    if not settings.api_key:
        raise ValueError("LLM_API_KEY 未设置，请检查 .env 文件")
    return LLMClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
    )


def cmd_run():
    os.makedirs(settings.data_path, exist_ok=True)
    os.makedirs(settings.output_path, exist_ok=True)

    print("[1/3] 读取学习画像，生成今日考察配置...")
    mcq_config = get_mcq_config(settings.data_path)
    tags = mcq_config.get("target_tags", [])
    print(f"      今日目标标签: {tags if tags else '（全领域随机）'}")

    print("[2/3] 生成今日题目包...")
    llm_client = _get_llm_client()
    extractor = LocalBankExtractor(settings.local_bank_path)
    coder = MathShellCoder(llm_client)
    mcq_gen = MCQGenerator(llm_client)

    coding_problems = []
    try:
        local = extractor.sample_problems(count=2)
        coding_problems.extend(local)
        print(f"      本地题库: 已抽取 {len(local)} 道算法题")
    except ValueError as e:
        print(f"      [警告] 本地题库不足: {e}，将由 LLM 补足")

    print("      正在生成 LLM 算法题...")
    math_problem = coder.generate_problem(mcq_config)
    # algo-03 占位，但若本地题目不足，编号从实际数量+1开始
    math_problem["id"] = f"algo-{len(coding_problems)+1:02d}"
    coding_problems.append(math_problem)

    print("      正在生成多项选择题...")
    mcqs = mcq_gen.generate_mcqs(mcq_config)

    bj_tz = timezone(timedelta(hours=8))
    now = datetime.now(bj_tz)
    date_str = now.strftime("%Y-%m-%d")
    date_compact = now.strftime("%Y%m%d")

    problem_set = {
        "exam_id": f"EXAM-{date_compact}-{os.urandom(4).hex().upper()}",
        "exam_date": date_str,
        "target_tags": mcq_config.get("target_tags", []),
        "algorithm_section": coding_problems,
        "mcq_section": mcqs,
    }

    ps_path = os.path.join(settings.data_path, f"problem_set_{date_compact}.json")
    with open(ps_path, "w", encoding="utf-8") as f:
        json.dump(problem_set, f, indent=2, ensure_ascii=False)

    print("[3/3] 排版试卷...")
    exam_path = build_daily_exam(problem_set, settings.output_path)

    print(f"\n✅ 试卷已生成: {os.path.abspath(exam_path)}")
    print(f"   题目包存档: {os.path.abspath(ps_path)}")
    print("\n请填写答案后运行: python main.py grade")


def cmd_grade():
    md_files = sorted(glob.glob(os.path.join(settings.output_path, "Exam_*.md")))
    if not md_files:
        print("❌ 未找到试卷文件，请先运行: python main.py run")
        sys.exit(1)

    md_path = md_files[-1]
    date_compact = os.path.basename(md_path).replace("Exam_", "").replace(".md", "")
    ps_path = os.path.join(settings.data_path, f"problem_set_{date_compact}.json")

    if not os.path.exists(ps_path):
        print(f"❌ 找不到对应题目包: {ps_path}")
        sys.exit(1)

    print(f"[1/3] 批改试卷: {md_path}")
    llm_client = _get_llm_client()
    report = grade_submission(md_path, ps_path, llm_client)

    print("[2/3] 更新学习画像...")
    update_mcq_stats(report, settings.data_path)

    print("[3/3] 生成进度报告...")
    generate_report(settings.data_path)

    total = len(report)
    if total == 0:
        print("\n⚠️  未提取到答案，请检查试卷格式。")
        return

    correct = sum(1 for r in report if r["score"] >= 0.99)
    partial = sum(1 for r in report if 0.3 <= r["score"] < 0.99)
    wrong = sum(1 for r in report if r["score"] < 0.3)

    print(f"\n✅ 批改完成！全对: {correct}/{total}  少选: {partial}/{total}  错/多选: {wrong}/{total}")
    print(f"   进度报告: {os.path.abspath(os.path.join(settings.data_path, 'learning_progress.md'))}")


def cmd_report():
    generate_report(settings.data_path)
    report_path = os.path.abspath(os.path.join(settings.data_path, "learning_progress.md"))
    print(f"✅ 报告已更新: {report_path}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    dispatch = {"run": cmd_run, "grade": cmd_grade, "report": cmd_report}
    if cmd in dispatch:
        dispatch[cmd]()
    else:
        print("用法: python main.py [run|grade|report]")
        print("  run     — 生成今日试卷")
        print("  grade   — 批改并更新学习画像")
        print("  report  — 单独重新生成进度报告")
        sys.exit(1)
```

- [ ] **Step 2: 验证 import 可正常解析（dry run）**

```bash
python -c "import main; print('imports OK')"
```

预期：`imports OK`（不应有 ImportError）

- [ ] **Step 3: 运行完整测试套件确认无回归**

```bash
uv run pytest tests/ -v
```

预期：全部已有测试通过

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add root orchestrator main.py with run/grade/report commands"
```

---

## Task 9: 确保 profiler 模块可从根目录导入 + 最终集成验证

**Files:**
- 验证 `profiler/__init__.py` 等文件已正确创建
- 运行 profiler 原有测试

- [ ] **Step 1: 从根目录运行 profiler 原有测试**

```bash
uv run pytest profiler/tests/test_profiler.py -v
```

预期：`3 passed`

- [ ] **Step 2: 运行全部测试**

```bash
uv run pytest tests/ profiler/tests/ -v
```

预期：全部通过，无 ImportError、无 AttributeError

- [ ] **Step 3: 验证 main.py 帮助信息可正常显示**

```bash
python main.py
```

预期输出（退出码 1）：
```
用法: python main.py [run|grade|report]
  run     — 生成今日试卷
  grade   — 批改并更新学习画像
  report  — 单独重新生成进度报告
```

- [ ] **Step 4: 最终 commit**

```bash
git add profiler/__init__.py profiler/tests/__init__.py problem_synthesizer/core/__init__.py
git commit -m "chore: finalize package structure for root-level imports"
```

---

## 附录：本地题库文件格式规范

文件放在 `local_bank/` 目录，文件名即题目标识符。格式示例：

```python
"""
题目名称：环形前缀和查询

给定一个长度为 $n$ 的整数数组，处理 $q$ 次区间和查询 $[l, r]$。
要求所有查询在 $O(1)$ 时间内响应。

约束条件：1 <= n <= 2 * 10^5，1 <= q <= 10^5，-10^9 <= a_i <= 10^9

Example:
Input:
5 3
1 2 3 4 5
1 3
2 4
1 5
Output:
6
9
15
"""
import sys

def solve():
    data = sys.stdin.read().split()
    idx = 0
    n, q = int(data[idx]), int(data[idx+1]); idx += 2
    a = [int(data[idx+i]) for i in range(n)]; idx += n
    prefix = [0] * (n + 1)
    for i in range(n):
        prefix[i+1] = prefix[i] + a[i]
    for _ in range(q):
        l, r = int(data[idx]), int(data[idx+1]); idx += 2
        print(prefix[r] - prefix[l-1])

if __name__ == "__main__":
    solve()
```

**文件命名约定（tag 自动推断）：**

| 前缀 | 推断 tag |
|------|----------|
| `dp_` | DP |
| `graph_` | Graph |
| `tree_` | Tree |
| `sort_` | Sorting |
| `search_` | Search |
| `string_` | String |
| `math_` | Math |
| `greedy_` | Greedy |
| `binary_` | BinarySearch |
| 无前缀 | Algorithm |
