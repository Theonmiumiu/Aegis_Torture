import json
import os
# 如果在本地实际运行，请确保目录结构为：
# project_root/
# ├── main.py
# └── services/
#     ├── __init__.py (空文件即可)
#     └── formatter.py
from services.formatter import build_daily_exam


def main():
    # 模拟 Sub-project B 传来的 JSON 数据 (包含被污染的答案数据)
    mock_data = {
        "exam_id": "EXAM-2026-04-18-001",
        "exam_date": "2026-04-18",
        "target_tags": ["Concurrency", "RAG"],
        "algorithm_section": [
            {
                "id": "algo-01",
                "title": "环形二进制串",
                "description": "给定长度为 $n$ 的串...",
                "constraints": "1 <= n <= 2*10^5",
                "sample_io": [
                    {"input": "3\n8\n11001001", "output": "4"}
                ],
                "io_spec": {
                    "type": "multi_test_case"
                },
                "std_solution": "def solve(): pass # 绝对不能出现在生成的 md 中"
            }
        ],
        "mcq_section": [
            {
                "id": "mcq-01",
                "tag": "Concurrency",
                "text": "关于 asyncio，以下说法正确的是？",
                "options": {
                    "A": "单线程并发",
                    "B": "多线程并发",
                    "C": "阻塞I/O",
                    "D": "依赖回调"
                },
                "correct_answers": ["A"],  # 绝对不能出现在生成的 md 中
                "explanation": "因为 asyncio 是单线程..."  # 不能出现
            }
        ]
    }

    output_directory = "./output"

    try:
        file_path = build_daily_exam(mock_data, output_directory)
        print(f"✅ 试卷生成成功！\n文件路径: {file_path}")
    except Exception as e:
        print(f"❌ 生成失败: {str(e)}")


if __name__ == "__main__":
    main()