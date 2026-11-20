"""Transcription engine using sherpa-onnx."""

from __future__ import annotations

import os
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from mindnotes.config import load_config
from mindnotes.stt.models import get_model_dir, install_model, is_model_installed


@dataclass
class TranscriptSegment:
    """A timestamped segment of transcribed speech."""
    start: float
    end: float
    text: str
    speaker: Optional[str] = None

    def format_timestamp(self) -> str:
        """Format start timestamp as [MM:SS] or [HH:MM:SS]."""
        total_seconds = int(self.start)
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        if h > 0:
            return f"[{h:02d}:{m:02d}:{s:02d}]"
        return f"[{m:02d}:{s:02d}]"


@dataclass
class TranscriptResult:
    """Complete output of a transcription run."""
    text: str
    segments: List[TranscriptSegment] = field(default_factory=list)
    duration_seconds: float = 0.0
    model_name: str = ""


class TranscriptionEngine:
    """Wrapper around sherpa-onnx OfflineRecognizer supporting Whisper and NeMo CTC (Parakeet)."""

    def __init__(self, profile: str = "fast"):
        self.profile = profile
        self.config = load_config()
        self.model_dir = get_model_dir(profile)
        self._recognizer = None

    def ensure_model(self) -> None:
        """Ensure model files are downloaded."""
        if not is_model_installed(self.profile):
            print(f"Model profile '{self.profile}' not found locally. Auto-downloading...")
            install_model(self.profile)

    def _init_recognizer(self):
        """Lazy initialization of sherpa-onnx recognizer."""
        if self._recognizer is not None:
            return

        try:
            import sherpa_onnx
        except ImportError:
            raise RuntimeError(
                "sherpa-onnx is not installed. Run 'pip install sherpa-onnx' to install it."
            )

        self.ensure_model()
        profile_data = self.config.get("stt", {}).get("profiles", {}).get(self.profile, {})
        model_type = profile_data.get("type", "whisper")
        num_threads = min(4, os.cpu_count() or 2)

        if model_type == "whisper":
            encoder_path = self.model_dir / profile_data.get("encoder", "")
            decoder_path = self.model_dir / profile_data.get("decoder", "")
            tokens_path = self.model_dir / profile_data.get("tokens", "")

            self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=str(encoder_path),
                decoder=str(decoder_path),
                tokens=str(tokens_path),
                num_threads=num_threads,
                language="en",
                task="transcribe",
            )
        elif model_type == "nemo_ctc":
            model_file = self.model_dir / profile_data.get("model", "model.int8.onnx")
            if not model_file.is_file():
                onnx_candidates = list(self.model_dir.glob("*.onnx"))
                if onnx_candidates:
                    model_file = onnx_candidates[0]
            tokens_path = self.model_dir / profile_data.get("tokens", "tokens.txt")

            self._recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
                model=str(model_file),
                tokens=str(tokens_path),
                num_threads=num_threads,
            )
        else:
            raise ValueError(f"Unsupported model type '{model_type}' for profile '{self.profile}'")

    def transcribe_wav(self, wav_path: Path | str) -> TranscriptResult:
        """
        Transcribe a 16kHz mono WAV file using sherpa-onnx.

        Args:
            wav_path: Path to 16kHz mono WAV file.

        Returns:
            TranscriptResult with full text and timestamped segments.
        """
        wav_p = Path(wav_path).resolve()
        if not wav_p.exists():
            raise FileNotFoundError(f"WAV file not found: {wav_p}")

        self._init_recognizer()

        with wave.open(str(wav_p), "rb") as wf:
            n_channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            duration = n_frames / float(sample_rate) if sample_rate > 0 else 0.0

            if n_channels != 1 or sample_rate != 16000 or sampwidth != 2:
                raise ValueError(
                    f"Audio must be 16kHz mono 16-bit PCM WAV (found {sample_rate}Hz, {n_channels} ch, {sampwidth*8} bit). "
                    "Run through normalizer.normalize_audio() first."
                )

            raw_bytes = wf.readframes(n_frames)

        try:
            import numpy as np
            samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        except ImportError:
            import array
            pcm_data = array.array("h", raw_bytes)
            samples = [s / 32768.0 for s in pcm_data]

        stream = self._recognizer.create_stream()
        stream.accept_waveform(sample_rate, samples)
        self._recognizer.decode_stream(stream)
        result = stream.result

        raw_text = result.text.strip() if hasattr(result, "text") else str(result).strip()

        segments: List[TranscriptSegment] = []
        if not segments and raw_text:
            segments.append(
                TranscriptSegment(
                    start=0.0,
                    end=duration,
                    text=raw_text,
                )
            )

        return TranscriptResult(
            text=raw_text,
            segments=segments,
            duration_seconds=duration,
            model_name=self.profile,
        )
