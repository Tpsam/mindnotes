"""STT Engine and model management."""

from mindnotes.stt.engine import (
    TranscriptionEngine,
    TranscriptResult,
    TranscriptSegment,
)
from mindnotes.stt.models import (
    install_model,
    is_model_installed,
    install_ffmpeg_if_missing,
    get_model_dir,
)

__all__ = [
    "TranscriptionEngine",
    "TranscriptResult",
    "TranscriptSegment",
    "install_model",
    "is_model_installed",
    "install_ffmpeg_if_missing",
    "get_model_dir",
]
