"""Audio normalization using ffmpeg."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional
from mindnotes.config import BIN_DIR


class AudioNormalizationError(Exception):
    """Raised when audio conversion fails."""
    pass


def find_ffmpeg() -> Optional[Path]:
    """Find ffmpeg binary from system PATH or ~/Mindnotes/bin/."""
    # 1. System PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return Path(system_ffmpeg)

    # 2. Check standard Winget / Chocolatey / Scoop paths
    common_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
        Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
    ]
    for p in common_paths:
        if p.is_file():
            return p

    # 3. ~/Mindnotes/bin/ffmpeg.exe
    bin_ffmpeg = BIN_DIR / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if bin_ffmpeg.exists():
        return bin_ffmpeg

    # 4. Check for subdirectories under bin
    for match in BIN_DIR.glob("**/ffmpeg.exe" if os.name == "nt" else "**/ffmpeg"):
        if match.is_file():
            return match

    return None


def is_already_16k_mono_wav(file_path: Path) -> bool:
    """Check if file is already a 16kHz mono 16-bit PCM WAV."""
    if file_path.suffix.lower() != ".wav":
        return False
    try:
        with wave.open(str(file_path), "rb") as wf:
            return (
                wf.getnchannels() == 1
                and wf.getframerate() == 16000
                and wf.getsampwidth() == 2
            )
    except Exception:
        return False


def normalize_audio(
    input_path: Path | str,
    output_path: Optional[Path | str] = None,
    target_sr: int = 16000,
) -> Path:
    """
    Transcode an input audio file (.mp3, .m4a, .wav, etc.) to 16kHz mono 16-bit WAV PCM.
    """
    input_p = Path(input_path).resolve()
    if not input_p.exists():
        raise FileNotFoundError(f"Input audio file not found: {input_p}")

    # Optimization: If already 16kHz mono WAV, skip re-encoding!
    if is_already_16k_mono_wav(input_p):
        return input_p

    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        raise AudioNormalizationError(
            "ffmpeg binary not found on system PATH.\n"
            "Run 'winget install Gyan.FFmpeg' to install it on Windows."
        )

    if output_path is None:
        temp_dir = Path(tempfile.gettempdir()) / "mindnotes"
        temp_dir.mkdir(parents=True, exist_ok=True)
        dest_p = temp_dir / f"{input_p.stem}_16k.wav"
    else:
        dest_p = Path(output_path).resolve()
        dest_p.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(ffmpeg_bin),
        "-y",
        "-nostdin",
        "-i", str(input_p),
        "-ac", "1",
        "-ar", str(target_sr),
        "-acodec", "pcm_s16le",
        str(dest_p),
    ]

    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AudioNormalizationError(
                f"ffmpeg failed with exit code {result.returncode}:\n{result.stderr[-500:]}"
            )
    except FileNotFoundError:
        raise AudioNormalizationError(f"Could not execute ffmpeg at {ffmpeg_bin}")

    if not dest_p.exists() or dest_p.stat().st_size == 0:
        raise AudioNormalizationError(f"Normalization produced empty or missing file at {dest_p}")

    return dest_p


def get_audio_duration_seconds(input_path: Path | str) -> float:
    """Return estimated audio duration in seconds via wave or ffmpeg."""
    input_p = Path(input_path).resolve()
    if not input_p.exists():
        return 0.0

    if input_p.suffix.lower() == ".wav":
        try:
            with wave.open(str(input_p), "rb") as wf:
                return wf.getnframes() / float(wf.getframerate())
        except Exception:
            pass

    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        return 0.0

    cmd = [str(ffmpeg_bin), "-nostdin", "-i", str(input_p)]
    result = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    for line in result.stderr.splitlines():
        if "Duration:" in line:
            try:
                part = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = part.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                break
    return 0.0
