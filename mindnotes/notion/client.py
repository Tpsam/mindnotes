"""Notion API integration client."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from mindnotes.config import load_config
from mindnotes.notion.blocks import (
    make_rich_text,
    make_toggle_block,
    markdown_to_notion_blocks,
)
from mindnotes.structuring.notes import StructuredNote


class NotionIntegrationError(Exception):
    """Raised on Notion API connection or schema failure."""
    pass


class NotionSyncClient:
    """Client for writing structured notes to Notion databases."""

    def __init__(self, token: Optional[str] = None):
        load_config()
        self.token = token or os.getenv("NOTION_API_KEY")
        if not self.token:
            raise NotionIntegrationError(
                "NOTION_API_KEY is not set. Set it in ~/Mindnotes/.env or run 'mindnotes setup'."
            )
        try:
            from notion_client import Client
            self.client = Client(auth=self.token)
        except ImportError:
            raise NotionIntegrationError(
                "notion-client is not installed. Run 'pip install notion-client'."
            )

    def _get_database_properties(self, db_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Extract properties from database metadata or associated data source."""
        props = db_meta.get("properties")
        if props:
            return props

        # Support Notion API v2025+ data_sources
        data_sources = db_meta.get("data_sources")
        if data_sources and isinstance(data_sources, list) and len(data_sources) > 0:
            ds_id = data_sources[0].get("id")
            if ds_id and hasattr(self.client, "data_sources"):
                try:
                    ds_meta = self.client.data_sources.retrieve(ds_id)
                    return ds_meta.get("properties", {})
                except Exception:
                    pass

        return {}

    def test_connection(self) -> Dict[str, Any]:
        """Verify Notion token validity and database schema accessibility."""
        config = load_config()
        results: Dict[str, Any] = {
            "authenticated": False,
            "bot_user": None,
            "notes_db": {"id": config.get("notion", {}).get("notes_db_id"), "valid": False, "error": None},
            "content_db": {"id": config.get("notion", {}).get("content_db_id"), "valid": False, "error": None},
        }

        try:
            bot_info = self.client.users.me()
            results["authenticated"] = True
            results["bot_user"] = bot_info.get("name") or bot_info.get("id")
        except Exception as e:
            results["error"] = f"Failed to authenticate with Notion: {e}"
            return results

        notes_db_id = results["notes_db"]["id"]
        if notes_db_id:
            try:
                db_info = self.client.databases.retrieve(database_id=notes_db_id)
                props = self._get_database_properties(db_info)
                results["notes_db"]["valid"] = True
                results["notes_db"]["title"] = db_info.get("title", [{}])[0].get("plain_text", "Untitled")
                results["notes_db"]["properties"] = list(props.keys())
            except Exception as e:
                results["notes_db"]["error"] = str(e)
        else:
            results["notes_db"]["error"] = "NOTION_NOTES_DB_ID not configured."

        content_db_id = results["content_db"]["id"]
        if content_db_id:
            try:
                db_info = self.client.databases.retrieve(database_id=content_db_id)
                props = self._get_database_properties(db_info)
                results["content_db"]["valid"] = True
                results["content_db"]["title"] = db_info.get("title", [{}])[0].get("plain_text", "Untitled")
                results["content_db"]["properties"] = list(props.keys())
            except Exception as e:
                results["content_db"]["error"] = str(e)
        else:
            results["content_db"]["error"] = "NOTION_CONTENT_DB_ID not configured."

        return results

    def push_quick_note(
        self,
        note: StructuredNote,
        source_audio: str,
        database_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Create a new page in the Notion Notes DB for a Quick Note.
        Includes structured body and a collapsible toggle containing verbatim transcript.
        """
        config = load_config()
        db_id = database_id or config.get("notion", {}).get("notes_db_id")
        if not db_id:
            raise NotionIntegrationError(
                "No Notes Database ID provided or configured. Set NOTION_NOTES_DB_ID."
            )

        try:
            db_meta = self.client.databases.retrieve(database_id=db_id)
            existing_props = self._get_database_properties(db_meta)
        except Exception as e:
            raise NotionIntegrationError(f"Could not access Notes DB ({db_id}): {e}")

        # Find title property
        title_prop_name = None
        for prop_name, prop_data in existing_props.items():
            if prop_data.get("type") == "title":
                title_prop_name = prop_name
                break
        if not title_prop_name:
            if "Name" in existing_props:
                title_prop_name = "Name"
            elif "Title" in existing_props:
                title_prop_name = "Title"
            else:
                title_prop_name = "Name"

        properties: Dict[str, Any] = {
            title_prop_name: {
                "title": [{"type": "text", "text": {"content": note.title or "Untitled Note"}}]
            }
        }

        # Multi-select: Tags
        if "Tags" in existing_props and existing_props["Tags"].get("type") == "multi_select":
            properties["Tags"] = {
                "multi_select": [{"name": t} for t in note.tags[:5]]
            }

        # Rich text: Source Audio
        if "Source Audio" in existing_props and existing_props["Source Audio"].get("type") == "rich_text":
            properties["Source Audio"] = {
                "rich_text": make_rich_text(source_audio)
            }

        # Date: Created
        if "Created" in existing_props and existing_props["Created"].get("type") == "date":
            now_iso = datetime.now(timezone.utc).date().isoformat()
            properties["Created"] = {"date": {"start": now_iso}}

        # Status: Status
        if "Status" in existing_props:
            prop_type = existing_props["Status"].get("type")
            if prop_type == "status":
                properties["Status"] = {"status": {"name": "Draft"}}
            elif prop_type == "select":
                properties["Status"] = {"select": {"name": "Draft"}}

        body_blocks = markdown_to_notion_blocks(note.body_markdown)
        toggle_block = make_toggle_block("Full Transcript", note.verbatim_transcript)
        all_blocks = body_blocks + [toggle_block]
        initial_children = all_blocks[:100]

        try:
            page = self.client.pages.create(
                parent={"database_id": db_id},
                properties=properties,
                children=initial_children,
            )
            page_id = page["id"]
            url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
            return {"page_id": page_id, "url": url}
        except Exception as e:
            # If status name doesn't match predefined options in user's DB, retry without status
            if "Status" in properties and ("status" in str(e).lower() or "select" in str(e).lower() or "option" in str(e).lower()):
                del properties["Status"]
                try:
                    page = self.client.pages.create(
                        parent={"database_id": db_id},
                        properties=properties,
                        children=initial_children,
                    )
                    page_id = page["id"]
                    url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
                    return {"page_id": page_id, "url": url}
                except Exception as inner_e:
                    raise NotionIntegrationError(f"Failed to create Notion page: {inner_e}")
            raise NotionIntegrationError(f"Failed to create Notion page: {e}")
