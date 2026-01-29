#!/usr/bin/env python3
"""
Extract today's Cursor AI conversations from the SQLite database.

Outputs JSON with conversation metadata for cursor-agent to summarize.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_db_path() -> Path:
    """Get the path to Cursor's SQLite database."""
    return Path.home() / "Library/Application Support/Cursor/User/globalStorage/state.vscdb"


def extract_text_from_richtext(richtext_json: str) -> str:
    """Extract plain text from Lexical richText JSON format."""
    try:
        data = json.loads(richtext_json)
        texts = []
        
        def extract_text_nodes(node: dict) -> None:
            if node.get("type") == "text" and "text" in node:
                texts.append(node["text"])
            for child in node.get("children", []):
                extract_text_nodes(child)
        
        if "root" in data:
            extract_text_nodes(data["root"])
        
        return " ".join(texts).strip()
    except (json.JSONDecodeError, KeyError, TypeError):
        return ""


def get_first_user_message(conn: sqlite3.Connection, composer_id: str, bubbles: list[dict]) -> str:
    """Get the first user message (type=1) from a conversation."""
    for bubble in bubbles:
        if bubble.get("type") == 1:  # type 1 = user message
            bubble_id = bubble.get("bubbleId")
            if bubble_id:
                key = f"bubbleId:{composer_id}:{bubble_id}"
                cursor = conn.execute(
                    "SELECT value FROM cursorDiskKV WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    try:
                        bubble_data = json.loads(row[0])
                        richtext = bubble_data.get("richText", "")
                        if richtext:
                            text = extract_text_from_richtext(richtext)
                            if text:
                                # Truncate long messages
                                return text[:500] + "..." if len(text) > 500 else text
                    except (json.JSONDecodeError, TypeError):
                        pass
    return ""


def get_workspace_from_uri(code_block_data: dict) -> Optional[str]:
    """Extract workspace path from codeBlockData URIs."""
    for uri_key in code_block_data.keys():
        if uri_key.startswith("file:///"):
            # Extract workspace from path like /Users/user/workspace/project/...
            path = uri_key.replace("file://", "")
            parts = path.split("/")
            # Look for common workspace indicators
            for i, part in enumerate(parts):
                if part == "workspace" and i + 2 < len(parts):
                    return "/".join(parts[:i+3])
            # Fallback: return up to 4 levels deep
            if len(parts) > 4:
                return "/".join(parts[:5])
    return None


def extract_todays_conversations(target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Extract conversations from today (or specified date)."""
    db_path = get_db_path()
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        return []
    
    # Calculate date boundaries (in milliseconds)
    if target_date is None:
        target_date = datetime.now()
    
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    
    start_ms = int(start_of_day.timestamp() * 1000)
    end_ms = int(end_of_day.timestamp() * 1000)
    
    conversations = []
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
        )
        
        for key, value in cursor.fetchall():
            if not value:
                continue
                
            try:
                data = json.loads(value)
            except json.JSONDecodeError:
                continue
            
            # Check if conversation was active today
            created_at = data.get("createdAt", 0)
            last_updated = data.get("lastUpdatedAt", 0)
            
            # Include if created or updated today
            if not ((start_ms <= created_at < end_ms) or (start_ms <= last_updated < end_ms)):
                continue
            
            # Extract conversation details
            composer_id = data.get("composerId", "")
            name = data.get("name", "Untitled conversation")
            status = data.get("status", "unknown")
            bubbles = data.get("fullConversationHeadersOnly", [])
            model_config = data.get("modelConfig", {})
            model_name = model_config.get("modelName", "unknown")
            code_block_data = data.get("codeBlockData", {})
            
            # Get first user message for context
            first_message = get_first_user_message(conn, composer_id, bubbles)
            
            # Try to extract workspace
            workspace = get_workspace_from_uri(code_block_data)
            
            # Convert timestamps to readable format
            created_time = datetime.fromtimestamp(created_at / 1000).strftime("%H:%M") if created_at else "unknown"
            
            conversations.append({
                "id": composer_id,
                "name": name,
                "created_at": created_time,
                "timestamp_ms": created_at,
                "status": status,
                "model": model_name,
                "message_count": len(bubbles),
                "first_message": first_message,
                "workspace": workspace,
            })
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        return []
    
    # Sort by creation time
    conversations.sort(key=lambda x: x.get("timestamp_ms", 0))
    
    return conversations


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract Cursor conversations")
    parser.add_argument(
        "--date",
        type=str,
        help="Target date in YYYY-MM-DD format (default: today)",
        default=None
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="Output format"
    )
    
    args = parser.parse_args()
    
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date format: {args.date}", file=sys.stderr)
            sys.exit(1)
    
    conversations = extract_todays_conversations(target_date)
    
    if args.format == "json":
        print(json.dumps(conversations, indent=2))
    else:
        # Summary format for quick viewing
        if not conversations:
            print("No conversations found for the specified date.")
        else:
            print(f"Found {len(conversations)} conversation(s):\n")
            for conv in conversations:
                print(f"[{conv['created_at']}] {conv['name']}")
                print(f"  Model: {conv['model']} | Messages: {conv['message_count']} | Status: {conv['status']}")
                if conv['first_message']:
                    preview = conv['first_message'][:100] + "..." if len(conv['first_message']) > 100 else conv['first_message']
                    print(f"  First message: {preview}")
                if conv['workspace']:
                    print(f"  Workspace: {conv['workspace']}")
                print()


if __name__ == "__main__":
    main()
