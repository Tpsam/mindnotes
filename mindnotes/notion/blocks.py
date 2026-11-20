"""Notion block builder and Markdown-to-Notion translator."""

from __future__ import annotations

import re
from typing import Any, Dict, List

MAX_TEXT_LENGTH = 2000  # Notion's maximum rich_text content length


def chunk_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> List[str]:
    """Split text into chunks of at most max_length characters."""
    if not text:
        return []
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = 0
    while current < len(text):
        chunk = text[current : current + max_length]
        chunks.append(chunk)
        current += max_length
    return chunks


def make_rich_text(text: str) -> List[Dict[str, Any]]:
    """Convert a string into a list of Notion rich_text objects, respecting length limits."""
    chunks = chunk_text(text, MAX_TEXT_LENGTH)
    if not chunks:
        return []
    return [{"type": "text", "text": {"content": c}} for c in chunks]


def make_paragraph_block(text: str) -> Dict[str, Any]:
    """Create a Notion paragraph block."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": make_rich_text(text),
        },
    }


def make_heading_block(text: str, level: int = 2) -> Dict[str, Any]:
    """Create a Notion heading_1, heading_2, or heading_3 block."""
    lvl = max(1, min(3, level))
    heading_type = f"heading_{lvl}"
    return {
        "object": "block",
        "type": heading_type,
        heading_type: {
            "rich_text": make_rich_text(text),
        },
    }


def make_bullet_block(text: str) -> Dict[str, Any]:
    """Create a Notion bulleted_list_item block."""
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": make_rich_text(text),
        },
    }


def make_toggle_block(title: str, content: str) -> Dict[str, Any]:
    """
    Create a Notion toggle block containing the verbatim transcript as children.
    """
    # Split content by paragraphs or chunks
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [content.strip() or "No transcript available."]

    children = []
    for p in paragraphs:
        for chunk in chunk_text(p, MAX_TEXT_LENGTH):
            children.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}],
                    },
                }
            )

    # Notion allows max 100 children per append block call
    children = children[:100]

    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}],
            "children": children,
        },
    }


def markdown_to_notion_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """
    Translate standard Markdown text into Notion block dictionaries.
    Handles headings (#, ##, ###), bullets (*, -), and regular paragraphs.
    """
    blocks: List[Dict[str, Any]] = []
    lines = markdown_text.splitlines()
    buffer: List[str] = []

    def flush_buffer():
        if buffer:
            joined = " ".join(buffer).strip()
            if joined:
                blocks.append(make_paragraph_block(joined))
            buffer.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_buffer()
            continue

        # Check for Headings
        heading_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading_match:
            flush_buffer()
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            blocks.append(make_heading_block(text, level))
            continue

        # Check for Bullet items
        bullet_match = re.match(r"^[-*•]\s+(.*)$", stripped)
        if bullet_match:
            flush_buffer()
            blocks.append(make_bullet_block(bullet_match.group(1)))
            continue

        # Check for Numbered items
        num_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if num_match:
            flush_buffer()
            # For simplicity render as bulleted item with number preserved
            blocks.append(make_bullet_block(stripped))
            continue

        # Otherwise append to paragraph buffer
        buffer.append(stripped)

    flush_buffer()
    return blocks
