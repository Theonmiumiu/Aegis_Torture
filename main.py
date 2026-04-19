import sys
import os
import json
import glob
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

from config import settings
from profiler.core.profiler import get_mcq_config, update_mcq_stats
from profiler.core.report_gen import generate_report
from problem_synthesizer.core.local_extractor import LocalBankExtractor
from problem_synthesizer.core.llm_coder import MathShellCoder
from problem_synthesizer.core.mcq_generator import MCQGenerator
from problem_synthesizer.core.code_snippet_generator import CodeSnippetGenerator
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
    mcq_config = get_mcq_config(settings.data_path, num_questions=20)
    tags = mcq_config.get("target_tags", [])
    print(f"      今日目标标签: {tags if tags else '（全领域随机）'}")

    print("[2/3] 生成今日题目包（并发）...")
    llm_client = _get_llm_client()
    extractor = LocalBankExtractor(settings.local_bank_path)
    coder = MathShellCoder(llm_client)
    mcq_gen = MCQGenerator(llm_client)
    snippet_gen = CodeSnippetGenerator(llm_client)

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

    print(f"      并发提交: 1 道 LLM 算法题 + {num_batches} 批 MCQ（每批最多 {batch_size} 道）+ 手撕题...")

    # 并发：LLM 算法题 + 所有 MCQ 批次 + 手撕题同时跑
    futures_map = {}
    with ThreadPoolExecutor(max_workers=num_batches + 2) as executor:
        futures_map[executor.submit(coder.generate_problem, mcq_config)] = "algo"
        futures_map[executor.submit(snippet_gen.generate, 3)] = "snippets"
        for i in range(num_batches):
            batch_count = min(batch_size, total_mcqs - i * batch_size)
            futures_map[executor.submit(mcq_gen.generate_batch, all_tags, batch_count)] = f"mcq_{i}"

    mcqs = []
    algo_problem = None
    snippets = []
    for future, key in futures_map.items():
        try:
            result = future.result()
        except Exception as e:
            print(f"      [警告] {key} 生成失败: {e}")
            continue
        if key == "algo":
            algo_problem = result
        elif key == "snippets":
            snippets = result
        else:
            mcqs.extend(result)

    if algo_problem:
        algo_problem["id"] = f"algo-{len(coding_problems)+1:02d}"
        coding_problems.append(algo_problem)

    print(f"      生成完毕：{len(coding_problems)} 道算法题，{len(mcqs)} 道多选题，{len(snippets)} 道手撕题")

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
        "code_snippet_section": snippets,
    }

    print("[3/3] 排版试卷...")
    exam_path = build_daily_exam(problem_set, settings.output_path)

    # 从生成的试卷文件名中提取 key，确保 JSON 与 md 永远一一对应
    exam_key = os.path.basename(exam_path).replace("Exam_", "").replace(".md", "")
    ps_path = os.path.join(settings.data_path, f"problem_set_{exam_key}.json")
    with open(ps_path, "w", encoding="utf-8") as f:
        json.dump(problem_set, f, indent=2, ensure_ascii=False)

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


def cmd_serve(port: int = 8080):
    from server.app import create_app
    app = create_app(settings)
    print(f"✅ 试卷服务已启动: http://localhost:{port}")
    print("   Ctrl+C 退出")
    app.run(host="127.0.0.1", port=port, debug=False)


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
