# HTML Interactive Exam Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供 `python main.py serve` 命令启动本地 Flask 服务器，浏览器访问试卷页面，MCQ 勾选复选框，算法题粘贴代码，提交后自动批改并在页面展示结果。

**Architecture:** `server/app.py` 包含 Flask 工厂函数 `create_app(settings)`，路由 `GET /` 渲染试卷，`POST /grade` 接收 JSON 答案，构造临时 Markdown 文件复用现有 `grade_submission`，结果渲染到 `result.html`。`main.py` 新增 `cmd_serve` 命令。

**Tech Stack:** Python 3.13, `flask>=3.0`，Jinja2（Flask 内置），`concurrent.futures`（已有）

---

## 文件结构

**新建文件：**
- `server/__init__.py` — 空，使 server 成为包
- `server/app.py` — Flask 工厂 + 路由 + `_build_temp_md` 辅助函数
- `server/templates/exam.html` — 试卷页面
- `server/templates/result.html` — 批改结果页面
- `tests/test_server.py` — Flask test client 测试

**修改文件：**
- `pyproject.toml` — 添加 `flask>=3.0` 依赖
- `main.py` — 新增 `cmd_serve` 和对应 dispatch

---

## Task 1: 安装 Flask + app 骨架

**Files:**
- Modify: `pyproject.toml`
- Create: `server/__init__.py`
- Create: `server/app.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: 添加 Flask 依赖到 pyproject.toml**

将 `dependencies` 部分改为：

```toml
dependencies = [
    "openai>=1.0",
    "python-dotenv>=1.0",
    "flask>=3.0",
]
```

- [ ] **Step 2: 安装新依赖**

```bash
uv sync
```

预期：包含 `Installed flask-3.x.x`

- [ ] **Step 3: 创建 `server/__init__.py`（空文件）**

- [ ] **Step 4: 写失败测试**

创建 `tests/test_server.py`：

```python
import json
import os
import tempfile
from unittest.mock import MagicMock, patch


def _make_problem_set():
    return {
        "exam_id": "EXAM-TEST-001",
        "exam_date": "2026-04-18",
        "target_tags": ["TCP"],
        "mcq_section": [
            {
                "question_id": "q1",
                "tag": "TCP",
                "text": "关于 TCP 三次握手？",
                "options": {"A": "SYN", "B": "ACK", "C": "FIN", "D": "RST"},
                "correct_options": ["A", "B"],
                "explanation": "三次握手需要 SYN 和 ACK。",
                "brief_description": "TCP 握手",
            }
        ],
        "algorithm_section": [
            {
                "id": "algo-01",
                "title": "两数之和",
                "desc": "给定数组...",
                "constraints": "n <= 10^4",
                "sample_io": [{"input": "2\n2 7", "output": "0 1"}],
                "io_spec": {"type": "single_test_case"},
                "std_solution": "pass",
                "tag": "Algorithm",
                "brief_description": "两数之和",
                "source": "local",
            }
        ],
    }


def _make_app(tmpdir):
    ps = _make_problem_set()
    ps_path = os.path.join(tmpdir, "problem_set_20260418.json")
    with open(ps_path, "w", encoding="utf-8") as f:
        json.dump(ps, f, ensure_ascii=False)

    from server.app import create_app
    mock_settings = MagicMock()
    mock_settings.data_path = tmpdir
    mock_settings.api_key = "test-key"
    mock_settings.base_url = "http://test"
    mock_settings.model = "test-model"
    app = create_app(mock_settings)
    app.config["TESTING"] = True
    return app, ps


def test_index_returns_200_with_exam():
    with tempfile.TemporaryDirectory() as tmpdir:
        app, ps = _make_app(tmpdir)
        with app.test_client() as client:
            resp = client.get("/")
    assert resp.status_code == 200
    assert b"TCP" in resp.data


def test_index_returns_404_when_no_problem_set():
    with tempfile.TemporaryDirectory() as tmpdir:
        from server.app import create_app
        mock_settings = MagicMock()
        mock_settings.data_path = tmpdir
        app = create_app(mock_settings)
        app.config["TESTING"] = True
        with app.test_client() as client:
            resp = client.get("/")
    assert resp.status_code == 404


def test_index_does_not_leak_answers():
    with tempfile.TemporaryDirectory() as tmpdir:
        app, ps = _make_app(tmpdir)
        with app.test_client() as client:
            resp = client.get("/")
    content = resp.data.decode("utf-8")
    assert "correct_options" not in content
    assert "std_solution" not in content
    assert "三次握手需要 SYN 和 ACK" not in content  # explanation hidden


def test_grade_returns_result_page():
    with tempfile.TemporaryDirectory() as tmpdir:
        app, ps = _make_app(tmpdir)
        mock_report = [
            {"tag": "TCP", "score": 1.0, "brief_description": "TCP 握手"},
            {"tag": "Algorithm", "score": 0.85, "brief_description": "两数之和"},
        ]
        with patch("server.app.grade_submission", return_value=mock_report), \
             patch("server.app.update_mcq_stats"), \
             patch("server.app.generate_report"):
            with app.test_client() as client:
                resp = client.post(
                    "/grade",
                    json={
                        "mcq_answers": {"q1": ["A", "B"]},
                        "code_answers": {"algo-01": "def solve(): pass"},
                    },
                )
    assert resp.status_code == 200
    content = resp.data.decode("utf-8")
    assert "TCP" in content
    assert "1.0" in content or "全对" in content
```

- [ ] **Step 5: 运行测试，确认失败**

```bash
uv run pytest tests/test_server.py -v
```

预期：`ModuleNotFoundError: No module named 'server'`

- [ ] **Step 6: 创建 `server/app.py`**

```python
import glob
import json
import os

from flask import Flask, render_template, request

from grader.grader import grade_submission
from profiler.core.profiler import update_mcq_stats
from profiler.core.report_gen import generate_report


def _get_latest_problem_set(data_path: str):
    """找到最新的 problem_set_*.json，返回 (dict, path) 或 (None, None)。"""
    files = sorted(glob.glob(os.path.join(data_path, "problem_set_*.json")))
    if not files:
        return None, None
    ps_path = files[-1]
    with open(ps_path, encoding="utf-8") as f:
        return json.load(f), ps_path


def _build_temp_md(problem_set: dict, mcq_answers: dict, code_answers: dict) -> str:
    """
    构造 grader/parser.py 可以解析的 Markdown 格式字符串。
    MCQ 格式：**你的答案: [A, C]**
    算法题格式：# --- 题目 ID: algo-01 ---\n```python\ncode\n```
    """
    lines = []

    for mcq in problem_set.get("mcq_section", []):
        qid = mcq["question_id"]
        selected = mcq_answers.get(qid, [])
        ans_str = ", ".join(sorted(selected)) if selected else ""
        lines.append(f"**你的答案: [{ans_str}]**")

    for algo in problem_set.get("algorithm_section", []):
        aid = algo["id"]
        code = code_answers.get(aid, "")
        lines.append(f"# --- 题目 ID: {aid} ---")
        lines.append("```python")
        lines.append(code if code else "# 未提交代码")
        lines.append("```")

    return "\n".join(lines)


def create_app(settings):
    app = Flask(__name__, template_folder="templates")

    @app.route("/")
    def index():
        problem_set, _ = _get_latest_problem_set(settings.data_path)
        if not problem_set:
            return "尚未生成试卷，请先运行: python main.py run", 404
        return render_template("exam.html", problem_set=problem_set)

    @app.route("/grade", methods=["POST"])
    def grade():
        data = request.get_json(force=True)
        mcq_answers = data.get("mcq_answers", {})
        code_answers = data.get("code_answers", {})

        problem_set, ps_path = _get_latest_problem_set(settings.data_path)
        if not problem_set:
            return "找不到题目包", 404

        tmp_dir = os.path.join(settings.data_path, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, "submission.md")

        try:
            tmp_md = _build_temp_md(problem_set, mcq_answers, code_answers)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(tmp_md)

            from problem_synthesizer.utils.llm_client import LLMClient
            llm_client = LLMClient(
                api_key=settings.api_key,
                base_url=settings.base_url,
                model=settings.model,
            )
            report = grade_submission(tmp_path, ps_path, llm_client)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        update_mcq_stats(report, settings.data_path)
        generate_report(settings.data_path)

        return render_template("result.html", report=report, problem_set=problem_set)

    return app
```

- [ ] **Step 7: 运行测试，确认通过**

```bash
uv run pytest tests/test_server.py -v
```

注意：`test_index_returns_200_with_exam` 和 `test_index_does_not_leak_answers` 此时可能因缺少模板而失败（`TemplateNotFound`）。这是正常的——模板在 Task 2 中创建。只需确认 `test_index_returns_404_when_no_problem_set` 通过即可。

```bash
uv run pytest tests/test_server.py::test_index_returns_404_when_no_problem_set -v
```

预期：`1 passed`

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml server/__init__.py server/app.py tests/test_server.py
git commit -m "feat: add Flask app skeleton with / and /grade routes"
```

---

## Task 2: exam.html 模板

**Files:**
- Create: `server/templates/exam.html`

- [ ] **Step 1: 创建 `server/templates/exam.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日评测 — {{ problem_set.exam_id }}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Segoe UI", "PingFang SC", sans-serif; background: #f5f5f5; color: #222; }
  header { background: #1a1a2e; color: #eee; padding: 20px 40px; }
  header h1 { font-size: 1.4rem; margin-bottom: 6px; }
  header p { font-size: 0.85rem; color: #aaa; }
  .container { max-width: 860px; margin: 30px auto; padding: 0 20px; }
  .section-title { font-size: 1.2rem; font-weight: bold; border-left: 4px solid #4a90d9;
                   padding-left: 12px; margin: 30px 0 16px; }
  .rule-note { background: #fff8e1; border: 1px solid #ffe082; border-radius: 6px;
               padding: 10px 16px; font-size: 0.85rem; margin-bottom: 20px; color: #6d4c00; }
  fieldset.mcq { background: #fff; border: 1px solid #ddd; border-radius: 8px;
                 padding: 16px 20px; margin-bottom: 16px; }
  fieldset.mcq legend { font-weight: 600; font-size: 0.95rem; padding: 0 6px; }
  .tag-badge { background: #e3f2fd; color: #1565c0; font-size: 0.75rem;
               padding: 2px 8px; border-radius: 12px; margin-left: 8px; font-weight: normal; }
  .option-label { display: flex; align-items: flex-start; gap: 10px; margin: 10px 0;
                  cursor: pointer; padding: 8px 12px; border-radius: 6px; transition: background 0.15s; }
  .option-label:hover { background: #f0f4ff; }
  .option-label input { margin-top: 2px; flex-shrink: 0; }
  .algo-card { background: #fff; border: 1px solid #ddd; border-radius: 8px;
               padding: 20px; margin-bottom: 20px; }
  .algo-card h3 { font-size: 1rem; margin-bottom: 12px; color: #1a1a2e; }
  .algo-desc { font-size: 0.9rem; line-height: 1.7; margin-bottom: 10px; }
  pre.constraint { background: #f8f8f8; border-left: 3px solid #ccc; padding: 8px 14px;
                   font-size: 0.85rem; margin: 10px 0; overflow-x: auto; }
  pre.sample { background: #1e1e2e; color: #cdd6f4; padding: 12px 16px; border-radius: 6px;
               font-size: 0.82rem; margin: 10px 0; overflow-x: auto; }
  .code-area { width: 100%; min-height: 260px; padding: 12px; font-family: "Consolas", monospace;
               font-size: 0.85rem; border: 1px solid #ccc; border-radius: 6px; resize: vertical;
               background: #1e1e2e; color: #cdd6f4; margin-top: 12px; }
  .submit-bar { position: sticky; bottom: 0; background: #fff; border-top: 1px solid #ddd;
                padding: 16px 20px; display: flex; align-items: center; gap: 16px;
                box-shadow: 0 -2px 8px rgba(0,0,0,.08); }
  #submit-btn { background: #4a90d9; color: #fff; border: none; padding: 12px 36px;
                border-radius: 8px; font-size: 1rem; cursor: pointer; font-weight: 600; }
  #submit-btn:hover { background: #357abd; }
  #submit-btn:disabled { background: #aaa; cursor: not-allowed; }
  #loading { color: #666; font-size: 0.9rem; display: none; }
</style>
</head>
<body>

<header>
  <h1>📋 每日算法与工程评测</h1>
  <p>试卷 ID: {{ problem_set.exam_id }} &nbsp;|&nbsp; 生成日期: {{ problem_set.exam_date }}
     &nbsp;|&nbsp; 知识点: {{ problem_set.target_tags | join(', ') }}</p>
</header>

<div class="container">

  {# ── 多项选择题 ── #}
  {% if problem_set.mcq_section %}
  <div class="section-title">第一部分：多项选择题</div>
  <div class="rule-note">⚠️ 本部分多选题：全对得 1 分，漏选得 1/3 分，错选/多选不得分。</div>

  {% for mcq in problem_set.mcq_section %}
  <fieldset class="mcq" data-qid="{{ mcq.question_id }}">
    <legend>{{ loop.index }}. {{ mcq.text }}
      <span class="tag-badge">{{ mcq.tag }}</span>
    </legend>
    {% for key, val in mcq.options.items() %}
    <label class="option-label">
      <input type="checkbox" class="mcq-opt" data-qid="{{ mcq.question_id }}" value="{{ key }}">
      <span><strong>{{ key }}.</strong> {{ val }}</span>
    </label>
    {% endfor %}
  </fieldset>
  {% endfor %}
  {% endif %}

  {# ── 算法编程题 ── #}
  {% if problem_set.algorithm_section %}
  <div class="section-title">第二部分：算法编程题</div>

  {% for algo in problem_set.algorithm_section %}
  <div class="algo-card">
    <h3>题 {{ loop.index }}: {{ algo.title }} &nbsp;<code style="font-size:.8rem;color:#888">ID: {{ algo.id }}</code></h3>
    <div class="algo-desc">{{ algo.desc }}</div>
    {% if algo.constraints %}
    <pre class="constraint">约束条件：{{ algo.constraints }}</pre>
    {% endif %}
    {% for io in algo.sample_io %}
    <pre class="sample">样例输入：
{{ io.input }}

样例输出：
{{ io.output }}</pre>
    {% endfor %}
    <textarea class="code-area" data-aid="{{ algo.id }}"
placeholder="import sys

def solve():
    # 在此粘贴或编写你的 Python 代码
    pass

if __name__ == '__main__':
    solve()"></textarea>
  </div>
  {% endfor %}
  {% endif %}

</div>

<div class="submit-bar">
  <button id="submit-btn" onclick="submitAnswers()">提交批改</button>
  <span id="loading">⏳ 正在批改中，请稍候（LLM 评测算法题可能需要数秒）...</span>
</div>

<script>
function submitAnswers() {
  const mcq_answers = {};
  document.querySelectorAll('fieldset[data-qid]').forEach(fs => {
    const qid = fs.dataset.qid;
    mcq_answers[qid] = [...fs.querySelectorAll('.mcq-opt:checked')].map(el => el.value);
  });

  const code_answers = {};
  document.querySelectorAll('.code-area[data-aid]').forEach(ta => {
    code_answers[ta.dataset.aid] = ta.value;
  });

  document.getElementById('submit-btn').disabled = true;
  document.getElementById('loading').style.display = 'inline';

  fetch('/grade', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mcq_answers, code_answers})
  })
  .then(r => {
    if (!r.ok) throw new Error('服务器返回 ' + r.status);
    return r.text();
  })
  .then(html => { document.open(); document.write(html); document.close(); })
  .catch(err => {
    alert('提交失败: ' + err);
    document.getElementById('submit-btn').disabled = false;
    document.getElementById('loading').style.display = 'none';
  });
}
</script>
</body>
</html>
```

- [ ] **Step 2: 运行试卷相关测试**

```bash
uv run pytest tests/test_server.py::test_index_returns_200_with_exam tests/test_server.py::test_index_does_not_leak_answers -v
```

预期：`2 passed`

- [ ] **Step 3: Commit**

```bash
git add server/templates/exam.html
git commit -m "feat: add exam.html with MCQ checkboxes and code textarea"
```

---

## Task 3: result.html 模板

**Files:**
- Create: `server/templates/result.html`

- [ ] **Step 1: 创建 `server/templates/result.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>批改结果 — {{ problem_set.exam_id }}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Segoe UI", "PingFang SC", sans-serif; background: #f5f5f5; color: #222; }
  header { background: #1a1a2e; color: #eee; padding: 20px 40px; }
  header h1 { font-size: 1.4rem; margin-bottom: 6px; }
  .container { max-width: 860px; margin: 30px auto; padding: 0 20px; }
  .summary-bar { display: flex; gap: 20px; background: #fff; border-radius: 10px;
                 padding: 20px 24px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  .stat { text-align: center; }
  .stat .num { font-size: 2rem; font-weight: 700; }
  .stat .lbl { font-size: 0.8rem; color: #666; margin-top: 4px; }
  .correct .num { color: #2e7d32; }
  .partial .num { color: #f57f17; }
  .wrong .num   { color: #c62828; }
  .total .num   { color: #1565c0; }
  .result-card { background: #fff; border-radius: 8px; padding: 16px 20px; margin-bottom: 14px;
                 border-left: 5px solid #ccc; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
  .result-card.rc-correct { border-left-color: #4caf50; }
  .result-card.rc-partial  { border-left-color: #ffc107; }
  .result-card.rc-wrong    { border-left-color: #f44336; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .tag-badge { background: #e3f2fd; color: #1565c0; font-size: 0.75rem;
               padding: 2px 8px; border-radius: 12px; }
  .score-badge { font-weight: 700; font-size: 0.9rem; }
  .desc-text { font-size: 0.88rem; color: #555; margin-bottom: 8px; }
  details summary { cursor: pointer; font-size: 0.85rem; color: #1565c0; margin-top: 8px; }
  details p { font-size: 0.85rem; color: #444; margin-top: 8px; line-height: 1.6;
              background: #f9f9f9; padding: 10px; border-radius: 6px; }
  .section-title { font-size: 1.1rem; font-weight: bold; border-left: 4px solid #4a90d9;
                   padding-left: 12px; margin: 28px 0 14px; }
  .footer-bar { text-align: center; margin: 40px 0 20px; }
  .footer-bar a { color: #4a90d9; text-decoration: none; font-size: 0.95rem; }
  .footer-bar a:hover { text-decoration: underline; }
  .updated-note { color: #555; font-size: 0.85rem; margin-top: 12px; }
</style>
</head>
<body>

<header>
  <h1>📊 批改结果 — {{ problem_set.exam_id }}</h1>
</header>

<div class="container">

  {# ── 总分概览 ── #}
  {% set n_correct = report | selectattr('score', 'ge', 0.99) | list | length %}
  {% set n_partial  = report | selectattr('score', 'ge', 0.3)  | selectattr('score', 'lt', 0.99) | list | length %}
  {% set n_wrong    = report | selectattr('score', 'lt', 0.3)  | list | length %}

  <div class="summary-bar">
    <div class="stat correct"><div class="num">{{ n_correct }}</div><div class="lbl">✅ 全对</div></div>
    <div class="stat partial"><div class="num">{{ n_partial }}</div><div class="lbl">⚠️ 少选</div></div>
    <div class="stat wrong">  <div class="num">{{ n_wrong }}</div>  <div class="lbl">❌ 错选/0分</div></div>
    <div class="stat total">  <div class="num">{{ report | length }}</div><div class="lbl">共 N 题</div></div>
  </div>

  {# ── MCQ 反馈（report 前 N 项对应 mcq_section，后 M 项对应 algorithm_section）── #}
  {% if problem_set.mcq_section %}
  <div class="section-title">多项选择题反馈</div>
  {% for i in range(problem_set.mcq_section | length) %}
    {% if i < report | length %}
    {% set item = report[i] %}
    {% set mcq  = problem_set.mcq_section[i] %}
    {% if item.score >= 0.99 %}
      {% set cls = "rc-correct" %}{% set icon = "✅ 全对 (1 分)" %}
    {% elif item.score >= 0.3 %}
      {% set cls = "rc-partial" %}{% set icon = "⚠️ 少选 (1/3 分)" %}
    {% else %}
      {% set cls = "rc-wrong" %}{% set icon = "❌ 错选/未选 (0 分)" %}
    {% endif %}
    <div class="result-card {{ cls }}">
      <div class="card-header">
        <span class="tag-badge">{{ item.tag }}</span>
        <span class="score-badge">{{ icon }}</span>
      </div>
      <p class="desc-text">{{ item.brief_description }}</p>
      {% if item.score < 0.99 and mcq.explanation %}
      <details>
        <summary>查看解析</summary>
        <p>{{ mcq.explanation }}</p>
      </details>
      {% endif %}
    </div>
    {% endif %}
  {% endfor %}
  {% endif %}

  {# ── 算法题反馈 ── #}
  {% set algo_offset = problem_set.mcq_section | length %}
  {% if problem_set.algorithm_section %}
  <div class="section-title">算法编程题反馈</div>
  {% for i in range(problem_set.algorithm_section | length) %}
    {% set idx = algo_offset + i %}
    {% if idx < report | length %}
    {% set item = report[idx] %}
    {% set algo = problem_set.algorithm_section[i] %}
    {% set score_pct = (item.score * 100) | int %}
    {% if score_pct >= 80 %}
      {% set cls = "rc-correct" %}
    {% elif score_pct >= 50 %}
      {% set cls = "rc-partial" %}
    {% else %}
      {% set cls = "rc-wrong" %}
    {% endif %}
    <div class="result-card {{ cls }}">
      <div class="card-header">
        <span class="tag-badge">{{ item.tag }}</span>
        <span class="score-badge">{{ score_pct }} / 100 分</span>
      </div>
      <p class="desc-text">{{ algo.title }} ({{ algo.id }})</p>
    </div>
    {% endif %}
  {% endfor %}
  {% endif %}

  <div class="footer-bar">
    <p class="updated-note">✅ 学习画像已更新</p>
    <p style="margin-top:14px"><a href="/">← 返回首页</a></p>
  </div>

</div>
</body>
</html>
```

- [ ] **Step 2: 运行全部 server 测试**

```bash
uv run pytest tests/test_server.py -v
```

预期：`4 passed`

- [ ] **Step 3: 运行完整套件，确认无回归**

```bash
uv run pytest tests/ profiler/tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add server/templates/result.html
git commit -m "feat: add result.html with per-question feedback and score summary"
```

---

## Task 4: cmd_serve 命令

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 在 `main.py` 末尾（`if __name__ == "__main__":` 之前）添加 `cmd_serve`**

```python
def cmd_serve(port: int = 8080):
    from server.app import create_app
    app = create_app(settings)
    print(f"✅ 试卷服务已启动: http://localhost:{port}")
    print("   Ctrl+C 退出")
    app.run(host="127.0.0.1", port=port, debug=False)
```

- [ ] **Step 2: 在 dispatch 字典和 help 文本中注册 serve 命令**

将 dispatch 行改为：

```python
dispatch = {"run": cmd_run, "grade": cmd_grade, "report": cmd_report, "serve": lambda: cmd_serve(port)}
```

在 `if __name__ == "__main__":` 块中，在 `cmd = sys.argv[1] ...` 之后添加 port 解析：

```python
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    port = 8080
    for arg in sys.argv[2:]:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg == "--port" and sys.argv.index(arg) + 1 < len(sys.argv):
            port = int(sys.argv[sys.argv.index(arg) + 1])

    dispatch = {
        "run": cmd_run,
        "grade": cmd_grade,
        "report": cmd_report,
        "serve": lambda: cmd_serve(port),
    }
    if cmd in dispatch:
        dispatch[cmd]()
    else:
        print("用法: python main.py [run|grade|report|serve]")
        print("  run          — 生成今日试卷")
        print("  grade        — 批改并更新学习画像")
        print("  report       — 单独重新生成进度报告")
        print("  serve [--port=8080]  — 启动本地 web 服务，浏览器作答")
        sys.exit(1)
```

- [ ] **Step 3: 验证 help 信息**

```bash
python main.py 2>&1 | head -6
```

预期：包含 `serve` 命令说明

- [ ] **Step 4: 运行完整测试套件**

```bash
uv run pytest tests/ profiler/tests/ -v
```

预期：全部通过

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: add 'python main.py serve' command with optional --port"
```
