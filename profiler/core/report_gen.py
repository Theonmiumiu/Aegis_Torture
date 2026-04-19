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
    wrong_history = stats.get("wrong_history", [])

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

    # --- 综合掌握情况评估 ---
    md_lines.extend([
        "\n---",
        "## 📋 综合掌握情况评估",
    ])
    if not tags_data:
        md_lines.append("\n> 暂无考试记录，请先完成至少一次考试并批改。")
    else:
        weakness_count = len(weaknesses)
        developing_count = len(developing)
        mastered_count = len(mastered)
        total_tags = len(tags_data)

        if avg_level >= 75:
            overall = "整体掌握情况**优秀**，大部分领域已达到熟练水平。建议继续保持，重点攻克剩余弱项。"
        elif avg_level >= 55:
            overall = "整体掌握情况**良好**，核心知识点有一定基础，仍有提升空间，需针对弱项强化训练。"
        elif avg_level >= 35:
            overall = "整体掌握情况**中等**，多个知识点尚未稳固，建议系统性复习薄弱领域。"
        else:
            overall = "整体掌握情况**需要加强**，大量知识点掌握度不足，建议从基础开始系统性学习。"

        md_lines.extend([
            f"\n{overall}",
            f"\n**知识点分布**: 已掌握 {mastered_count} 个 | 巩固中 {developing_count} 个 | 核心弱项 {weakness_count} 个 | 合计 {total_tags} 个",
            f"**全局平均掌握度**: {avg_level:.1f} / 100\n",
        ])

        if weaknesses:
            top_weak = weaknesses[:3]
            weak_names = "、".join(f"`{t}`" for t, _ in top_weak)
            md_lines.append(f"**最需优先复习**: {weak_names}\n")

    # --- 错题复习日历（按日期分组） ---
    md_lines.extend([
        "---",
        "## 📅 错题复习日历",
        "> *记录近 30 天内所有未全对的题目，帮助你有针对性地复习。*\n",
    ])

    if not wrong_history:
        md_lines.append("> 暂无错题记录。继续加油！\n")
    else:
        # 按日期分组，日期降序（最新的在前）
        from collections import defaultdict
        by_date: dict = defaultdict(list)
        for record in wrong_history:
            by_date[record.get("date", "未知日期")].append(record)

        section_labels = {
            "mcq": "多选题",
            "algorithm": "算法编程题",
            "code_snippet": "算法模块手撕",
        }

        for date_str in sorted(by_date.keys(), reverse=True):
            records = by_date[date_str]
            md_lines.append(f"### {date_str}（共 {len(records)} 道未全对）\n")
            md_lines.append("| 题型 | 知识点标签 | 题目 | 得分 |")
            md_lines.append("| :---: | :--- | :--- | :---: |")
            for r in records:
                sec = section_labels.get(r.get("section", "mcq"), "多选题")
                tag = r.get("tag", "-")
                qtext = r.get("question_text", "-")
                # 截断长题目文本
                if len(qtext) > 60:
                    qtext = qtext[:57] + "..."
                score_val = r.get("score", 0.0)
                if score_val < 0.05:
                    score_disp = "❌ 0分"
                elif score_val < 0.5:
                    score_disp = f"⚠️ {score_val:.0%}"
                else:
                    score_disp = f"🔶 {score_val:.0%}"
                md_lines.append(f"| {sec} | {tag} | {qtext} | {score_disp} |")
            md_lines.append("")

    md_lines.append("\n---\n*本报告由 Aegis Torture Profiler 自动生成。*")

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