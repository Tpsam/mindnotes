import numpy as np
from mindnotes.audio.chunker import chunk_audio, find_quietest_point


def test_chunk_audio_short_file():
    # 10 seconds of silence/tone
    sr = 16000
    samples = np.zeros(10 * sr, dtype=np.float32)
    chunks = chunk_audio(samples, sample_rate=sr, max_chunk_sec=28.0)
    assert len(chunks) == 1
    assert chunks[0].start_sec == 0.0
    assert chunks[0].end_sec == 10.0
    assert len(chunks[0].samples) == 10 * sr


def test_chunk_audio_long_file_splits_under_max():
    # 70 seconds of audio
    sr = 16000
    total_samples = 70 * sr
    samples = np.ones(total_samples, dtype=np.float32) * 0.5

    # Insert silence at 24s and 50s
    samples[int(24 * sr) : int(24.5 * sr)] = 0.0
    samples[int(50 * sr) : int(50.5 * sr)] = 0.0

    chunks = chunk_audio(samples, sample_rate=sr, max_chunk_sec=28.0, min_chunk_sec=20.0)

    # Every chunk must be <= 28.0 seconds
    for c in chunks:
        duration = c.end_sec - c.start_sec
        assert duration <= 28.01, f"Chunk duration {duration} exceeds 28s"
        assert len(c.samples) == int(round((c.end_sec - c.start_sec) * sr))

    # All audio accounted for
    assert chunks[0].start_sec == 0.0
    assert abs(chunks[-1].end_sec - 70.0) < 0.01

    # First split should be at or near the silence at 24s
    assert abs(chunks[0].end_sec - 24.25) < 0.5


def test_chunk_audio_without_numpy():
    # Python list test
    sr = 16000
    samples = [0.1] * (35 * sr)
    # Insert quiet point at 25s
    for i in range(25 * sr, int(25.5 * sr)):
        samples[i] = 0.0

    chunks = chunk_audio(samples, sample_rate=sr, max_chunk_sec=28.0, min_chunk_sec=20.0)
    assert len(chunks) == 2
    assert chunks[0].end_sec <= 28.0
    assert abs(chunks[-1].end_sec - 35.0) < 0.01
