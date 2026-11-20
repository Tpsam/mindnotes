import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from mindnotes.cli import main, run_autostart, run_retry_cached
from mindnotes.storage.cache import RunRecord, save_run_cache


def test_cli_retry_cached(tmp_path, monkeypatch):
    monkeypatch.setattr("mindnotes.storage.cache.OUTPUT_DIR", tmp_path)

    # Create an unsynced record
    rec = RunRecord(
        id="test_run_retry",
        timestamp="2026-11-20T12:00:00Z",
        mode="notes",
        source_file="memo.m4a",
        duration_seconds=12.0,
        title="Retry Title",
        tags=["Retry"],
        structured_data={"body_markdown": "Body text to sync"},
        verbatim_transcript="Spoken words.",
        synced=False,
    )
    save_run_cache(rec)

    # Mock NotionSyncClient
    with patch("mindnotes.notion.client.NotionSyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.push_quick_note.return_value = {
            "page_id": "notion_123",
            "url": "https://notion.so/notion_123",
        }
        mock_client_cls.return_value = mock_client

        # Run retry-cached
        run_retry_cached()

        assert mock_client.push_quick_note.called
        # Check that cache was updated to synced
        from mindnotes.storage.cache import load_run_cache
        updated = load_run_cache(tmp_path / "test_run_retry.json")
        assert updated.synced is True
        assert updated.notion_page_id == "notion_123"
