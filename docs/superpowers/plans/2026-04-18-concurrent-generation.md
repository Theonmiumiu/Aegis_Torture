# Concurrent Generation + MCQ Batching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 LLM 算法题生成与所有 MCQ 批次并发执行，MCQ 从逐 tag 串行改为固定批次（每批 4 道）并发，并对 Rate Limit 错误专项处理（等 60s 后重试，不消耗普通重试次数）。

**Architecture:** `LLMClient.generate_text` 新增 rate limit 检测，等 60s 后无限重试；`MCQGenerator` 新增 `generate_batch(tags, count)` 方法，单次请求生成多道题覆盖多 tag；`main.py cmd_run` 用 `ThreadPoolExecutor` 并发提交 LLM 算法题 + 所有 MCQ 批次。

**Tech Stack:** Python 3.13, `concurrent.futures.ThreadPoolExecutor`（标准库），`math`（标准库），现有 `openai` SDK

---

## 文件结构

**修改文件：**
- `problem_synthesizer/utils/llm_client.py` — 新增 `_is_rate_limit_error`，修改重试循环
- `problem_synthesizer/prompts/templates.py` — 新增 `MCQ_BATCH_PROMPT_TEMPLATE`
- `problem_synthesizer/core/mcq_generator.py` — 新增 `generate_batch` 方法
- `main.py` — `cmd_run` 改为并发执行

**修改测试：**
- `tests/test_llm_client.py` — 新增 rate limit 测试
- `tests/test_mcq_generator.py` — 新增 `generate_batch` 测试

---

## Task 1: Rate Limit 专项处理

**Files:**
- Modify: `problem_synthesizer/utils/llm_client.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_llm_client.py` 末尾追加：

```python
def test_rate_limit_does_not_consume_retries():
    """Rate limit 错误不应消耗 max_retries 计数。"""
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "success"
        create_mock = mock_openai_cls.return_value.chat.completions.create
        # 两次 rate limit，第三次成功
        create_mock.side_effect = [
            Exception("429 rate limit exceeded"),
            Exception("too frequent, please try again"),
            mock_response,
        ]

        with patch("problem_synthesizer.utils.llm_client.time.sleep"):
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=1)
            result = client.generate_text("hello")

    assert result == "success"
    # max_retries=1 but 2 rate limit errors happened — should NOT have raised
    assert create_mock.call_count == 3


def test_rate_limit_sleeps_60_seconds():
    """Rate limit 错误必须等待 60 秒。"""
    with patch("problem_synthesizer.utils.llm_client.OpenAI") as mock_openai_cls:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        create_mock = mock_openai_cls.return_value.chat.completions.create
        create_mock.side_effect = [Exception("too frequent"), mock_response]

        with patch("problem_synthesizer.utils.llm_client.time.sleep") as mock_sleep:
            from problem_synthesizer.utils.llm_client import LLMClient
            client = LLMClient(api_key="t", base_url="http://t", model="m", max_retries=3)
            client.generate_text("hello")

    assert mock_sleep.call_args_list[0][0][0] == 60
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
uv run pytest tests/test_llm_client.py::test_rate_limit_does_not_consume_retries tests/test_llm_client.py::test_rate_limit_sleeps_60_seconds -v
```

预期：FAIL（当前代码对 rate limit 和普通错误处理相同）

- [ ] **Step 3: 修改 `problem_synthesizer/utils/llm_client.py`**

将整个文件替换为：

```python
import time
import random
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def _is_rate_limit_error(e: Exception) -> bool:
    """判断是否为 Rate Limit 类错误（HTTP 429 / too frequent）。"""
    msg = str(e).lower()
    return any(kw in msg for kw in ("429", "too frequent", "rate limit", "rate_limit", "ratelimit"))


class LLMClient:
    """
    LLM 客户端封装，支持所有 OpenAI-compatible 接口。
    内置带 Jitter 的指数退避重试机制。
    max_retries=3 表示初始请求失败后最多重试 3 次，共最多 4 次请求。
    Rate limit 错误单独处理：等待 60s 后重试，不消耗 max_retries 计数。
    """

    def __init__(self, api_key: str, base_url: str, model: str, max_retries: int = 3):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_retries = max_retries

    def generate_text(self, prompt: str, temperature: float = 0.5) -> str:
        """发送 Prompt 并获取文本回复。Rate limit 错误等 60s 重试；其他错误最多重试 max_retries 次。"""
        retries = 0
        base_delay = 2.0

        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=2048,
                )
                content = response.choices[0].message.content
                if content is None:
                    raise RuntimeError("LLM 返回了空内容（finish_reason 可能表示拒绝）")
                return content

            except Exception as e:
                if _is_rate_limit_error(e):
                    logger.warning("触发 Rate Limit，等待 60s 后重试（不消耗重试次数）...")
                    time.sleep(60)
                    continue

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

- [ ] **Step 4: 运行所有 LLMClient 测试**

```bash
uv run pytest tests/test_llm_client.py -v
```

预期：`5 passed`（原有 3 个 + 新增 2 个）

- [ ] **Step 5: 运行完整测试套件确认无回归**

```bash
uv run pytest tests/ profiler/tests/ -v
```

预期：`36 passed`（原 34 + 2 新增）

- [ ] **Step 6: Commit**

```bash
git add problem_synthesizer/utils/llm_client.py tests/test_llm_client.py
git commit -m "feat: add rate limit handling (60s wait, no retry count consumed)"
```

---

## Task 2: MCQ_BATCH_PROMPT_TEMPLATE

**Files:**
- Modify: `problem_synthesizer/prompts/templates.py`

- [ ] **Step 1: 追加 `MCQ_BATCH_PROMPT_TEMPLATE` 到 templates.py 末尾**

```python
MCQ_BATCH_PROMPT_TEMPLATE = """
Role: 顶级大厂资深架构师及笔试出题官。
Style: 苛刻、专业，擅长考察候选人的底层原理理解深度。

Task:
请从以下技术领域/知识点中出题，尽量覆盖所有标签：【{tags_str}】
生成 {count} 道高难度的多项选择题。

Constraint (非常严格，必须遵守):
1. 选项数量：每道题固定提供 4 个选项（A, B, C, D）。
2. 正确项分布：每道题【必须有 2 到 3 个正确选项】，不能是单选题，也不能全对。
3. 每道题必须包含 "tag" 字段，值必须是上述知识点列表中的一项原文。
4. 混淆设计原则（陷阱）：
   - 生成一个看似正确但实则违背底层原理的选项。
   - 生成一个在特定场景下才成立，但在题目描述的一般场景下不适用的选项（张冠李戴）。
5. 必须输出合法的 JSON 数组格式，不要用 Markdown 的 ```json 标签包裹。

JSON 数组格式如下：
[
    {{
        "tag": "知识点名称（必须来自上述列表中的一项）",
        "text": "题目描述（包含具体的业务或技术场景）",
        "options": {{
            "A": "选项 A 的内容",
            "B": "选项 B 的内容",
            "C": "选项 C 的内容",
            "D": "选项 D 的内容"
        }},
        "correct_options": ["A", "C"],
        "explanation": "详细的解析，必须逐一解释为什么选 A、C，以及为什么 B、D 是陷阱。"
    }}
]
"""
```

- [ ] **Step 2: 验证模板可正常格式化**

```bash
python -c "
from problem_synthesizer.prompts.templates import MCQ_BATCH_PROMPT_TEMPLATE
result = MCQ_BATCH_PROMPT_TEMPLATE.format(tags_str='TCP, RAG', count=4)
assert 'TCP, RAG' in result
assert '4' in result
print('OK')
"
```

预期：`OK`

- [ ] **Step 3: Commit**

```bash
git add problem_synthesizer/prompts/templates.py
git commit -m "feat: add MCQ_BATCH_PROMPT_TEMPLATE for multi-tag batch generation"
```

---

## Task 3: generate_batch 方法

**Files:**
- Modify: `problem_synthesizer/core/mcq_generator.py`
- Modify: `tests/test_mcq_generator.py`

- [ ] **Step 1: 追加 generate_batch 测试到 `tests/test_mcq_generator.py` 末尾**

```python
def test_generate_batch_returns_correct_count():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[
        {"tag": "TCP", "text": "Q1?", "options": {"A":"a","B":"b","C":"c","D":"d"}, "correct_options": ["A","B"], "explanation": "..."},
        {"tag": "RAG", "text": "Q2?", "options": {"A":"a","B":"b","C":"c","D":"d"}, "correct_options": ["B","C"], "explanation": "..."},
        {"tag": "TCP", "text": "Q3?", "options": {"A":"a","B":"b","C":"c","D":"d"}, "correct_options": ["A","C"], "explanation": "..."},
        {"tag": "RAG", "text": "Q4?", "options": {"A":"a","B":"b","C":"c","D":"d"}, "correct_options": ["C","D"], "explanation": "..."}
    ]'''

    result = gen.generate_batch(["TCP", "RAG"], count=4)

    assert len(result) == 4
    for item in result:
        assert "question_id" in item
        assert "tag" in item
        assert "correct_options" in item


def test_generate_batch_uses_llm_provided_tag():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "tag": "RAG",
        "text": "Q?", "options": {"A":"a","B":"b","C":"c","D":"d"},
        "correct_options": ["A","B"], "explanation": "..."
    }]'''

    result = gen.generate_batch(["TCP", "RAG"], count=1)

    assert result[0]["tag"] == "RAG"


def test_generate_batch_fallback_tag_when_missing():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "text": "Q?", "options": {"A":"a","B":"b","C":"c","D":"d"},
        "correct_options": ["A","B"], "explanation": "..."
    }]'''

    result = gen.generate_batch(["TCP", "RAG"], count=1)

    assert result[0]["tag"] == "TCP"


def test_generate_batch_prompt_contains_all_tags():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "tag": "TCP", "text": "Q?", "options": {"A":"a","B":"b","C":"c","D":"d"},
        "correct_options": ["A","B"], "explanation": "..."
    }]'''

    gen.generate_batch(["TCP", "RAG", "Concurrency"], count=3)

    prompt = mock_client.generate_text.call_args[0][0]
    assert "TCP" in prompt
    assert "RAG" in prompt
    assert "Concurrency" in prompt


def test_generate_batch_empty_tags_uses_fallback():
    gen, mock_client = _make_gen()
    mock_client.generate_text.return_value = '''[{
        "tag": "并发与多线程 (Concurrency)", "text": "Q?",
        "options": {"A":"a","B":"b","C":"c","D":"d"},
        "correct_options": ["A","B"], "explanation": "..."
    }]'''

    result = gen.generate_batch([], count=1)

    assert len(result) == 1
    mock_client.generate_text.assert_called_once()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
uv run pytest tests/test_mcq_generator.py::test_generate_batch_returns_correct_count -v
```

预期：FAIL（`generate_batch` 方法不存在）

- [ ] **Step 3: 在 `problem_synthesizer/core/mcq_generator.py` 添加 generate_batch**

在文件顶部 import 区追加：
```python
from problem_synthesizer.prompts.templates import MCQ_BATCH_PROMPT_TEMPLATE
```

（`MCQ_PROMPT_TEMPLATE` 的 import 已存在，只需追加 `MCQ_BATCH_PROMPT_TEMPLATE`）

在 `MCQGenerator` 类末尾（`generate_mcqs` 方法之后）追加：

```python
def generate_batch(self, tags: List[str], count: int) -> List[Dict[str, Any]]:
    """
    单次 LLM 请求生成 count 道题，出题范围覆盖所有 tags。
    比 generate_mcqs 更高效：减少 LLM 请求次数，适合并发批次调用。
    """
    if not tags:
        tags = random.sample(self.fallback_tags, min(2, len(self.fallback_tags)))

    tags_str = "、".join(tags)
    prompt = MCQ_BATCH_PROMPT_TEMPLATE.format(tags_str=tags_str, count=count).strip()

    try:
        response_text = self.llm_client.generate_text(prompt, temperature=0.2)
        clean_json_str = response_text.replace("```json", "").replace("```", "").strip()
        parsed_mcqs = json.loads(clean_json_str)

        result = []
        for i, mcq in enumerate(parsed_mcqs):
            tag = mcq.get("tag") or tags[i % len(tags)]

            correct_count = len(mcq.get("correct_options", []))
            if correct_count > 3:
                mcq["correct_options"] = mcq["correct_options"][:3]
            elif correct_count < 2:
                existing = mcq.get("correct_options") or []
                mcq["correct_options"] = (existing + ["A", "B"])[:2]

            result.append({
                "question_id": str(uuid.uuid4()),
                "tag": tag,
                "text": mcq.get("text", "题目生成失败"),
                "options": mcq.get("options", {}),
                "correct_options": mcq.get("correct_options"),
                "explanation": mcq.get("explanation", "无解析"),
            })
        return result

    except json.JSONDecodeError as e:
        import logging as _log
        _log.getLogger(__name__).warning(f"MCQ 批次 JSON 解析失败: {e}，触发降级补偿")
        return [
            {
                "question_id": str(uuid.uuid4()),
                "tag": tags[i % len(tags)],
                "text": f"（降级补偿题）关于 {tags[i % len(tags)]}，以下说法正确的是？",
                "options": {"A": "正确描述A。", "B": "正确描述B。", "C": "错误描述C。", "D": "无关描述D。"},
                "correct_options": ["A", "B"],
                "explanation": f"LLM 生成失败: {str(e)}",
            }
            for i in range(count)
        ]
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).warning(f"MCQ 批次生成异常: {e}")
        return []
```

- [ ] **Step 4: 运行 generate_batch 测试**

```bash
uv run pytest tests/test_mcq_generator.py -v
```

预期：`9 passed`（原 4 个 + 新 5 个）

- [ ] **Step 5: 运行完整测试套件**

```bash
uv run pytest tests/ profiler/tests/ -v
```

预期：`41 passed`

- [ ] **Step 6: Commit**

```bash
git add problem_synthesizer/core/mcq_generator.py tests/test_mcq_generator.py
git commit -m "feat: add MCQGenerator.generate_batch for concurrent batch MCQ generation"
```

---

## Task 4: 并发 cmd_run

**Files:**
- Modify: `main.py`

注意：此任务修改 `cmd_run` 的执行策略，LLM 调用本身不变，故无需额外单元测试（并发行为难以 mock 验证）。手动验证即可。

- [ ] **Step 1: 在 `main.py` 顶部追加 import**

在现有 import 之后追加：

```python
import math
from concurrent.futures import ThreadPoolExecutor
```

- [ ] **Step 2: 将 `cmd_run` 函数完整替换为以下内容**

```python
def cmd_run():
    import math
    from concurrent.futures import ThreadPoolExecutor

    os.makedirs(settings.data_path, exist_ok=True)
    os.makedirs(settings.output_path, exist_ok=True)

    print("[1/3] 读取学习画像，生成今日考察配置...")
    mcq_config = get_mcq_config(settings.data_path)
    tags = mcq_config.get("target_tags", [])
    print(f"      今日目标标签: {tags if tags else '（全领域随机）'}")

    print("[2/3] 生成今日题目包（并发）...")
    llm_client = _get_llm_client()
    extractor = LocalBankExtractor(settings.local_bank_path)
    coder = MathShellCoder(llm_client)
    mcq_gen = MCQGenerator(llm_client)

    # 本地题库：同步执行（无 LLM 调用）
    coding_problems = []
    try:
        local = extractor.sample_problems(count=2)
        coding_problems.extend(local)
        print(f"      本地题库: 已抽取 {len(local)} 道算法题")
    except ValueError as e:
        print(f"      [警告] 本地题库不足: {e}")

    # 计算 MCQ 批次数
    total_mcqs = mcq_config.get("constraints", {}).get("num_questions", 10)
    batch_size = 4
    num_batches = math.ceil(total_mcqs / batch_size)
    all_tags = mcq_config.get("target_tags", []) or mcq_gen.fallback_tags[:2]

    print(f"      并发提交: 1 道 LLM 算法题 + {num_batches} 批 MCQ（每批最多 {batch_size} 道）...")

    # 并发：LLM 算法题 + 所有 MCQ 批次同时跑
    futures_map = {}
    with ThreadPoolExecutor(max_workers=num_batches + 1) as executor:
        futures_map[executor.submit(coder.generate_problem, mcq_config)] = "algo"
        for i in range(num_batches):
            batch_count = min(batch_size, total_mcqs - i * batch_size)
            futures_map[executor.submit(mcq_gen.generate_batch, all_tags, batch_count)] = f"mcq_{i}"
    # ThreadPoolExecutor.__exit__ waits for all futures before continuing

    mcqs = []
    algo_problem = None
    for future, key in futures_map.items():
        try:
            result = future.result()
        except Exception as e:
            print(f"      [警告] {key} 生成失败: {e}")
            continue
        if key == "algo":
            algo_problem = result
        else:
            mcqs.extend(result)

    if algo_problem:
        algo_problem["id"] = f"algo-{len(coding_problems)+1:02d}"
        coding_problems.append(algo_problem)

    print(f"      生成完毕：{len(coding_problems)} 道算法题，{len(mcqs)} 道多选题")

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
```

- [ ] **Step 3: 验证 import 通过**

```bash
python -c "import main; print('OK')"
```

预期：`OK`

- [ ] **Step 4: 运行测试套件确认无回归**

```bash
uv run pytest tests/ profiler/tests/ -v
```

预期：`41 passed`

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: concurrent LLM generation with ThreadPoolExecutor (algo + MCQ batches)"
```

---

## 附录：批次示例

当 `num_questions=10`，`batch_size=4`，`target_tags=["TCP","RAG","Concurrency","DP"]` 时：

| Future | 内容 | 并发 |
|--------|------|------|
| F1 | `coder.generate_problem(mcq_config)` — 1 道 LLM 算法题 | ✅ |
| F2 | `mcq_gen.generate_batch(all_tags, 4)` — 批次 0，4 道 MCQ | ✅ |
| F3 | `mcq_gen.generate_batch(all_tags, 4)` — 批次 1，4 道 MCQ | ✅ |
| F4 | `mcq_gen.generate_batch(all_tags, 2)` — 批次 2，2 道 MCQ | ✅ |

4 个 LLM 请求同时发出，总耗时 ≈ 单次最慢请求时间，而非原来的 4 倍串行。
