"""Quick Notes mode structuring using a single LLM pass."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional
from mindnotes.llm.client import LLMClient


@dataclass
class StructuredNote:
    """Structured representation of a Quick Note."""
    title: str
    body_markdown: str
    tags: List[str] = field(default_factory=list)
    verbatim_transcript: str = ""

    def to_markdown(self) -> str:
        """Render complete note to Markdown including tags and toggle transcript."""
        tags_line = " ".join([f"`#{t}`" for t in self.tags]) if self.tags else ""
        lines = [f"# {self.title}\n"]
        if tags_line:
            lines.append(f"**Tags:** {tags_line}\n")
        lines.append(self.body_markdown.strip())
        lines.append("\n\n---\n")
        lines.append("<details>\n<summary><b>Full Transcript</b></summary>\n\n")
        lines.append(self.verbatim_transcript.strip())
        lines.append("\n\n</details>\n")
        return "\n".join(lines)


SYSTEM_PROMPT = """You are an expert personal note synthesizer.
Your task is to take a raw voice memo transcript and turn it into a high-value, organized first-draft note.

Return a STRICT JSON object with the following keys:
1. "title": A concise, clear title capturing the core idea (4 to 8 words).
2. "body_markdown": The structured note in clean GitHub-flavored Markdown. Organize ideas logically into coherent paragraphs, clear bullet points, action items (if any), or numbered takeaways. Remove stream-of-consciousness rambling while preserving all insights, facts, and intent.
3. "tags": A list of 2 to 3 concise relevant tags (e.g. ["Product", "Strategy"]).

Output ONLY the JSON object. Do not wrap with conversational commentary.
"""


def extract_json_payload(raw_response: str) -> dict:
    """Safely extract JSON from an LLM response string."""
    text = raw_response.strip()
    # Strip markdown code blocks if present
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
    return json.loads(text)


def structure_quick_note(
    cleaned_transcript: str,
    verbatim_transcript: str = "",
    client: Optional[LLMClient] = None,
) -> StructuredNote:
    """
    Pass cleaned transcript to LLM to generate title, body, and tags.
    """
    if not cleaned_transcript.strip():
        return StructuredNote(
            title="Empty Note",
            body_markdown="No spoken content detected.",
            tags=["Empty"],
            verbatim_transcript=verbatim_transcript,
        )

    llm = client or LLMClient()
    user_prompt = f"Transcript:\n\"\"\"\n{cleaned_transcript}\n\"\"\""

    response = llm.complete(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_prompt,
        max_tokens=1500,
    )

    try:
        data = extract_json_payload(response.raw)
        title = data.get("title", "Voice Note").strip()
        body_markdown = data.get("body_markdown", "").strip()
        tags = [str(t).strip() for t in data.get("tags", []) if str(t).strip()]
    except Exception as e:
        # Fallback if JSON parsing fails
        title = "Voice Note"
        body_markdown = response.raw.strip()
        tags = ["Draft"]

    return StructuredNote(
        title=title,
        body_markdown=body_markdown,
        tags=tags,
        verbatim_transcript=verbatim_transcript or cleaned_transcript,
    )
