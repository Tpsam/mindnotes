import json
from unittest.mock import MagicMock
from mindnotes.structuring.cleanup import clean_transcript
from mindnotes.structuring.notes import (
    StructuredNote,
    structure_quick_note,
    extract_json_payload,
)
from mindnotes.llm.client import LLMResponse


def test_clean_transcript():
    raw = "um, so basically like like we need to, uh, fix this right now."
    cleaned = clean_transcript(raw)
    assert "um" not in cleaned.lower()
    assert "uh" not in cleaned.lower()
    assert "like like" not in cleaned
    assert "fix this right now" in cleaned


def test_extract_json_payload():
    valid = '{"title": "Test Title", "body_markdown": "Test Body", "tags": ["Tag1"]}'
    res = extract_json_payload(valid)
    assert res["title"] == "Test Title"

    wrapped = '```json\n{"title": "Wrapped Title", "body_markdown": "Body", "tags": []}\n```'
    res2 = extract_json_payload(wrapped)
    assert res2["title"] == "Wrapped Title"


def test_structure_quick_note():
    mock_client = MagicMock()
    mock_client.complete.return_value = LLMResponse(
        raw=json.dumps({
            "title": "Quarterly Launch Plan",
            "body_markdown": "### Goals\n- Finish the build on time.\n- Ship to production.",
            "tags": ["Launch", "Q4"]
        }),
        provider="mock",
        model="mock-model",
        latency_ms=120,
    )

    note = structure_quick_note(
        cleaned_transcript="We need to finish the build on time and ship to production for the launch.",
        verbatim_transcript="Um we need to finish the build on time and ship to production for the launch.",
        client=mock_client,
    )

    assert note.title == "Quarterly Launch Plan"
    assert "Finish the build" in note.body_markdown
    assert "Launch" in note.tags
    assert "<summary><b>Full Transcript</b></summary>" in note.to_markdown()
    assert "Um we need to finish" in note.to_markdown()
