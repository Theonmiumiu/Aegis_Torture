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

    for snip in problem_set.get("code_snippet_section", []):
        sid = snip["id"]
        code = code_answers.get(sid, "")
        lines.append(f"# --- 题目 ID: {sid} ---")
        lines.append("```python")
        lines.append(code if code else "# 未提交代码")
        lines.append("```")

    return "\n".join(lines)


def create_app(settings):
    app = Flask(__name__, template_folder="templates")

    @app.route("/favicon.ico")
    def favicon():
        return "", 204

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
