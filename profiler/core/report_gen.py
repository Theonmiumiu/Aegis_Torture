import os
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List


def _get_beijing_time() -> datetime:
    """获取当前的北京时间 (UTC+8)"""
    tz_bj = timezone(timedelta(hours=8))
    return datetime.now(tz_bj)


def _load_stats(storage_path: str) -> Dict[str, Any]:
    """读取已有的统计数据"""
    file_path = os.path.join(storage_path, "mcq_stats.json")
    if not os.path.exists(file_path):
        return {"tags": {}, "global_config": {"total_exams_taken": 0}}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"读取数据文件失败: {e}")
        return {"tags": {}, "global_config": {"total_exams_taken": 0}}


def _format_table_row(tag: str, data: dict) -> str:
    """格式化单行表格数据"""
    level = data.get("level", 50)
    fail_streak = data.get("fail_streak", 0)
    last_seen = data.get("last_seen", "N/A")

    # 状态指示器
    streak_alert = " ⚠️" if fail_streak >= 2 else ""

    return f"| {tag} | {level:.1f}/100 | {fail_streak}{streak_alert} | {last_seen} |"


def generate_report(storage_path: str) -> bool:
    """
    读取 mcq_stats.json，生成人类可读的 learning_progress.md。
    时间统一使用北京时间。
    """
    stats = _load_stats(storage_path)
    tags_data = stats.get("tags", {})
    total_exams = stats.get("global_config", {}).get("total_exams_taken", 0)

    # 获取北京时间
    bj_time = _get_beijing_time()
    report_time_str = bj_time.strftime("%Y-%m-%d %H:%M:%S (北京时间)")

    # 分类标签
    mastered = []  # L > 80
    developing = []  # 30 <= L <= 80
    weaknesses = []  # L < 30 或 fail_streak >= 2

    total_level = 0

    for tag, data in tags_data.items():
        level = data.get("level", 50)
        fail_streak = data.get("fail_streak", 0)
        total_level += level

        # 将数据包装以便排序
        item = (tag, data)

        if level < 30 or fail_streak >= 2:
            weaknesses.append(item)
        elif level > 80:
            mastered.append(item)
        else:
            developing.append(item)

    # 按规则排序：弱项按连续错误次数和掌握度升序排列，其余按掌握度降序排列
    weaknesses.sort(key=lambda x: (x[1].get("fail_streak", 0), -x[1].get("level", 50)), reverse=True)
    developing.sort(key=lambda x: x[1].get("level", 50), reverse=True)
    mastered.sort(key=lambda x: x[1].get("level", 50), reverse=True)

    avg_level = (total_level / len(tags_data)) if tags_data else 0.0

    # 组装 Markdown 内容
    md_lines = [
        "# 📊 MCQ 学习进度与知识点画像",
        f"**生成时间**: {report_time_str}\n",
        "## 📈 全局统计",
        f"- **已完成测试次数**: {total_exams}",
        f"- **已追踪知识点数**: {len(tags_data)}",
        f"- **全局平均掌握度**: {avg_level:.1f} / 100\n",
        "---",
        "## 🔴 核心弱项 (Priority Targets)",
        "> *掌握度 < 30 或 连续选错 ≥ 2 次，系统将在接下来的测试中显著提高其抽样权重。*",
        "| 知识点 (Tag) | 掌握度 (Level) | 连错次数 | 最后考察日期 |",
        "| :--- | :---: | :---: | :--- |"
    ]

    if not weaknesses:
        md_lines.append("| (暂无数据) | - | - | - |")
    else:
        for tag, data in weaknesses:
            md_lines.append(_format_table_row(tag, data))

    md_lines.extend([
        "\n## 🟡 巩固提升 (Developing)",
        "> *处于遗忘曲线与模糊地带的知识点，将按 Epsilon-Greedy 算法常态化抽样。*",
        "| 知识点 (Tag) | 掌握度 (Level) | 连错次数 | 最后考察日期 |",
        "| :--- | :---: | :---: | :--- |"
    ])

    if not developing:
        md_lines.append("| (暂无数据) | - | - | - |")
    else:
        for tag, data in developing:
            md_lines.append(_format_table_row(tag, data))

    md_lines.extend([
        "\n## 🟢 已掌握领域 (Mastered)",
        "> *掌握度 > 80，已移入探索池，仅保留极小概率抽样以防长期遗忘。*",
        "| 知识点 (Tag) | 掌握度 (Level) | 连错次数 | 最后考察日期 |",
        "| :--- | :---: | :---: | :--- |"
    ])

    if not mastered:
        md_lines.append("| (暂无数据) | - | - | - |")
    else:
        for tag, data in mastered:
            md_lines.append(_format_table_row(tag, data))

    md_lines.append("\n---\n*本报告由 Sub-project A: Profiler 自动生成。*")

    # 写入文件
    md_content = "\n".join(md_lines)
    output_path = os.path.join(storage_path, "learning_progress.md")

    try:
        # 确保目录存在
        os.makedirs(storage_path, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        return True
    except Exception as e:
        print(f"写入报告文件失败: {e}")
        return False

# 示例调用说明：
# if __name__ == "__main__":
#     generate_report("../data")