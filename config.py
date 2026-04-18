from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    )
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))
    local_bank_path: str = field(
        default_factory=lambda: os.getenv("LOCAL_BANK_PATH", "./local_bank")
    )
    data_path: str = field(default_factory=lambda: os.getenv("DATA_PATH", "./data"))
    output_path: str = field(
        default_factory=lambda: os.getenv("OUTPUT_PATH", "./output")
    )


settings = Settings()
