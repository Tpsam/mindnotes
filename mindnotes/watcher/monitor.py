"""
Watched Folders Monitor with File-Settling and Lock Verification
────────────────────────────────────────────────────────────────
Monitors ~/Mindnotes/inbox/notes and ~/Mindnotes/inbox/content.
Guarantees file write completion before triggering pipeline.py.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional, Set

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    FileSystemEvent = object
    FileSystemEventHandler = object
    Observer = None

from mindnotes.config import (
    INBOX_CONTENT_DIR,
    INBOX_DIR,
    INBOX_NOTES_DIR,
    load_config,
)
from mindnotes.pipeline import process_audio

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".wma", ".mp4", ".m4r"}


def wait_for_file_settled(file_path: Path, settle_seconds: float = 2.0, max_wait: float = 60.0) -> bool:
    """
    Wait until file size is stable for at least `settle_seconds` and can be exclusively opened.
    Returns True if file is ready, False if timed out or inaccessible.
    """
    start_time = time.monotonic()
    last_size = -1
    stable_since = None

    while (time.monotonic() - start_time) < max_wait:
        if not file_path.exists():
            return False

        try:
            current_size = file_path.stat().st_size
        except OSError:
            time.sleep(0.5)
            continue

        if current_size == 0:
            time.sleep(0.5)
            continue

        now = time.monotonic()
        if current_size == last_size:
            if stable_since is None:
                stable_since = now
            elif (now - stable_since) >= settle_seconds:
                try:
                    with open(file_path, "rb") as f:
                        f.read(1024)
                    return True
                except (PermissionError, OSError):
                    pass
        else:
            last_size = current_size
            stable_since = None

        time.sleep(0.5)

    return False


if HAS_WATCHDOG:
    class AudioDropHandler(FileSystemEventHandler):
        """Handles audio file drops into watched folders."""

        def __init__(self):
            super().__init__()
            self.config = load_config()
            self._processing: Set[Path] = set()

        def on_created(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._handle_file(Path(event.src_path))

        def on_moved(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._handle_file(Path(event.dest_path))

        def process_existing_files(self) -> None:
            """Scan and process files already in inbox on watcher startup."""
            if not INBOX_DIR.exists():
                return
            for p in sorted(INBOX_DIR.glob("**/*")):
                if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and not p.name.startswith("."):
                    self._handle_file(p)

        def _handle_file(self, file_path: Path) -> None:
            p = file_path.resolve()

            if p.name.startswith(".") or p.name.startswith("~") or p.suffix.lower() not in AUDIO_EXTENSIONS:
                return

            if p in self._processing or not p.exists():
                return

            self._processing.add(p)
            try:
                print(f"\n[bold blue]New audio detected:[/bold blue] {p.name}")
                print(f"Waiting for file write to complete (settling lock check)...")

                if not wait_for_file_settled(p, settle_seconds=2.0):
                    print(f"[yellow]Skipping {p.name}: File did not stabilize or remained locked.[/yellow]")
                    return

                mode = "notes"
                project = None

                if INBOX_CONTENT_DIR.resolve() in p.parents:
                    mode = "content"
                    rel_parts = p.relative_to(INBOX_CONTENT_DIR.resolve()).parts
                    if len(rel_parts) > 1:
                        project = rel_parts[0]
                    else:
                        project = self.config.get("content", {}).get("default_project", "Other")
                else:
                    mode = "notes"

                process_audio(
                    file_path=p,
                    mode=mode,
                    project=project,
                    move_file=True,
                )
            finally:
                self._processing.discard(p)
else:
    class AudioDropHandler:
        def process_existing_files(self):
            pass


def start_watcher(foreground: bool = True) -> Optional[Observer]:
    """Start watchdog observer monitoring inbox directories."""
    if not HAS_WATCHDOG:
        raise RuntimeError("watchdog is not installed. Run 'pip install watchdog' to enable folder watching.")

    INBOX_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    handler = AudioDropHandler()
    observer = Observer()
    observer.schedule(handler, str(INBOX_DIR), recursive=True)
    observer.start()

    print("[bold green]Mindnotes folder watcher is active![/bold green]")
    print(f"• Notes inbox:   {INBOX_NOTES_DIR}")
    print(f"• Content inbox: {INBOX_CONTENT_DIR}")
    print("Drop audio files (.mp3, .m4a, .wav, .mp4) into either folder to process automatically.\n")

    # Check for files already present when watcher starts
    handler.process_existing_files()

    if foreground:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping folder watcher...")
            observer.stop()
        observer.join()

    return observer
