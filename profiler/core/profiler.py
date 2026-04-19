import json
import os
import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 默认状态模板
DEFAULT_STATS = {
    "tags": {},
    "global_config": {
        "epsilon": 0.15,
        "total_exams_taken": 0
    },
    "history_buffer": []  # 格式: [{"date": "YYYY-MM-DD", "description": "..."}]
}


def _get_current_date_str() -> str:
    """获取当前日期的字符串表示，用于状态记录。"""
    return datetime.now().strftime("%Y-%m-%d")


def _load_stats(storage_path: str) -> dict:
    """加载 JSON 状态文件，如果不存在则初始化默认状态。"""
    file_path = os.path.join(storage_path, "mcq_stats.json")
    if not os.path.exists(file_path):
        # 确保目录存在
        os.makedirs(storage_path, exist_ok=True)
        return DEFAULT_STATS.copy()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading stats: {e}")
        return DEFAULT_STATS.copy()


def _save_stats(storage_path: str, data: dict) -> bool:
    """将状态存入 JSON 文件。"""
    file_path = os.path.join(storage_path, "mcq_stats.json")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving stats: {e}")
        return False


def _calculate_weight(tag_data: dict, current_date: datetime) -> float:
    """
    计算特定知识点的抽样权重 W:
    W = (100 - L) * (1 + FailCount * 0.5) + RecencyBonus
    """
    level = tag_data.get("level", 50)
    fail_streak = tag_data.get("fail_streak", 0)
    last_seen_str = tag_data.get("last_seen", _get_current_date_str())

    last_seen_date = datetime.strptime(last_seen_str, "%Y-%m-%d")
    days_since_seen = (current_date - last_seen_date).days

    # 模拟遗忘曲线：距离上次考察越久，权重增加越多 (每天增加 2.0 的权重)
    recency_bonus = max(0, days_since_seen * 2.0)

    weight = (100 - level) * (1 + fail_streak * 0.5) + recency_bonus
    return max(0.1, weight)  # 保证最小权重不为 0


def _weighted_sample_without_replacement(population: List[str], weights: List[float], k: int) -> List[str]:
    """
    不放回的加权随机抽样 (A-Res 算法的一种简单替代实现)。
    Theon, 考虑到你需要严格的概率分布控制，这里采用按权重计算 key 的方式进行排序截取。
    """
    if k >= len(population):
        return population

    # 使用权重和随机数生成排序键
    weighted_keys = [
        (math.pow(random.random(), 1.0 / w), item)
        for item, w in zip(population, weights)
    ]
    # 取键值最大的前 k 个
    weighted_keys.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in weighted_keys[:k]]


def get_mcq_config(storage_path: str, num_questions: int = 10) -> dict:
    """
    功能：计算并生成今日 MCQ 的考察指令。
    """
    stats = _load_stats(storage_path)
    tags_data = stats.get("tags", {})
    global_config = stats.get("global_config", {})
    epsilon = global_config.get("epsilon", 0.15)

    current_date = datetime.now()

    explore_pool = []
    exploit_pool = []
    exploit_weights = []

    # 1. 划分探索池 (L > 80) 与开发池 (L <= 80)
    for tag, data in tags_data.items():
        if data.get("level", 50) > 80:
            explore_pool.append(tag)
        else:
            exploit_pool.append(tag)
            exploit_weights.append(_calculate_weight(data, current_date))

    # 计算名额分配
    explore_count = int(num_questions * epsilon)
    exploit_count = num_questions - explore_count

    # 修正名额池不足的情况
    if len(explore_pool) < explore_count:
        exploit_count += (explore_count - len(explore_pool))
        explore_count = len(explore_pool)

    if len(exploit_pool) < exploit_count:
        # 如果开发池标签不够，拿探索池补足（但不能超过探索池实际大小）
        extra_needed = exploit_count - len(exploit_pool)
        explore_count = min(len(explore_pool), explore_count + extra_needed)
        exploit_count = len(exploit_pool)

    # 2. 抽样
    selected_tags = []
    if explore_count > 0:
        selected_tags.extend(random.sample(explore_pool, explore_count))

    if exploit_count > 0:
        selected_tags.extend(
            _weighted_sample_without_replacement(exploit_pool, exploit_weights, exploit_count)
        )

    # 3. 提取 History Buffer 作为 exclusion_list
    recent_descriptions = [
        item["description"] for item in stats.get("history_buffer", [])
    ]

    return {
        "target_tags": selected_tags,
        "difficulty": "hard",  # 默认设置为 hard，可根据总体平均 level 动态拓展
        "constraints": {
            "num_questions": num_questions,
            "exclusion_list": recent_descriptions
        }
    }


def update_mcq_stats(report_data: List[Dict[str, Any]], storage_path: str) -> bool:
    """
    功能：解析批改报告，执行掌握度状态转移，并更新历史缓存 (Anti-Bootstrap)。
    """
    stats = _load_stats(storage_path)
    tags_data = stats.get("tags", {})
    history_buffer = stats.get("history_buffer", [])

    current_date_str = _get_current_date_str()
    current_date = datetime.strptime(current_date_str, "%Y-%m-%d")

    wrong_history = stats.get("wrong_history", [])

    for item in report_data:
        tag = item.get("tag")
        score = float(item.get("score", 0.0))
        description = item.get("brief_description", "")

        # 将描述加入缓存，用于抗过拟合
        if description:
            history_buffer.append({
                "date": current_date_str,
                "description": description
            })

        # 记录错题详情（score < 1.0 即有问题，score < 0.3 为严重错误）
        if score < 0.99:
            wrong_history.append({
                "date": current_date_str,
                "tag": tag,
                "section": item.get("section", "mcq"),
                "question_text": item.get("question_text", description)[:150],
                "score": round(score, 2),
            })

        if tag not in tags_data:
            tags_data[tag] = {"level": 50, "fail_streak": 0, "last_seen": current_date_str}

        tag_state = tags_data[tag]
        tag_state["last_seen"] = current_date_str

        # 核心状态转移逻辑
        old_level = tag_state["level"]
        if score >= 0.99:  # 全对 (考虑浮点精度)
            tag_state["level"] = min(100, old_level + 10)
            tag_state["fail_streak"] = 0
        elif score >= 0.3:  # 少选 (通常为 0.33)
            tag_state["level"] = min(100, old_level + 2)
            # fail_streak 保持平稳，不清零也不增加
        else:  # 错选/多选 (0分)
            tag_state["level"] = max(0, old_level - 15)
            tag_state["fail_streak"] += 1

    # 清理过期历史记录 (超过 3 天)
    cutoff_date = current_date - timedelta(days=3)
    filtered_buffer = []
    for record in history_buffer:
        try:
            record_date = datetime.strptime(record["date"], "%Y-%m-%d")
            if record_date >= cutoff_date:
                filtered_buffer.append(record)
        except ValueError:
            continue  # 忽略日期解析错误的非法记录

    # 保留最近 30 天的错题记录
    cutoff_wrong = current_date - timedelta(days=30)
    wrong_history = [
        r for r in wrong_history
        if _safe_parse_date(r.get("date", "")) >= cutoff_wrong
    ]

    stats["history_buffer"] = filtered_buffer
    stats["wrong_history"] = wrong_history
    stats["tags"] = tags_data
    stats["global_config"]["total_exams_taken"] = stats["global_config"].get("total_exams_taken", 0) + 1

    return _save_stats(storage_path, stats)


def _safe_parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return datetime(2000, 1, 1)