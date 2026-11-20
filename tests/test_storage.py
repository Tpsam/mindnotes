from pathlib import Path
from mindnotes.storage.cache import (
    RunRecord,
    save_run_cache,
    load_run_cache,
    update_sync_status,
    get_unsynced_runs,
)


def test_save_and_update_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("mindnotes.storage.cache.OUTPUT_DIR", tmp_path)

    record = RunRecord(
        id="test_run_001",
        timestamp="2026-11-20T12:00:00Z",
        mode="notes",
        source_file="memo.m4a",
        duration_seconds=45.2,
        title="Test Title",
        tags=["Test"],
        structured_data={"body_markdown": "Test body content"},
        verbatim_transcript="Verbatim audio text here.",
        synced=False,
    )

    json_path = save_run_cache(record)
    assert json_path.exists()
    assert (tmp_path / "test_run_001.md").exists()

    # Verify unsynced runs
    unsynced = get_unsynced_runs()
    assert len(unsynced) == 1
    assert unsynced[0].id == "test_run_001"

    # Update sync status
    update_sync_status(
        run_id="test_run_001",
        synced=True,
        notion_page_id="page_12345",
        notion_url="https://notion.so/page_12345",
    )

    updated = load_run_cache(json_path)
    assert updated.synced is True
    assert updated.notion_page_id == "page_12345"
    assert updated.notion_url == "https://notion.so/page_12345"

    # Should no longer be in unsynced
    assert len(get_unsynced_runs()) == 0
