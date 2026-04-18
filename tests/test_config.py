import os

def test_settings_has_default_values(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LOCAL_BANK_PATH", raising=False)
    monkeypatch.delenv("DATA_PATH", raising=False)
    monkeypatch.delenv("OUTPUT_PATH", raising=False)

    import importlib
    import config as cfg
    importlib.reload(cfg)

    assert cfg.settings.base_url == "https://api.openai.com/v1"
    assert cfg.settings.model == "gpt-4o"
    assert cfg.settings.data_path == "./data"
    assert cfg.settings.output_path == "./output"
    assert cfg.settings.local_bank_path == "./local_bank"

def test_settings_reads_from_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")

    import importlib
    import config as cfg
    importlib.reload(cfg)

    assert cfg.settings.api_key == "sk-test-key"
    assert cfg.settings.base_url == "https://api.deepseek.com/v1"
    assert cfg.settings.model == "deepseek-chat"
