"""Model and binary management for sherpa-onnx and ffmpeg."""

from __future__ import annotations

import os
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from mindnotes.config import BIN_DIR, MODELS_DIR, load_config

FFMPEG_WINDOWS_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"


def download_with_progress(
    url: str,
    dest_path: Path,
    description: str = "Downloading",
) -> Path:
    """Download a file with progress reporting."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    if HAS_REQUESTS:
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))

            if HAS_RICH and total_size > 0:
                progress = Progress(
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                )
                with progress:
                    task = progress.add_task(description, total=total_size)
                    with open(temp_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                                progress.update(task, advance=len(chunk))
            else:
                print(f"{description}... ({total_size // (1024*1024) if total_size else '?'} MB)")
                downloaded = 0
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
    else:
        print(f"{description} (via urllib)...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mindnotes/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(temp_path, "wb") as f:
            shutil.copyfileobj(resp, f)

    if temp_path.exists():
        if dest_path.exists():
            dest_path.unlink()
        temp_path.rename(dest_path)

    return dest_path


def get_model_dir(profile: str = "fast") -> Path:
    """Return directory for a model profile."""
    config = load_config()
    profile_data = config.get("stt", {}).get("profiles", {}).get(profile, {})
    model_name = profile_data.get("name", f"sherpa-onnx-{profile}")
    return MODELS_DIR / model_name


def is_model_installed(profile: str = "fast") -> bool:
    """Check if all required model files for a profile exist."""
    config = load_config()
    profile_data = config.get("stt", {}).get("profiles", {}).get(profile, {})
    if not profile_data:
        return False

    model_dir = get_model_dir(profile)
    if not model_dir.is_dir():
        return False

    model_type = profile_data.get("type", "whisper")
    tokens_file = model_dir / profile_data.get("tokens", "tokens.txt")

    if model_type == "whisper":
        encoder_file = model_dir / profile_data.get("encoder", "")
        decoder_file = model_dir / profile_data.get("decoder", "")
        return encoder_file.is_file() and decoder_file.is_file() and tokens_file.is_file()
    elif model_type == "nemo_ctc":
        # Check for model.int8.onnx or model.onnx
        model_file = model_dir / profile_data.get("model", "model.int8.onnx")
        if not model_file.is_file():
            # Check for any .onnx file
            onnx_files = list(model_dir.glob("*.onnx"))
            if not onnx_files:
                return False
        return tokens_file.is_file()

    return False


def install_model(profile: str = "fast", force: bool = False) -> Path:
    """Download and extract an ONNX model profile."""
    config = load_config()
    profile_data = config.get("stt", {}).get("profiles", {}).get(profile)
    if not profile_data:
        raise ValueError(f"Unknown STT profile: '{profile}'. Available: {list(config.get('stt', {}).get('profiles', {}).keys())}")

    model_dir = get_model_dir(profile)
    if is_model_installed(profile) and not force:
        return model_dir

    archive_url = profile_data.get("url")
    if not archive_url:
        raise ValueError(f"No download URL configured for profile '{profile}'")

    archive_name = archive_url.split("/")[-1]
    archive_path = MODELS_DIR / archive_name

    download_with_progress(archive_url, archive_path, description=f"Fetching {profile_data.get('name')}")

    print(f"Extracting {archive_name} into {MODELS_DIR}...")
    if archive_name.endswith(".tar.bz2") or archive_name.endswith(".tar.gz"):
        with tarfile.open(archive_path, "r:*") as tar:
            tar.extractall(path=MODELS_DIR)
    elif archive_name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(path=MODELS_DIR)

    if archive_path.exists():
        archive_path.unlink()

    if not is_model_installed(profile):
        raise RuntimeError(f"Model installation failed: expected files not found in {model_dir}")

    return model_dir


def install_ffmpeg_if_missing(force: bool = False) -> Optional[Path]:
    """Auto-provision FFmpeg into ~/Mindnotes/bin/ on Windows if missing."""
    from mindnotes.audio.normalizer import find_ffmpeg

    existing = find_ffmpeg()
    if existing and not force:
        return existing

    if os.name != "nt":
        print("Please install ffmpeg using your system package manager (apt, brew, pacman).")
        return None

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = BIN_DIR / "ffmpeg.zip"

    print("Downloading static FFmpeg for Windows...")
    download_with_progress(FFMPEG_WINDOWS_URL, zip_path, description="Downloading FFmpeg")

    print("Extracting FFmpeg binary...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        for file_info in zf.infolist():
            if file_info.filename.endswith("ffmpeg.exe"):
                with zf.open(file_info) as src, open(BIN_DIR / "ffmpeg.exe", "wb") as dst:
                    shutil.copyfileobj(src, dst)
                break

    if zip_path.exists():
        zip_path.unlink()

    ffmpeg_bin = BIN_DIR / "ffmpeg.exe"
    if ffmpeg_bin.exists():
        print(f"FFmpeg provisioned successfully at: {ffmpeg_bin}")
        return ffmpeg_bin
    return None
