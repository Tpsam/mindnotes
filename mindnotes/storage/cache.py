"""Local-first caching and sync status tracking."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from mindnotes.config import OUTPUT_DIR


@dataclass
class RunRecord:
    """Complete record of a transcription & structuring run."""
    id: str
    timestamp: str
    mode: str
    source_file: str
    duration_seconds: float
    title: str
    tags: List[str]
    structured_data: Dict[str, Any]
    verbatim_transcript: str
    synced: bool = False
    notion_page_id: Optional[str] = None
    notion_url: Optional[str] = None
    sync_error: Optional[str] = None
    last_sync_attempt: Optional[str] = None


def generate_run_id(prefix: str = "run") -> str:
    """Generate a sortable timestamped run ID."""
    now = datetime.now()
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{prefix}"


def save_run_cache(record: RunRecord) -> Path:
    """
    Save structured output to ~/Mindnotes/output/<id>.json and <id>.md.
    Returns path to the JSON file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / f"{record.id}.json"
    md_path = OUTPUT_DIR / f"{record.id}.md"

    # Save JSON metadata and structured data
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(asdict(record), f, indent=2, ensure_ascii=False)

    # Save human-readable Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        body = record.structured_data.get("body_markdown", "")
        f.write(f"# {record.title}\n\n")
        if record.tags:
            f.write(f"**Tags:** {' '.join([f'`#{t}`' for t in record.tags])}\n\n")
        f.write(f"{body}\n\n")
        f.write("---\n")
        f.write("<details>\n<summary><b>Full Transcript</b></summary>\n\n")
        f.write(f"{record.verbatim_transcript}\n\n")
        f.write("</details>\n")

    return json_path


def update_sync_status(
    run_id: str,
    synced: bool,
    notion_page_id: Optional[str] = None,
    notion_url: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Update Notion synchronization status in the local JSON cache."""
    json_path = OUTPUT_DIR / f"{run_id}.json"
    if not json_path.exists():
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["synced"] = synced
        data["notion_page_id"] = notion_page_id
        data["notion_url"] = notion_url
        data["sync_error"] = error
        data["last_sync_attempt"] = datetime.now(timezone.utc).isoformat()

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to update cache sync status for {run_id}: {e}")


def load_run_cache(run_id_or_path: str | Path) -> Optional[RunRecord]:
    """Load a RunRecord from run_id or direct JSON path."""
    p = Path(run_id_or_path)
    if not p.is_file():
        p = OUTPUT_DIR / f"{run_id_or_path}.json"

    if not p.exists():
        return None

    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
            return RunRecord(**d)
    except Exception:
        return None


def get_unsynced_runs() -> List[RunRecord]:
    """Find all runs in ~/Mindnotes/output/ where synced == False."""
    unsynced = []
    if not OUTPUT_DIR.exists():
        return unsynced

    for json_file in sorted(OUTPUT_DIR.glob("*.json")):
        rec = load_run_cache(json_file)
        if rec and not rec.synced:
            unsynced.append(rec)

    return unsynced
