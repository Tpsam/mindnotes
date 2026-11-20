import wave
from pathlib import Path
from unittest.mock import MagicMock, patch
from mindnotes.pipeline import process_audio, move_to_processed
from mindnotes.stt.engine import TranscriptResult, TranscriptSegment
from mindnotes.structuring.notes import StructuredNote


def create_dummy_wav(path: Path, duration_sec: float = 1.0):
    """Create a minimal valid 16kHz mono 16-bit WAV file."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        n_frames = int(16000 * duration_sec)
        wf.writeframes(b"\x00\x00" * n_frames)


def test_move_to_processed(tmp_path, monkeypatch):
    processed_dir = tmp_path / "processed"
    monkeypatch.setattr("mindnotes.pipeline.PROCESSED_DIR", processed_dir)

    source = tmp_path / "test_memo.wav"
    source.write_text("dummy audio")

    # Move first time
    dest1 = move_to_processed(source)
    assert dest1.exists()
    assert dest1.name == "test_memo.wav"
    assert not source.exists()

    # Move second file with same name -> collision resolution
    source2 = tmp_path / "test_memo.wav"
    source2.write_text("dummy audio 2")
    dest2 = move_to_processed(source2)
    assert dest2.exists()
    assert dest2.name != "test_memo.wav"
    assert "test_memo_" in dest2.name


@patch("mindnotes.pipeline.normalize_audio")
@patch("mindnotes.pipeline.TranscriptionEngine")
@patch("mindnotes.pipeline.structure_quick_note")
def test_process_audio_offline_resilience(
    mock_structure,
    mock_engine_cls,
    mock_normalize,
    tmp_path,
    monkeypatch,
):
    # Setup directories
    mindnotes_home = tmp_path / "Mindnotes"
    output_dir = mindnotes_home / "output"
    processed_dir = mindnotes_home / "processed"
    monkeypatch.setattr("mindnotes.pipeline.PROCESSED_DIR", processed_dir)
    monkeypatch.setattr("mindnotes.storage.cache.OUTPUT_DIR", output_dir)
    monkeypatch.setenv("NOTION_API_KEY", "")  # Guarantee offline Notion failure

    # Mock normalize
    test_audio = tmp_path / "memo.m4a"
    test_audio.write_text("dummy")
    norm_wav = tmp_path / "memo_16k.wav"
    create_dummy_wav(norm_wav)
    mock_normalize.return_value = norm_wav

    # Mock STT
    mock_engine = MagicMock()
    mock_engine.transcribe_wav.return_value = TranscriptResult(
        text="This is a test transcript of my thoughts.",
        segments=[TranscriptSegment(start=0.0, end=1.0, text="This is a test transcript of my thoughts.")],
        duration_seconds=1.0,
        model_name="fast",
    )
    mock_engine_cls.return_value = mock_engine

    # Mock Structuring
    mock_structure.return_value = StructuredNote(
        title="Test Thoughts",
        body_markdown="Structured thoughts body.",
        tags=["Test", "Thoughts"],
        verbatim_transcript="This is a test transcript of my thoughts.",
    )

    result = process_audio(
        file_path=test_audio,
        mode="notes",
        model_profile="fast",
        move_file=True,
    )

    assert result["id"] is not None
    assert result["title"] == "Test Thoughts"
    assert result["synced"] is False  # Notion push failed gracefully without crashing
    assert Path(result["cache_file"]).exists()
    assert Path(result["processed_file"]).exists()


@patch("mindnotes.pipeline.normalize_audio")
@patch("mindnotes.pipeline.TranscriptionEngine")
@patch("mindnotes.pipeline.structure_quick_note")
def test_process_audio_chunked_timestamp_formatting(
    mock_structure,
    mock_engine_cls,
    mock_normalize,
    tmp_path,
    monkeypatch,
):
    mindnotes_home = tmp_path / "Mindnotes"
    output_dir = mindnotes_home / "output"
    processed_dir = mindnotes_home / "processed"
    monkeypatch.setattr("mindnotes.pipeline.PROCESSED_DIR", processed_dir)
    monkeypatch.setattr("mindnotes.storage.cache.OUTPUT_DIR", output_dir)
    monkeypatch.setenv("NOTION_API_KEY", "")

    test_audio = tmp_path / "long_memo.wav"
    create_dummy_wav(test_audio, duration_sec=60.0)
    mock_normalize.return_value = test_audio

    mock_engine = MagicMock()
    mock_engine.transcribe_wav.return_value = TranscriptResult(
        text="First chunk sentence. Second chunk sentence.",
        segments=[
            TranscriptSegment(start=0.0, end=25.0, text="First chunk sentence."),
            TranscriptSegment(start=25.0, end=60.0, text="Second chunk sentence."),
        ],
        duration_seconds=60.0,
        model_name="fast",
    )
    mock_engine_cls.return_value = mock_engine

    mock_structure.return_value = StructuredNote(
        title="Long Note",
        body_markdown="Note body",
        tags=["Long"],
        verbatim_transcript="[00:00] First chunk sentence.\n\n[00:25] Second chunk sentence.",
    )

    result = process_audio(
        file_path=test_audio,
        mode="notes",
        model_profile="fast",
        move_file=False,
    )

    # Verify structure_quick_note received formatted verbatim transcript with timestamps
    mock_structure.assert_called_once()
    called_kwargs = mock_structure.call_args.kwargs
    assert "[00:00] First chunk sentence." in called_kwargs["verbatim_transcript"]
    assert "[00:25] Second chunk sentence." in called_kwargs["verbatim_transcript"]
    assert called_kwargs["cleaned_transcript"] == "First chunk sentence. Second chunk sentence."
