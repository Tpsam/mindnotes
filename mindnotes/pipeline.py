"""
Core Engine (pipeline.py)
─────────────────────────
UI-agnostic orchestrator:
Audio Normalization -> STT -> LLM Structuring -> Local Cache -> Notion Push -> Move to Processed
"""

from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from mindnotes.audio.normalizer import normalize_audio
from mindnotes.config import PROCESSED_DIR, load_config
from mindnotes.notion.client import NotionIntegrationError, NotionSyncClient
from mindnotes.storage.cache import (
    RunRecord,
    generate_run_id,
    save_run_cache,
    update_sync_status,
)
from mindnotes.stt.engine import TranscriptionEngine
from mindnotes.structuring.cleanup import clean_transcript
from mindnotes.structuring.notes import structure_quick_note


def move_to_processed(source_path: Path) -> Path:
    """
    Move source audio file to ~/Mindnotes/processed/ with collision protection.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = PROCESSED_DIR / source_path.name

    if dest_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = PROCESSED_DIR / f"{source_path.stem}_{timestamp}{source_path.suffix}"

    shutil.move(str(source_path), str(dest_path))
    return dest_path


def process_audio(
    file_path: str | Path,
    mode: str = "notes",
    model_profile: Optional[str] = None,
    project: Optional[str] = None,
    move_file: bool = True,
) -> Dict[str, Any]:
    """
    Process an audio recording end-to-end.

    Args:
        file_path: Path to raw audio file.
        mode: "notes" (default) or "content".
        model_profile: STT profile ("fast", "accurate", "parakeet"). Defaults to config.yaml.
        project: Project tag (e.g. "LIAS S2") for content mode.
        move_file: Whether to move source audio to ~/Mindnotes/processed/ when done.

    Returns:
        Summary dict of run results.
    """
    config = load_config()
    profile = model_profile or config.get("stt", {}).get("default_profile", "fast")
    source_p = Path(file_path).resolve()
    if not source_p.exists():
        raise FileNotFoundError(f"Source audio file not found: {source_p}")

    run_id = generate_run_id(prefix=source_p.stem[:12])
    print(f"\n[bold green]=== Processing: {source_p.name} (Mode: {mode.upper()}, Model: {profile}, ID: {run_id}) ===[/bold green]")

    # 1. Normalization (16kHz mono WAV)
    print("Normalizing audio via FFmpeg...")
    normalized_wav = normalize_audio(source_p)

    # 2. Transcription via sherpa-onnx
    print(f"Transcribing audio with '{profile}' profile...")
    engine = TranscriptionEngine(profile=profile)
    transcription = engine.transcribe_wav(normalized_wav)
    raw_transcript = transcription.text.strip()
    duration_sec = transcription.duration_seconds

    # 3. Clean up temporary WAV
    try:
        if normalized_wav.exists() and normalized_wav != source_p:
            normalized_wav.unlink()
    except Exception:
        pass

    # 4. Transcript cleanup
    cleaned = clean_transcript(raw_transcript)

    # Format verbatim transcript: if chunked, include timestamp markers
    if len(transcription.segments) > 1:
        verbatim_transcript = "\n\n".join(
            f"{s.format_timestamp()} {s.text}" for s in transcription.segments if s.text
        )
    else:
        verbatim_transcript = raw_transcript

    # 5. Mode Routing & Structuring
    print(f"Structuring output via LLM ({mode} mode)...")
    if mode == "notes":
        structured_note = structure_quick_note(
            cleaned_transcript=cleaned,
            verbatim_transcript=verbatim_transcript,
        )
        title = structured_note.title
        tags = structured_note.tags
        structured_data = {
            "title": structured_note.title,
            "body_markdown": structured_note.body_markdown,
            "tags": structured_note.tags,
        }
    else:
        # Fallback for Phase 1 content mode
        title = f"Content: {source_p.stem}"
        tags = [project or "Content"]
        structured_data = {
            "title": title,
            "body_markdown": cleaned,
            "tags": tags,
            "project": project or "Other",
        }

    # 6. Local-First Caching (Always saved BEFORE any network call)
    print("Writing local cache to ~/Mindnotes/output/...")
    record = RunRecord(
        id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        source_file=str(source_p),
        duration_seconds=duration_sec,
        title=title,
        tags=tags,
        structured_data=structured_data,
        verbatim_transcript=verbatim_transcript,
        synced=False,
    )
    json_cache_path = save_run_cache(record)
    print(f"Cached locally at: {json_cache_path.name}")

    # 7. Push to Notion
    notion_url = None
    notion_page_id = None
    sync_error = None
    try:
        print("Pushing structured output to Notion...")
        notion_client = NotionSyncClient()
        if mode == "notes":
            res = notion_client.push_quick_note(
                note=structured_note,
                source_audio=source_p.name,
            )
            notion_page_id = res["page_id"]
            notion_url = res["url"]
            update_sync_status(
                run_id=run_id,
                synced=True,
                notion_page_id=notion_page_id,
                notion_url=notion_url,
            )
            print(f"[bold green]Successfully pushed to Notion:[/bold green] {notion_url}")
    except Exception as e:
        sync_error = str(e)
        update_sync_status(run_id=run_id, synced=False, error=sync_error)
        print(f"[yellow]Notice: Notion sync pending ({e}). Run 'mindnotes retry-cached' to push later.[/yellow]")

    # 8. Move source file to processed/
    processed_file_path = None
    if move_file and source_p.exists():
        try:
            processed_file_path = move_to_processed(source_p)
            print(f"Moved source audio to: {processed_file_path.name}")
        except Exception as e:
            print(f"Warning: Failed to move source file to processed: {e}")

    return {
        "id": run_id,
        "title": title,
        "synced": notion_page_id is not None,
        "notion_url": notion_url,
        "error": sync_error,
        "cache_file": str(json_cache_path),
        "processed_file": str(processed_file_path) if processed_file_path else None,
    }
