"""Watcher and autostart module."""

from mindnotes.watcher.monitor import start_watcher, wait_for_file_settled
from mindnotes.watcher.autostart import (
    enable_autostart,
    disable_autostart,
    is_autostart_enabled,
)

__all__ = [
    "start_watcher",
    "wait_for_file_settled",
    "enable_autostart",
    "disable_autostart",
    "is_autostart_enabled",
]
