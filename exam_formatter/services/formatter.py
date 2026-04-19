import os
import sys
import datetime


def _inject_boilerplate(problem_data: dict) -> str:
    """
    私有方法：根据题目信息生成对应的 Python 代码支架
    """
    io_spec = problem_data.get("io_spec", {})
    io_type = io_spec.get("type", "single_test_case")
    problem_id = problem_data.get("id", "unknown-algo")

    # 基础的 solve 函数模板
    solve_func = """import sys

def solve():
    # 读取输入，例如：
    # n = int(sys.stdin.readline())
    # data = list(map(int, sys.stdin.readline().split()))

    # TODO: 在此处编写你的算法逻辑
    pass"""

    # 根据 io_type 决定主函数的调用方式
    if io_type == "multi_test_case":
        main_func = """if __name__ == "__main__":
    T = int(sys.stdin.readline().strip())
    for _ in range(T):
        solve()"""
    else:
        main_func = """if __name__ == "__main__":
    solve()"""

    # 组合为完整的代码块
    boilerplate = f"# --- 题目 ID: {problem_id} ---\n{solve_func}\n\n{main_func}"
    return boilerplate


def build_daily_exam(problem_set: dict, output_dir: str) -> str:
    """
    核心接口：将题目 JSON 数据转换为 Markdown 试卷并落盘
    """
    # 1. 解析日期并生成文件名 (如 2026-04-18 -> Exam_20260418.md)
    # 如果 JSON 中没有日期，则默认使用当前北京时间
    exam_date_str = problem_set.get("exam_date")
    if exam_date_str:
        try:
            date_obj = datetime.datetime.strptime(exam_date_str, "%Y-%m-%d")
            file_date = date_obj.strftime("%Y%m%d")
        except ValueError:
            file_date = exam_date_str.replace("-", "")
    else:
        # 兜底：使用北京时间 (UTC+8)
        bj_tz = datetime.timezone(datetime.timedelta(hours=8))
        file_date = datetime.datetime.now(bj_tz).strftime("%Y%m%d")

    bj_tz = datetime.timezone(datetime.timedelta(hours=8))
    time_str = datetime.datetime.now(bj_tz).strftime("%H%M%S")
    filename = f"Exam_{file_date}_{time_str}.md"

    # 2. 检查目录权限与创建目录
    abs_output_dir = os.path.abspath(output_dir)
    if not os.path.exists(abs_output_dir):
        os.makedirs(abs_output_dir, exist_ok=True)

    if not os.access(abs_output_dir, os.W_OK):
        raise PermissionError(f"目录不可写，请检查权限: {abs_output_dir}")

    file_path = os.path.join(abs_output_dir, filename)

    # 3. 提取基本信息并开始构建 Markdown 字符串
    exam_id = problem_set.get("exam_id", "N/A")
    target_tags = ", ".join(problem_set.get("target_tags", []))

    md_lines = []

    # 【修复截断】: 动态生成 Markdown 的代码块围栏 (三个反引号)，防止被文档系统错误解析
    fence = chr(96) * 3

    # --- 渲染试卷头信息 ---
    md_lines.append(f"# 每日算法与工程评测")
    md_lines.append(f"**试卷 ID**: `{exam_id}` | **生成日期**: {exam_date_str or file_date}")
    md_lines.append(f"**知识点分布**: {target_tags}")
    md_lines.append(f"**预计完成时间**: 120 分钟\n")
    md_lines.append("---\n")

    # --- 渲染 MCQ 部分 ---
    mcq_section = problem_set.get("mcq_section", [])
    if mcq_section:
        md_lines.append("## 第一部分：多项选择题 (MCQs)")
        md_lines.append("> **注：本部分多选题，全对得 1 分，漏选得 1/3 分，错选/多选不得分。**\n")

        for idx, mcq in enumerate(mcq_section, start=1):
            type_label = "🎓 学术" if mcq.get("question_type") == "academic" else "🏭 业务场景"
            md_lines.append(f"### {idx}. {mcq.get('text')} [标签: {mcq.get('tag', 'General')}] [{type_label}]")
            options = mcq.get("options", {})
            for key, val in options.items():
                md_lines.append(f"- **{key}**: {val}")
            md_lines.append("\n**你的答案: [ ]**\n")

        md_lines.append("---\n")

    # --- 渲染算法题部分 ---
    algo_section = problem_set.get("algorithm_section", [])
    if algo_section:
        md_lines.append("## 第二部分：算法编程题")

        for idx, algo in enumerate(algo_section, start=1):
            title = algo.get("title", "未命名题目")
            md_lines.append(f"### 题 {idx}: {title} (ID: `{algo.get('id')}`)\n")
            md_lines.append(f"**题目描述**:\n{algo.get('description')}\n")
            md_lines.append(f"**约束条件**:\n{fence}text\n{algo.get('constraints')}\n{fence}\n")

            sample_io = algo.get("sample_io", [])
            if sample_io:
                md_lines.append("**样例输入/输出**:")
                for io_idx, io in enumerate(sample_io, start=1):
                    md_lines.append(
                        f"样例 {io_idx}:\n{fence}text\n输入:\n{io.get('input')}\n\n输出:\n{io.get('output')}\n{fence}\n")

            code_boilerplate = _inject_boilerplate(algo)
            md_lines.append("**代码实现区**:")
            md_lines.append(f"{fence}python")
            md_lines.append(code_boilerplate)
            md_lines.append(f"{fence}\n")

        md_lines.append("---\n")

    # --- 渲染算法模块手撕部分 ---
    snippet_section = problem_set.get("code_snippet_section", [])
    if snippet_section:
        md_lines.append("## 第三部分：算法模块手撕")
        md_lines.append("> **考察目标：不借助任何框架 API，从零手写核心算法模块代码。评分关注正确性与实现思路。**\n")

        # 预制常用数据结构类定义，免去 ACM 模式下需自行声明的麻烦
        md_lines.append("### 预制类定义（可直接使用，无需重写）\n")
        md_lines.append(f"{fence}python")
        md_lines.append(
            "# 链表节点\n"
            "class ListNode:\n"
            "    def __init__(self, val=0, next=None):\n"
            "        self.val = val\n"
            "        self.next = next\n"
            "\n"
            "# 双向链表节点\n"
            "class DListNode:\n"
            "    def __init__(self, val=0, prev=None, next=None):\n"
            "        self.val = val\n"
            "        self.prev = prev\n"
            "        self.next = next\n"
            "\n"
            "# 二叉树节点\n"
            "class TreeNode:\n"
            "    def __init__(self, val=0, left=None, right=None):\n"
            "        self.val = val\n"
            "        self.left = left\n"
            "        self.right = right\n"
            "\n"
            "# N 叉树节点\n"
            "class NTreeNode:\n"
            "    def __init__(self, val=0, children=None):\n"
            "        self.val = val\n"
            "        self.children = children or []\n"
            "\n"
            "# 图（邻接表）\n"
            "from collections import defaultdict, deque\n"
            "# graph = defaultdict(list)  # graph[u].append(v)"
        )
        md_lines.append(f"{fence}\n")

        for idx, snip in enumerate(snippet_section, start=1):
            sid = snip.get("id", f"snippet-{idx:02d}")
            difficulty_label = "🔴 Hard" if snip.get("difficulty") == "hard" else "🟡 Medium"
            md_lines.append(f"### 手撕 {idx}: {snip.get('title')} [标签: {snip.get('tag')}] [{difficulty_label}]")
            md_lines.append(f"\n**题目要求**:\n{snip.get('desc')}\n")
            md_lines.append(f"**思路提示**:\n> {snip.get('hint')}\n")
            md_lines.append("**你的实现**:")
            md_lines.append(f"{fence}python")
            md_lines.append(f"# --- 题目 ID: {sid} ---")
            md_lines.append("# 在此处手写你的实现代码")
            md_lines.append(f"{fence}\n")

        md_lines.append("---\n")

    # 4. 强制使用 UTF-8 写入本地文件
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return file_path