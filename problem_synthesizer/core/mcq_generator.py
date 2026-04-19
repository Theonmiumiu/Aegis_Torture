import json
import uuid
import random
from typing import Dict, Any, List

from problem_synthesizer.prompts.templates import MCQ_PROMPT_TEMPLATE, MCQ_BATCH_PROMPT_TEMPLATE


class MCQGenerator:
    """
    多项选择题生成器 (MCQ Generator)
    负责根据目标标签定向生成具有高度迷惑性的多项选择题。
    """

    def __init__(self, llm_client):
        """
        :param llm_client: 封装好的 LLM 客户端实例（包含重试机制）
        """
        self.llm_client = llm_client

        # 兜底全领域题库标签（当 A 模块未提供 target_tags 时使用）
        self.fallback_tags = [
            "并发与多线程 (Concurrency)",
            "分布式锁与事务 (Distributed Systems)",
            "数据库索引与调优 (Database Tuning)",
            "检索增强生成 (RAG) 与大模型基础",
            "统计推断与A/B测试 (A/B Testing)",
            "高频交易系统架构 (HFT Architecture)",
            "缓存一致性协议 (Cache Coherence)",
            "微服务熔断与限流 (Microservices)",
            "网络协议与传输层 (HTTP/2, WebSocket, QUIC, gRPC, TLS)",
            "分布式数据一致性与状态管理 (CAP定理, CRDT, Eventual Consistency, Saga模式)",
            "强化学习与RLHF (PPO, DPO, GRPO, 奖励建模, 价值对齐)",
            "大模型架构原理 (Transformer, BERT, LLaMA, Mamba/SSM, MoE, 多头注意力机制)",
            "大模型微调技术 (LoRA, QLoRA, Prompt Tuning, Full Fine-tuning, PEFT, 灾难性遗忘)",
            "深度学习经典模型与算法 (CNN, RNN, LSTM, ResNet, BatchNorm, Dropout, 优化器)",
            "经典自然语言处理应用、对比等 (N-gram, HMM, CRF, TF-IDF, LDA, LSA, 词向量, BERT vs GPT, 命名实体识别, 文本分类, 机器翻译, 情感分析, 交叉熵, BPC, BPW, 困惑度/Perplexity)",
            "经典机器学习算法 (决策树, 随机森林, SVM, 梯度提升, XGBoost, K-means, PCA, 正则化)",
        ]

    def _build_prompt(self, tag: str, count: int) -> str:
        """
        构建生成 MCQ 的 Prompt，严格限制选项数量、正确答案数量以及混淆项设计逻辑。
        """
        return MCQ_PROMPT_TEMPLATE.format(tag=tag, count=count).strip()

    def generate_mcqs(self, config_from_a: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        对外主接口：根据 A 模块配置生成试卷所需的多选题集合。
        """
        target_tags = config_from_a.get("target_tags", [])

        # 容错处理：若 target_tags 为空，自动切换至“全领域随机抽样”模式
        if not target_tags:
            # 随机抽取 2 个兜底标签
            target_tags = random.sample(self.fallback_tags, 2)

        all_mcqs = []

        # 为每个 tag 生成 1-2 道题目 (根据总题量需求调整，这里设定为每个 tag 1 题，保障多样性)
        for tag in target_tags:
            prompt = self._build_prompt(tag, count=1)

            try:
                # 多选题需要高逻辑性，temperature 设低一点以保证严谨度
                response_text = self.llm_client.generate_text(prompt, temperature=0.2)

                # 净化 LLM 输出
                clean_json_str = response_text.replace("```json", "").replace("```", "").strip()
                parsed_mcqs = json.loads(clean_json_str)

                # 为每道题注入必要的系统元数据
                for mcq in parsed_mcqs:
                    # 校验 LLM 是否乖乖听话输出了 2-3 个正确选项，进行防御性编程
                    correct_count = len(mcq.get("correct_options", []))
                    if correct_count > 3:
                        import logging as _logging
                        _logging.getLogger(__name__).warning(
                            f"LLM 为 {tag} 返回了 {correct_count} 个正确选项（期望 2-3），截断至 3 个"
                        )
                        mcq["correct_options"] = mcq["correct_options"][:3]
                    elif correct_count < 2:
                        import logging as _logging
                        _logging.getLogger(__name__).warning(
                            f"LLM 为 {tag} 返回了 {correct_count} 个正确选项（期望 2-3），使用默认值"
                        )
                        existing = mcq.get("correct_options") or []
                        if len(existing) < 2:
                            mcq["correct_options"] = (existing + ["A", "B"])[:2]

                    mcq_record = {
                        "question_id": str(uuid.uuid4()),
                        "tag": tag,
                        "text": mcq.get("text", "题目生成失败"),
                        "options": mcq.get("options", {}),
                        "correct_options": mcq.get("correct_options"),
                        "explanation": mcq.get("explanation", "无解析")
                    }
                    all_mcqs.append(mcq_record)

            except json.JSONDecodeError as e:
                # 降级容错机制
                fallback_mcq = {
                    "question_id": str(uuid.uuid4()),
                    "tag": tag,
                    "text": f"（系统降级补偿题）关于 {tag}，以下说法正确的是？",
                    "options": {
                        "A": "这是一个正确的基础描述。",
                        "B": "这也是一个正确的基础描述。",
                        "C": "这是一个错误描述（降级生成）。",
                        "D": "这是一个不相关的描述。"
                    },
                    "correct_options": ["A", "B"],
                    "explanation": f"LLM 生成失败，触发容错补偿。JSON解析错误信息: {str(e)}"
                }
                all_mcqs.append(fallback_mcq)
            except Exception as e:
                print(f"[Warning] 为标签 {tag} 生成 MCQ 时发生异常: {str(e)}")
                continue

        return all_mcqs

    def generate_batch(self, tags: List[str], count: int) -> List[Dict[str, Any]]:
        """
        单次 LLM 请求生成 count 道题，出题范围覆盖所有 tags。
        每批按 1:1 比例出题：一半学术知识考察，一半业务情景应用。
        """
        if not tags:
            tags = random.sample(self.fallback_tags, min(2, len(self.fallback_tags)))

        academic_count = count // 2
        business_count = count - academic_count

        tags_str = "、".join(tags)
        prompt = MCQ_BATCH_PROMPT_TEMPLATE.format(
            tags_str=tags_str,
            count=count,
            academic_count=academic_count,
            business_count=business_count,
        ).strip()

        valid_types = {"academic", "business_scenario"}

        try:
            response_text = self.llm_client.generate_text(prompt, temperature=0.2)
            clean_json_str = response_text.replace("```json", "").replace("```", "").strip()
            parsed_mcqs = json.loads(clean_json_str)

            result = []
            for i, mcq in enumerate(parsed_mcqs):
                tag = mcq.get("tag") or tags[i % len(tags)]

                correct_count = len(mcq.get("correct_options", []))
                if correct_count > 3:
                    mcq["correct_options"] = mcq["correct_options"][:3]
                elif correct_count < 2:
                    existing = mcq.get("correct_options") or []
                    mcq["correct_options"] = (existing + ["A", "B"])[:2]

                q_type = mcq.get("question_type", "")
                if q_type not in valid_types:
                    q_type = "academic" if i < academic_count else "business_scenario"

                result.append({
                    "question_id": str(uuid.uuid4()),
                    "tag": tag,
                    "question_type": q_type,
                    "text": mcq.get("text", "题目生成失败"),
                    "options": mcq.get("options", {}),
                    "correct_options": mcq.get("correct_options"),
                    "explanation": mcq.get("explanation", "无解析"),
                })
            return result

        except json.JSONDecodeError as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"MCQ 批次 JSON 解析失败: {e}，触发降级补偿")
            return [
                {
                    "question_id": str(uuid.uuid4()),
                    "tag": tags[i % len(tags)],
                    "question_type": "academic" if i < academic_count else "business_scenario",
                    "text": f"（降级补偿题）关于 {tags[i % len(tags)]}，以下说法正确的是？",
                    "options": {"A": "正确描述A。", "B": "正确描述B。", "C": "错误描述C。", "D": "无关描述D。"},
                    "correct_options": ["A", "B"],
                    "explanation": f"LLM 生成失败: {str(e)}",
                }
                for i in range(count)
            ]
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"MCQ 批次生成异常: {e}")
            return []