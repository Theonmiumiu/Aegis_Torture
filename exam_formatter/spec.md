1. 需求背景与功能定义

本模块负责将 Sub-project B 生成的原始题目数据转化为人类可读的本地 Markdown 文件。它不仅是排版工具，更是“实验环境准备工具”，负责为你准备好算法题的代码支架（Boilerplate）。

核心功能

Markdown 渲染：生成带有标准层级（H1-H3）、代码块、数学公式（LaTeX）渲染支持的试卷。

ACM 代码支架注入：针对 3 道算法题，自动生成基于 sys.stdin 的 Python 输入模板，确保你开箱即写。

评分规则提示：在多选题部分显著标注“少选得 1/3 分”的提醒。

本地文件管理：以日期命名（如 Exam_20260418.md）并在指定目录下生成文件。

2. 试卷排版结构设计

生成的 Markdown 文件应遵循以下布局：

2.1 试卷头信息 (Header)

试卷 ID 与 生成日期。

预计完成时间建议。

知识点分布（由 A 模块提供的 target_tags 决定）。

2.2 第一部分：多项选择题 (Section: MCQs)

每一题展示：题面、选项 (A, B, C, D)。

预留交互区域：你的答案: [ ]（方便后续 D 模块通过正则解析）。

底部标注：注：本部分多选题，全对得 1 分，漏选得 1/3 分，错选/多选不得分。

2.3 第二部分：算法编程题 (Section: Algorithm)

展示：题目名称（数学伪装名）、题目描述、约束条件（Constraints）、样例输入/输出。

核心：代码支架区。为每道题生成一个代码块，如下所示：

# --- 题目 ID: algo-01 ---
import sys

def solve():
    # 读取输入，例如：
    # n = int(sys.stdin.readline())
    # data = list(map(int, sys.stdin.readline().split()))

    # TODO: 在此处编写你的算法逻辑
    pass

if __name__ == "__main__":
    solve()


3. 核心算法逻辑：代码支架生成器

3.1 动态模板填充

C 模块需要识别 B 模块返回的题目类型，并从预设的 templates/ 中选择合适的读取方式。如果题目描述中包含“多组测试数据”，模板应自动变为：

T = int(sys.stdin.readline())
for _ in range(T):
    solve()


4. API 接口规范 (Python)

模块路径：services/formatter.py

build_daily_exam(problem_set: dict, output_dir: str) -> str

输入参数：

problem_set: Sub-project B 输出的完整 JSON（详见第 7 章）。

output_dir: 本地存储路径。

输出：生成的文件绝对路径。

_inject_boilerplate(problem_data: dict) -> str

功能：私有方法，根据题目给出的 io_spec 生成 Python 代码字符串。

5. 渲染细节约束

LaTeX 支持：所有的变量（如 $n$, $k$）和数学表达式必须包裹在 $ 符号中，以确保在支持 LaTeX 的编辑器中完美显示。

答案隔离：严禁在生成的试卷文件中包含 correct_answers 或 explanation 字段。C 模块在渲染时必须主动剔除这些敏感信息，防止用户通过 Markdown 源码作弊。

6. 异常处理

目录权限：检查 output_dir 是否可写。

字符编码：强制使用 UTF-8 编码写入文件，防止中文字符在不同操作系统下乱码。

7. 输入数据架构 (Input Data Schema)

C 模块期待从 Sub-project B 接收到如下结构的字典（problem_set）：

{
  "exam_id": "EXAM-2026-04-18-001",
  "exam_date": "2026-04-18",
  "target_tags": ["Concurrency", "RAG"],
  "algorithm_section": [
    {
      "id": "algo-01",
      "title": "环形二进制串",
      "description": "给定长度为 n 的串...",
      "constraints": "1 <= n <= 2*10^5",
      "sample_io": [
        {"input": "3 8 11001001", "output": "4"}
      ],
      "io_spec": {
        "type": "multi_test_case" 
      }
    }
  ],
  "mcq_section": [
    {
      "id": "mcq-01",
      "tag": "Concurrency",
      "text": "关于 asyncio，以下说法正确的是？",
      "options": {
        "A": "选项内容...",
        "B": "选项内容...",
        "C": "选项内容...",
        "D": "选项内容..."
      }
    }
  ]
}


字段说明：

io_spec.type: 可选值为 single_test_case 或 multi_test_case。用于决定代码支架是否包含 for _ in range(T) 循环。

注意: problem_set 中可能包含 std_solution 或 correct_options 字段（由 B 模块生成），但 C 模块严禁将这些字段内容渲染进 Markdown 文件。