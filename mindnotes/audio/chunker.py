"""Audio chunking utilities for splitting audio into Whisper-compatible segments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence, Union


@dataclass
class AudioChunk:
    """A slice of audio with start/end timestamps in seconds."""
    start_sec: float
    end_sec: float
    samples: Any  # 1D numpy array or sequence of float32 samples


def find_quietest_point(
    samples: Any,
    start_idx: int,
    end_idx: int,
    sample_rate: int = 16000,
    window_ms: int = 100,
    hop_ms: int = 50,
) -> int:
    """
    Find the midpoint of the lowest-energy window within [start_idx, end_idx].

    This locates natural pauses (silence, breath) to avoid cutting words in half.
    """
    window_samples = int(sample_rate * (window_ms / 1000.0))
    hop_samples = int(sample_rate * (hop_ms / 1000.0))

    default_split = start_idx + (end_idx - start_idx) // 2
    if end_idx - start_idx <= window_samples:
        return default_split

    min_energy = float("inf")
    best_split = default_split

    sub_len = end_idx - start_idx
    num_hops = max(1, (sub_len - window_samples) // hop_samples)

    try:
        import numpy as np
        if isinstance(samples, np.ndarray):
            sub = samples[start_idx:end_idx]
            for h in range(num_hops):
                pos = h * hop_samples
                w = sub[pos : pos + window_samples]
                energy = float(np.mean(np.abs(w)))
                if energy < min_energy:
                    min_energy = energy
                    best_split = start_idx + pos + (window_samples // 2)
            return best_split
    except ImportError:
        pass

    for h in range(num_hops):
        pos = h * hop_samples
        w = samples[start_idx + pos : start_idx + pos + window_samples]
        energy = sum(abs(x) for x in w) / len(w)
        if energy < min_energy:
            min_energy = energy
            best_split = start_idx + pos + (window_samples // 2)

    return best_split


def chunk_audio(
    samples: Any,
    sample_rate: int = 16000,
    max_chunk_sec: float = 28.0,
    min_chunk_sec: float = 20.0,
) -> List[AudioChunk]:
    """
    Split audio samples into chunks of <= max_chunk_sec.

    Splits at low-energy silence/pause points between min_chunk_sec and max_chunk_sec.
    """
    total_samples = len(samples)
    total_duration = total_samples / float(sample_rate)

    if total_duration <= max_chunk_sec:
        return [AudioChunk(start_sec=0.0, end_sec=total_duration, samples=samples)]

    chunks: List[AudioChunk] = []
    current_idx = 0
    max_samples = int(max_chunk_sec * sample_rate)
    min_samples = int(min_chunk_sec * sample_rate)

    while total_samples - current_idx > max_samples:
        search_start = current_idx + min_samples
        search_end = current_idx + max_samples

        split_idx = find_quietest_point(
            samples=samples,
            start_idx=search_start,
            end_idx=search_end,
            sample_rate=sample_rate,
        )

        chunk_samples = samples[current_idx:split_idx]
        chunks.append(
            AudioChunk(
                start_sec=current_idx / float(sample_rate),
                end_sec=split_idx / float(sample_rate),
                samples=chunk_samples,
            )
        )
        current_idx = split_idx

    # Final trailing chunk
    if current_idx < total_samples:
        final_samples = samples[current_idx:]
        chunks.append(
            AudioChunk(
                start_sec=current_idx / float(sample_rate),
                end_sec=total_samples / float(sample_rate),
                samples=final_samples,
            )
        )

    return chunks
