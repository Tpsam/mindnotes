"""Configuration and path management for Mindnotes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

# Base user directory: ~/Mindnotes (or override via MINDNOTES_HOME)
MINDNOTES_DIR = Path(os.getenv("MINDNOTES_HOME", Path.home() / "Mindnotes")).resolve()

# Operational directories
INBOX_DIR = MINDNOTES_DIR / "inbox"
INBOX_NOTES_DIR = INBOX_DIR / "notes"
INBOX_CONTENT_DIR = INBOX_DIR / "content"
PROCESSED_DIR = MINDNOTES_DIR / "processed"
OUTPUT_DIR = MINDNOTES_DIR / "output"
MODELS_DIR = MINDNOTES_DIR / "models"
BIN_DIR = MINDNOTES_DIR / "bin"
CONFIG_FILE = MINDNOTES_DIR / "config.yaml"
ENV_FILE = MINDNOTES_DIR / ".env"


def _load_env_file(dotenv_path: Optional[Path | str] = None) -> bool:
    """Load environment variables from a .env file into os.environ."""
    p = Path(dotenv_path) if dotenv_path else ENV_FILE
    if not p.is_file():
        p = Path(".env")
    if p.is_file():
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        # Strip whitespace and quotes
                        clean_k = k.strip()
                        clean_v = v.strip().strip("'\"")
                        if clean_k:
                            os.environ[clean_k] = clean_v
            return True
        except Exception:
            return False
    return False


try:
    from dotenv import load_dotenv as _vendor_load_dotenv
    def load_dotenv(path: Optional[Path | str] = None) -> bool:
        p = Path(path) if path else ENV_FILE
        if p.is_file():
            _vendor_load_dotenv(p, override=True)
            # Also run our line stripper to clean up any leading spaces after =
            _load_env_file(p)
            return True
        return _load_env_file(path)
except ImportError:
    load_dotenv = _load_env_file

# Auto-load environment on module import
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv()

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_CONFIG: Dict[str, Any] = {
    "llm": {
        "provider": None,
        "model": None,
        "timeout_seconds": 60.0,
    },
    "stt": {
        "default_profile": "fast",
        "profiles": {
            "fast": {
                "type": "whisper",
                "name": "sherpa-onnx-whisper-small.en",
                "encoder": "small.en-encoder.int8.onnx",
                "decoder": "small.en-decoder.int8.onnx",
                "tokens": "small.en-tokens.txt",
                "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-small.en.tar.bz2",
            },
            "accurate": {
                "type": "whisper",
                "name": "sherpa-onnx-whisper-medium.en",
                "encoder": "medium.en-encoder.int8.onnx",
                "decoder": "medium.en-decoder.int8.onnx",
                "tokens": "medium.en-tokens.txt",
                "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-medium.en.tar.bz2",
            },
            "parakeet": {
                "type": "nemo_ctc",
                "name": "sherpa-onnx-nemo-fast-conformer-ctc-en-24500",
                "model": "model.onnx",
                "tokens": "tokens.txt",
                "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-fast-conformer-ctc-en-24500.tar.bz2",
            },
        },
    },
    "diarization": {
        "default_speakers": 2,
        "threshold": 0.6,
    },
    "content": {
        "default_project": "Other",
        "projects": ["LIAS S2", "Throughline", "Other"],
    },
    "notion": {
        "notes_db_id": None,
        "content_db_id": None,
    },
}


def ensure_directories() -> None:
    """Create all operational directories if they do not exist."""
    for directory in [
        MINDNOTES_DIR,
        INBOX_DIR,
        INBOX_NOTES_DIR,
        INBOX_CONTENT_DIR,
        PROCESSED_DIR,
        OUTPUT_DIR,
        MODELS_DIR,
        BIN_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def init_config_file() -> None:
    """Write default config.yaml if missing."""
    ensure_directories()
    if not CONFIG_FILE.exists() and yaml is not None:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)


def load_config() -> Dict[str, Any]:
    """Load configuration from config.yaml merged with defaults and environment."""
    ensure_directories()
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        load_dotenv()

    config = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists() and yaml is not None:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
                for key, val in user_config.items():
                    if isinstance(val, dict) and isinstance(config.get(key), dict):
                        config[key].update(val)
                    else:
                        config[key] = val
        except Exception:
            pass

    if os.getenv("NOTION_NOTES_DB_ID"):
        config["notion"]["notes_db_id"] = os.getenv("NOTION_NOTES_DB_ID")
    if os.getenv("NOTION_CONTENT_DB_ID"):
        config["notion"]["content_db_id"] = os.getenv("NOTION_CONTENT_DB_ID")

    return config
