# src/exceptions.py

class MarkdownFormatError(Exception):
    """
    当用户破坏了 Markdown 的固定格式时抛出。
    常用于拦截并触发 UI 提示，引导用户恢复占位符格式。
    """
    pass

class LLMUnavailableError(Exception):
    """
    当 LLM 宕机、超时或无响应时抛出。
    常用于触发系统的死信队列（Dead Letter Queue），保留用户代码并延后重试批改。
    """
    pass