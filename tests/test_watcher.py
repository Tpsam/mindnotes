import time
from mindnotes.watcher.monitor import wait_for_file_settled


def test_wait_for_file_settled(tmp_path):
    test_file = tmp_path / "test_memo.m4a"
    test_file.write_bytes(b"Dummy audio content for test")

    # Settle time set small for fast unit test
    ready = wait_for_file_settled(test_file, settle_seconds=0.2, max_wait=2.0)
    assert ready is True


def test_wait_for_missing_file(tmp_path):
    missing_file = tmp_path / "missing.m4a"
    ready = wait_for_file_settled(missing_file, settle_seconds=0.2, max_wait=0.5)
    assert ready is False
