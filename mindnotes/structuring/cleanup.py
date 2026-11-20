"""Transcript cleanup and normalization."""

from __future__ import annotations

import re


def clean_transcript(raw_text: str) -> str:
    """
    Clean up filler words, excessive spaces, and minor verbal tics from raw speech.
    Preserves verbatim meaning while making the text cleaner for LLM consumption.
    """
    if not raw_text:
        return ""

    text = raw_text

    # Remove standalone filler words (case-insensitive)
    filler_patterns = [
        r"\b(um+h*|uh+h*|er+h*)\b",
        r"\b(you know|sort of|kind of|i mean)\b(?=[\s,]+(you know|sort of|kind of|i mean))",  # duplicated fillers
    ]
    for pattern in filler_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Clean repeated duplicate words (e.g. "the the", "like like")
    text = re.sub(r"\b([a-zA-Z]+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)

    # Clean multiple spaces and irregular commas
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r",+", ",", text)
    text = re.sub(r"\s*\.\s*", ". ", text)
    text = re.sub(r"\.+", ".", text)

    # Clean whitespace around punctuation
    text = text.strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text
