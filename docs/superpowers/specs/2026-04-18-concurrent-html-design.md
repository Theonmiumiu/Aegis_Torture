# Concurrent Generation + HTML Exam Interface Design

**日期**: 2026-04-18  
**拆分**: Sub-project 1（后端并发）+ Sub-project 2（HTML 前端）

---

## Sub-project 1：并发生成 + MCQ 批次拆分

### 背景

当前 `cmd_run` 串行执行：LLM 算法题 → MCQ（每 tag 一次请求）。当 target_tags 有 8 个时需要 9 次串行 LLM 调用，速度"令人窒息"。

### 目标

1. LLM 算法题生成与所有 MCQ 批次**并发执行**
2. MCQ 按固定批次（每批 4 道）拆分为多个请求，所有批次也并发
3. Rate limit（HTTP 429 / "too frequent" / "rate limit" 错误）专项处理：等 60s 后重试，不消耗普通重试计数

### 变更文件

#### `problem_synthesizer/utils/llm_client.py`

在 `generate_text` 的重试循环中，区分两类异常：

- **Rate limit 错误**：捕获 HTTP 429 或错误消息包含 `"too frequent"` / `"rate limit"` / `"429"` 的异常，等待 **60s**（固定，不加 Jitter），**不递增** `retries` 计数，日志级别 WARNING，提示用户等待。
- **普通网络错误**：保持现有指数退避逻辑，递增 `retries`，最多 `max_retries` 次。

```python
# 伪代码
while retries <= self.max_retries:
    try:
        response = self.client.chat.completions.create(...)
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("LLM 返回了空内容")
        return content
    except Exception as e:
        if _is_rate_limit_error(e):
            logger.warning("触发 Rate Limit，等待 60s 后重试...")
            time.sleep(60)
            continue  # 不递增 retries
        retries += 1
        if retries > self.max_retries:
            raise RuntimeError(f"LLM 接口多次调用失败: {e}") from e
        delay = base_delay * (2 ** (retries - 1)) + random.uniform(0, 1.0)
        time.sleep(delay)

def _is_rate_limit_error(e: Exception) -> bool:
    """判断是否为 rate limit 错误。"""
    msg = str(e).lower()
    return "429" in msg or "too frequent" in msg or "rate limit" in msg or "rate_limit" in msg
```

#### `problem_synthesizer/core/mcq_generator.py`

新增 `generate_batch(tags: List[str], count: int) -> List[MCQProblem]` 方法：

- 单次 LLM 请求生成 `count` 道题
- prompt 使用新模板 `MCQ_BATCH_PROMPT_TEMPLATE`（新增到 templates.py），接受 `{tags_str}` 和 `{count}` 占位符，`tags_str` 为逗号分隔的标签列表，prompt 中要求"从以下知识领域中出题，尽量覆盖所有标签"
- 每道题的 `tag` 字段：LLM 在输出 JSON 中包含 `tag` 字段，若缺失则从 `tags` 列表中按轮询顺序补充
- 返回值为完整的 MCQProblem 列表（含 question_id、tag 等元数据注入）
- 原有 `generate_mcqs` 方法保留（向后兼容，测试不破坏），内部改为调用 `generate_batch`

#### `main.py` — `cmd_run`

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

# 本地算法题抽取（同步，无 LLM 调用）
coding_problems = []
try:
    local = extractor.sample_problems(count=2)
    coding_problems.extend(local)
except ValueError as e:
    print(f"[警告] {e}")

# 计算 MCQ 批次
total_mcqs = mcq_config.get("constraints", {}).get("num_questions", 10)
batch_size = 4
num_batches = math.ceil(total_mcqs / batch_size)
all_tags = mcq_config.get("target_tags", []) or mcq_gen.fallback_tags[:2]

# 并发执行：LLM 算法题 + 所有 MCQ 批次
futures_map = {}
with ThreadPoolExecutor(max_workers=num_batches + 1) as executor:
    # Future: LLM 算法题
    f_algo = executor.submit(coder.generate_problem, mcq_config)
    futures_map[f_algo] = "algo"

    # Future: MCQ 各批次
    for i in range(num_batches):
        batch_count = min(batch_size, total_mcqs - i * batch_size)
        f_mcq = executor.submit(mcq_gen.generate_batch, all_tags, batch_count)
        futures_map[f_mcq] = f"mcq_batch_{i}"

    mcqs = []
    for future in as_completed(futures_map):
        key = futures_map[future]
        result = future.result()
        if key == "algo":
            result["id"] = f"algo-{len(coding_problems)+1:02d}"
            coding_problems.append(result)
        else:
            mcqs.extend(result)
```

### 错误处理

- 某个 MCQ 批次失败（非 rate limit）：降级为空列表，打印警告，其余批次结果仍保留
- LLM 算法题失败：使用 fallback 补偿题（现有逻辑）
- Rate limit：无限等待重试（不计入 max_retries），每次等 60s

---

## Sub-project 2：Flask HTML 交互式试卷

### 背景

当前用户在 Markdown 文件中手动填写答案，体验原始。目标是提供本地 web 界面，MCQ 直接勾选，算法题代码粘贴提交。

### 目标

`python main.py serve [--port 8080]` 启动本地 Flask 服务器，浏览器访问 `http://localhost:8080`，完成答题和批改的全流程。

### 新增文件

```
server/
├── app.py              # Flask 路由
└── templates/
    ├── exam.html       # 试卷页面
    └── result.html     # 批改结果页面
```

### 路由设计

| 路由 | 方法 | 功能 |
|------|------|------|
| `GET /` | GET | 加载最新 problem_set JSON，渲染 exam.html |
| `POST /grade` | POST | 接收答案，调 grade_submission，渲染 result.html |

### exam.html 功能规格

**头部**：试卷 ID、日期、知识点标签、预计时间

**第一部分 — 多项选择题**：
- 每题渲染为独立 `<fieldset>`
- 每个选项为 `<input type="checkbox">` + label
- 题目标注 [标签: Concurrency] 等知识点信息
- 评分规则提示：全对 1 分，漏选 1/3 分，错/多选 0 分

**第二部分 — 算法题**：
- 题目描述、约束条件、样例输入输出（`<pre>` 块）
- `<textarea>` 代码输入区（可拖拽调整高度），placeholder 为代码支架模板
- 题目 ID 作为 hidden input

**提交按钮**：收集所有答案，AJAX POST 到 `/grade`

### result.html 功能规格

**总分概览**：全对 N 题 / 少选 N 题 / 错选 N 题

**MCQ 逐题反馈**：
- 你的选择 vs 正确答案
- ✅ / ⚠️ / ❌ 标记（全对 / 少选 / 错选）
- 折叠展开的解析文本

**算法题反馈**：
- LLM 评分（0-100 分）
- 改进建议文字

**底部**：「学习进度已更新」提示 + 进度报告文件路径链接

### 数据流

```
exam.html POST /grade
    body: {
      "mcq_answers": {"mcq-01": ["A", "C"], "mcq-02": ["B"]},
      "code_answers": {"algo-01": "import sys\ndef solve(): ...", "algo-02": "..."}
    }
    ↓
server/app.py: 将答案写入临时 .md 文件（使用 exam_formatter 的 Markdown 格式，
               使 grader/parser.py 的正则可直接复用）
    ↓
grade_submission(tmp_md_path, ps_json_path, llm_client)
    ↓
update_mcq_stats(report, data_path)
    ↓
result.html 渲染报告
```

### pyproject.toml 新增依赖

```toml
dependencies = [
    "openai>=1.0",
    "python-dotenv>=1.0",
    "flask>=3.0",
]
```

### main.py 新增命令

```python
def cmd_serve(port: int = 8080):
    from server.app import create_app
    app = create_app(settings)
    print(f"✅ 试卷服务已启动: http://localhost:{port}")
    print("   Ctrl+C 退出")
    app.run(host="127.0.0.1", port=port, debug=False)
```

命令行：`python main.py serve` 或 `python main.py serve --port 9000`

### 安全约束

- 仅监听 `127.0.0.1`（不对外暴露）
- `debug=False`（不暴露 Flask debugger）
- 临时 md 文件写入 `data/tmp/`，批改完成后自动删除

---

## 依赖总结

| 新增依赖 | 用途 |
|----------|------|
| `flask>=3.0` | HTML 服务器 |

`concurrent.futures` 和 `math` 均为标准库，无需安装。

---

*本文档由 Claude Code 辅助生成，经用户逐节确认。*
