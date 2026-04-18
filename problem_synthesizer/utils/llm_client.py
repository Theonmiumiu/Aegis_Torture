import time
import random
import logging
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM 客户端封装，支持所有 OpenAI-compatible 接口。
    内置带 Jitter 的指数退避重试机制。
    """

    def __init__(self, api_key: str, base_url: str, model: str, max_retries: int = 3):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_retries = max_retries

    def generate_text(self, prompt: str, temperature: float = 0.5) -> str:
        """发送 Prompt 并获取文本回复，包含指数退避重试逻辑。"""
        retries = 0
        base_delay = 2.0

        while retries <= self.max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=2048,
                )
                return response.choices[0].message.content

            except Exception as e:
                retries += 1
                if retries > self.max_retries:
                    logger.error(
                        f"LLM API 达到最大重试次数 ({self.max_retries})，任务最终失败。Error: {e}"
                    )
                    raise RuntimeError(f"LLM 接口多次调用失败: {str(e)}") from e

                delay = base_delay * (2 ** (retries - 1)) + random.uniform(0, 1.0)
                logger.warning(
                    f"LLM API 调用异常: {e}。等待 {delay:.2f}s 后进行第 {retries} 次重试..."
                )
                time.sleep(delay)
