from mindnotes.notion.blocks import (
    chunk_text,
    make_rich_text,
    make_toggle_block,
    markdown_to_notion_blocks,
    MAX_TEXT_LENGTH,
)


def test_chunk_text():
    short = "Short text"
    assert chunk_text(short, 100) == [short]

    long_text = "A" * 2500
    chunks = chunk_text(long_text, MAX_TEXT_LENGTH)
    assert len(chunks) == 2
    assert len(chunks[0]) == 2000
    assert len(chunks[1]) == 500


def test_make_toggle_block():
    toggle = make_toggle_block("Full Transcript", "This is the transcript content.")
    assert toggle["object"] == "block"
    assert toggle["type"] == "toggle"
    assert toggle["toggle"]["rich_text"][0]["text"]["content"] == "Full Transcript"
    assert len(toggle["toggle"]["children"]) == 1
    assert toggle["toggle"]["children"][0]["paragraph"]["rich_text"][0]["text"]["content"] == "This is the transcript content."


def test_markdown_to_notion_blocks():
    md = """# Top Heading
## Second Heading
Here is a paragraph of regular text.

- First bullet
- Second bullet
"""
    blocks = markdown_to_notion_blocks(md)
    assert len(blocks) == 5
    assert blocks[0]["type"] == "heading_1"
    assert blocks[1]["type"] == "heading_2"
    assert blocks[2]["type"] == "paragraph"
    assert blocks[3]["type"] == "bulleted_list_item"
    assert blocks[4]["type"] == "bulleted_list_item"
