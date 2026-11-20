from pathlib import Path
from mindnotes.config import (
    load_config,
    ensure_directories,
    MINDNOTES_DIR,
    INBOX_NOTES_DIR,
    INBOX_CONTENT_DIR,
    OUTPUT_DIR,
    MODELS_DIR,
)


def test_ensure_directories(tmp_path, monkeypatch):
    monkeypatch.setenv("MINDNOTES_HOME", str(tmp_path / "Mindnotes"))
    from mindnotes import config

    config.MINDNOTES_DIR = tmp_path / "Mindnotes"
    config.INBOX_DIR = config.MINDNOTES_DIR / "inbox"
    config.INBOX_NOTES_DIR = config.INBOX_DIR / "notes"
    config.INBOX_CONTENT_DIR = config.INBOX_DIR / "content"
    config.PROCESSED_DIR = config.MINDNOTES_DIR / "processed"
    config.OUTPUT_DIR = config.MINDNOTES_DIR / "output"
    config.MODELS_DIR = config.MINDNOTES_DIR / "models"
    config.BIN_DIR = config.MINDNOTES_DIR / "bin"
    config.CONFIG_FILE = config.MINDNOTES_DIR / "config.yaml"

    config.ensure_directories()

    assert config.INBOX_NOTES_DIR.exists()
    assert config.INBOX_CONTENT_DIR.exists()
    assert config.OUTPUT_DIR.exists()
    assert config.MODELS_DIR.exists()
    assert config.BIN_DIR.exists()


def test_default_config():
    cfg = load_config()
    assert "llm" in cfg
    assert "stt" in cfg
    assert "fast" in cfg["stt"]["profiles"]
    assert "accurate" in cfg["stt"]["profiles"]
    assert cfg["diarization"]["default_speakers"] == 2
