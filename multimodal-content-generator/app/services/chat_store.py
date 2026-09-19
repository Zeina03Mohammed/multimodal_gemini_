"""
Persists chat conversations and messages to a local SQLite database, so
conversation history survives an app/server restart - unlike the vector
store's documents, chat history has no reason to live anywhere fancier.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

_db_path = Path(settings.chat_db_path)
_db_path.parent.mkdir(parents=True, exist_ok=True)

# check_same_thread=False: FastAPI's default (sync, threadpool-backed)
# endpoints may run this on different worker threads across requests.
_connection = sqlite3.connect(_db_path, check_same_thread=False)
_connection.execute(
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """
)
_connection.execute(
    """
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(id),
        role TEXT NOT NULL,
        text TEXT,
        image_base64 TEXT,
        image_mime_type TEXT,
        sources_json TEXT,
        created_at TEXT NOT NULL
    )
    """
)
_connection.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_conversation(title: str) -> dict:
    conversation_id = str(uuid.uuid4())
    created_at = _now()
    _connection.execute(
        "INSERT INTO conversations (id, title, created_at) VALUES (?, ?, ?)",
        (conversation_id, title, created_at),
    )
    _connection.commit()
    return {"conversation_id": conversation_id, "title": title, "created_at": created_at}


def list_conversations() -> list[dict]:
    rows = _connection.execute(
        "SELECT id, title, created_at FROM conversations ORDER BY created_at DESC"
    ).fetchall()
    return [{"conversation_id": r[0], "title": r[1], "created_at": r[2]} for r in rows]


def conversation_exists(conversation_id: str) -> bool:
    row = _connection.execute(
        "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    return row is not None


def update_title(conversation_id: str, title: str) -> None:
    _connection.execute(
        "UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id)
    )
    _connection.commit()


def get_messages(conversation_id: str) -> list[dict]:
    rows = _connection.execute(
        "SELECT role, text, image_base64, image_mime_type, sources_json, created_at "
        "FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (conversation_id,),
    ).fetchall()
    return [
        {
            "role": r[0],
            "text": r[1],
            "image_base64": r[2],
            "image_mime_type": r[3],
            "sources": json.loads(r[4]) if r[4] else [],
            "created_at": r[5],
        }
        for r in rows
    ]


def add_message(
    conversation_id: str,
    role: str,
    text: str | None = None,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
    sources: list[dict] | None = None,
) -> dict:
    created_at = _now()
    _connection.execute(
        "INSERT INTO messages "
        "(id, conversation_id, role, text, image_base64, image_mime_type, sources_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            conversation_id,
            role,
            text,
            image_base64,
            image_mime_type,
            json.dumps(sources) if sources else None,
            created_at,
        ),
    )
    _connection.commit()
    return {
        "role": role,
        "text": text,
        "image_base64": image_base64,
        "image_mime_type": image_mime_type,
        "sources": sources or [],
        "created_at": created_at,
    }


def delete_conversation(conversation_id: str) -> bool:
    if not conversation_exists(conversation_id):
        return False
    _connection.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    _connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    _connection.commit()
    return True
