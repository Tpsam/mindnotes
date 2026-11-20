"""
Mindnotes CLI Entrypoint
────────────────────────
Command-line interface with dual Typer / Argparse support.
Runs out-of-the-box with standard library argparse if Typer is not installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from mindnotes import __version__
from mindnotes.config import (
    INBOX_CONTENT_DIR,
    INBOX_NOTES_DIR,
    MINDNOTES_DIR,
    OUTPUT_DIR,
    ensure_directories,
    init_config_file,
)
from mindnotes.pipeline import process_audio
from mindnotes.storage.cache import get_unsynced_runs, update_sync_status
from mindnotes.stt.models import (
    install_ffmpeg_if_missing,
    install_model,
    is_model_installed,
)
from mindnotes.watcher.autostart import (
    disable_autostart,
    enable_autostart,
    is_autostart_enabled,
)
from mindnotes.watcher.monitor import start_watcher

# Try importing rich for colored output
try:
    from rich import print as rprint
    from rich.console import Console
    from rich.table import Table
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None

    def rprint(*args, **kwargs):
        # Strip simple rich tags if printing to plain console
        import re
        clean_args = []
        for a in args:
            if isinstance(a, str):
                clean_args.append(re.sub(r"\[/?\w+.*?\]", "", a))
            else:
                clean_args.append(a)
        print(*clean_args, **kwargs)


def run_setup(profile: str = "fast", force: bool = False):
    """Execute setup command."""
    rprint("[bold cyan]=== Mindnotes Setup ===[/bold cyan]")
    rprint(f"Ensuring user directories at: {MINDNOTES_DIR}")
    ensure_directories()
    init_config_file()

    # 1. Provision FFmpeg
    rprint("\n[bold]1. Checking Audio Decoder (FFmpeg)...[/bold]")
    ffmpeg_path = install_ffmpeg_if_missing(force=force)
    if ffmpeg_path:
        rprint(f"  [green]✓[/green] FFmpeg ready at: {ffmpeg_path}")
    else:
        rprint("  [yellow]![/yellow] FFmpeg not found. Run 'winget install Gyan.FFmpeg' or install manually.")

    # 2. Provision STT Model
    rprint(f"\n[bold]2. Checking STT Model Profile ('{profile}')...[/bold]")
    if is_model_installed(profile) and not force:
        rprint(f"  [green]✓[/green] Model profile '{profile}' is already installed.")
    else:
        rprint(f"  Downloading quantized ONNX Whisper model for '{profile}'...")
        try:
            model_dir = install_model(profile=profile, force=force)
            rprint(f"  [green]✓[/green] Model ready at: {model_dir}")
        except Exception as e:
            rprint(f"  [red]✗[/red] Failed to download model: {e}")

    rprint("\n[bold green]Setup completed successfully![/bold green]")
    rprint(f"• Drop notes into:   {INBOX_NOTES_DIR}")
    rprint(f"• Drop content into: {INBOX_CONTENT_DIR}")
    rprint(f"• Outputs saved to:  {OUTPUT_DIR}\n")


def run_process(
    file_path: Path,
    mode: str = "notes",
    profile: Optional[str] = None,
    project: Optional[str] = None,
    no_move: bool = False,
):
    """Execute run command."""
    if not file_path.exists():
        rprint(f"[red]Error: Audio file not found at {file_path}[/red]")
        sys.exit(1)

    try:
        res = process_audio(
            file_path=file_path,
            mode=mode,
            model_profile=profile,
            project=project,
            move_file=not no_move,
        )
        rprint("\n[bold green]Pipeline Run Completed![/bold green]")
        rprint(f"• ID:      {res['id']}")
        rprint(f"• Title:   {res['title']}")
        rprint(f"• Synced:  {'Yes' if res['synced'] else 'Pending (saved locally)'}")
        if res.get("notion_url"):
            rprint(f"• Notion:  {res['notion_url']}")
        rprint(f"• Cache:   {res['cache_file']}")
    except Exception as e:
        rprint(f"\n[bold red]Pipeline failed:[/bold red] {e}")
        sys.exit(1)


def run_watch():
    """Execute watch command."""
    start_watcher(foreground=True)


def run_autostart(action: str):
    """Execute autostart command."""
    act = action.lower()
    if act == "enable":
        try:
            vbs_p = enable_autostart()
            rprint(f"[bold green]Autostart enabled![/bold green] Silent launcher registered at:\n{vbs_p}")
        except Exception as e:
            rprint(f"[bold red]Failed to enable autostart:[/bold red] {e}")
    elif act == "disable":
        if disable_autostart():
            rprint("[bold yellow]Autostart disabled.[/bold yellow] Removed startup launcher.")
        else:
            rprint("Autostart was not enabled.")
    elif act == "status":
        enabled = is_autostart_enabled()
        status_text = "[bold green]ENABLED[/bold green]" if enabled else "[yellow]DISABLED[/yellow]"
        rprint(f"Mindnotes Windows background autostart: {status_text}")
    else:
        rprint(f"[red]Unknown action '{action}'. Use 'enable', 'disable', or 'status'.[/red]")


def run_notion_test():
    """Execute notion test command."""
    from mindnotes.notion.client import NotionSyncClient

    rprint("[bold cyan]=== Testing Notion Connection & Schemas ===[/bold cyan]")
    try:
        client = NotionSyncClient()
        res = client.test_connection()

        if HAS_RICH and console:
            table = Table(title="Notion Integration Diagnostics", show_lines=True)
            table.add_column("Component", style="bold")
            table.add_column("Status")
            table.add_column("Details")

            if res.get("authenticated"):
                table.add_row("Authentication", "[green]Success[/green]", f"Connected as: {res.get('bot_user')}")
            else:
                table.add_row("Authentication", "[red]Failed[/red]", res.get("error", "Unknown auth error"))

            notes = res.get("notes_db", {})
            if notes.get("valid"):
                props = ", ".join(notes.get("properties", []))
                table.add_row("Notes DB", "[green]Accessible[/green]", f"Title: {notes.get('title')}\nProps: {props}")
            else:
                table.add_row("Notes DB", "[yellow]Warning/Missing[/yellow]", str(notes.get("error")))

            content = res.get("content_db", {})
            if content.get("valid"):
                props = ", ".join(content.get("properties", []))
                table.add_row("Content DB", "[green]Accessible[/green]", f"Title: {content.get('title')}\nProps: {props}")
            else:
                table.add_row("Content DB", "[yellow]Warning/Missing[/yellow]", str(content.get("error")))

            console.print(table)
        else:
            rprint(f"• Auth: {'OK' if res.get('authenticated') else 'FAILED: ' + str(res.get('error'))}")
            rprint(f"• Notes DB: {res.get('notes_db')}")
            rprint(f"• Content DB: {res.get('content_db')}")
    except Exception as e:
        rprint(f"[bold red]Connection test failed:[/bold red] {e}")


def run_retry_cached():
    """Execute retry-cached command."""
    from mindnotes.notion.client import NotionSyncClient
    from mindnotes.structuring.notes import StructuredNote

    rprint("[bold cyan]=== Retrying Unsynced Notion Entries ===[/bold cyan]")
    unsynced = get_unsynced_runs()
    if not unsynced:
        rprint("[green]All cached runs are already synced to Notion![/green]")
        return

    rprint(f"Found {len(unsynced)} unsynced run(s). Connecting to Notion...")
    try:
        client = NotionSyncClient()
    except Exception as e:
        rprint(f"[bold red]Cannot connect to Notion:[/bold red] {e}")
        sys.exit(1)

    succeeded = 0
    for record in unsynced:
        rprint(f"Retrying run {record.id} ({record.title})...")
        try:
            note = StructuredNote(
                title=record.title,
                body_markdown=record.structured_data.get("body_markdown", ""),
                tags=record.tags,
                verbatim_transcript=record.verbatim_transcript,
            )
            res = client.push_quick_note(
                note=note,
                source_audio=Path(record.source_file).name,
            )
            update_sync_status(
                run_id=record.id,
                synced=True,
                notion_page_id=res["page_id"],
                notion_url=res["url"],
            )
            rprint(f"  [green]✓ Synced:[/green] {res['url']}")
            succeeded += 1
        except Exception as e:
            rprint(f"  [red]✗ Failed:[/red] {e}")
            update_sync_status(run_id=record.id, synced=False, error=str(e))

    rprint(f"\nCompleted: {succeeded}/{len(unsynced)} synced successfully.")


# Dual CLI Dispatcher: Typer if available, argparse fallback
try:
    import typer

    app = typer.Typer(
        name="mindnotes",
        help="Mindnotes: Local speech-to-knowledge pipeline with sherpa-onnx and Notion sync.",
        add_completion=False,
    )
    notion_subapp = typer.Typer(help="Notion database integration and verification.")
    app.add_typer(notion_subapp, name="notion")

    @app.callback()
    def typer_callback(version: Optional[bool] = typer.Option(None, "--version", "-v")):
        if version:
            rprint(f"[bold cyan]Mindnotes[/bold cyan] v{__version__}")
            raise typer.Exit()

    @app.command(name="setup")
    def typer_setup(
        profile: str = typer.Option("fast", "--profile", "-p"),
        force: bool = typer.Option(False, "--force", "-f"),
    ):
        run_setup(profile=profile, force=force)

    @app.command(name="run")
    def typer_run(
        file_path: Path = typer.Argument(...),
        mode: str = typer.Option("notes", "--mode", "-m"),
        profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Model profile ('fast', 'accurate', 'parakeet'). Defaults to config.yaml"),
        project: Optional[str] = typer.Option(None, "--project"),
        no_move: bool = typer.Option(False, "--no-move"),
    ):
        run_process(file_path=file_path, mode=mode, profile=profile, project=project, no_move=no_move)

    @app.command(name="watch")
    def typer_watch():
        run_watch()

    @app.command(name="autostart")
    def typer_autostart(action: str = typer.Argument("status")):
        run_autostart(action=action)

    @notion_subapp.command(name="test")
    def typer_notion_test():
        run_notion_test()

    @app.command(name="retry-cached")
    def typer_retry_cached():
        run_retry_cached()

    def main():
        app()

except ImportError:
    # Argparse standard library fallback
    def main():
        parser = argparse.ArgumentParser(
            prog="mindnotes",
            description="Mindnotes: Local speech-to-knowledge pipeline with sherpa-onnx and Notion sync.",
        )
        parser.add_argument("-v", "--version", action="version", version=f"Mindnotes v{__version__}")
        subparsers = parser.add_subparsers(dest="command")

        # setup
        setup_p = subparsers.add_parser("setup", help="Bootstrap directories and download models")
        setup_p.add_argument("-p", "--profile", default="fast", help="Model profile (fast/accurate)")
        setup_p.add_argument("-f", "--force", action="store_true", help="Force re-download")

        # run
        run_p = subparsers.add_parser("run", help="Process an audio file")
        run_p.add_argument("file_path", type=Path, help="Audio file path")
        run_p.add_argument("-m", "--mode", default="notes", help="Mode: notes or content")
        run_p.add_argument("-p", "--profile", default=None, help="Profile ('fast', 'accurate', 'parakeet'). Defaults to config.yaml")
        run_p.add_argument("--project", default=None, help="Project name")
        run_p.add_argument("--no-move", action="store_true", help="Do not move source file to processed/")

        # watch
        subparsers.add_parser("watch", help="Start foreground folder watcher")

        # autostart
        auto_p = subparsers.add_parser("autostart", help="Manage Windows login background autostart")
        auto_p.add_argument("action", nargs="?", default="status", choices=["enable", "disable", "status"])

        # notion
        notion_p = subparsers.add_parser("notion", help="Notion commands")
        notion_sub = notion_p.add_subparsers(dest="notion_command")
        notion_sub.add_parser("test", help="Test Notion connection and DB schemas")

        # retry-cached
        subparsers.add_parser("retry-cached", help="Retry pushing unsynced runs to Notion")

        args = parser.parse_args()
        if args.command == "setup":
            run_setup(profile=args.profile, force=args.force)
        elif args.command == "run":
            run_process(
                file_path=args.file_path,
                mode=args.mode,
                profile=args.profile,
                project=args.project,
                no_move=args.no_move,
            )
        elif args.command == "watch":
            run_watch()
        elif args.command == "autostart":
            run_autostart(args.action)
        elif args.command == "notion":
            if getattr(args, "notion_command", None) == "test":
                run_notion_test()
            else:
                notion_p.print_help()
        elif args.command == "retry-cached":
            run_retry_cached()
        else:
            parser.print_help()

    app = main


if __name__ == "__main__":
    main()
