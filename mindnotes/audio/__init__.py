"""Audio normalization and processing module."""

from mindnotes.audio.normalizer import (
    normalize_audio,
    find_ffmpeg,
    get_audio_duration_seconds,
    AudioNormalizationError,
)

__all__ = [
    "normalize_audio",
    "find_ffmpeg",
    "get_audio_duration_seconds",
    "AudioNormalizationError",
]
