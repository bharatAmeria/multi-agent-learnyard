"""Wrapper around the SQLite MCP server — long-term memory store."""
import json
import sqlite3
import sys
from pathlib import Path

from config import settings
from exception import MyException
from logger import GLOBAL_LOGGER as logger


def _connect() -> sqlite3.Connection:
    try:
        db_path = Path(settings.sqlite_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        # Some synced/network filesystems don't support the rollback-journal's
        # file locking, which surfaces as "disk I/O error". MEMORY journal mode
        # avoids touching a second lock file on disk.
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS project_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_requirement TEXT,
                architecture_plan TEXT,
                review_feedback TEXT,
                quality_score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        return conn
    except Exception as e:
        logger.error("sqlite_connect_failed", db_path=settings.sqlite_db_path, error=str(e))
        raise MyException(e, sys) from e


def save_project_memory(state: dict) -> int:
    try:
        conn = _connect()
        cur = conn.execute(
            "INSERT INTO project_memory (user_requirement, architecture_plan, review_feedback, quality_score) "
            "VALUES (?, ?, ?, ?)",
            (
                state.get("user_requirement", ""),
                state.get("architecture_plan", ""),
                state.get("review_feedback", ""),
                state.get("quality_score", 0.0),
            ),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        logger.info("project_memory_saved", row_id=row_id)
        return row_id
    except MyException:
        raise
    except Exception as e:
        logger.error("save_project_memory_failed", error=str(e))
        raise MyException(e, sys) from e


def fetch_recent_memory(limit: int = 5) -> list[dict]:
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT user_requirement, architecture_plan, review_feedback, quality_score "
            "FROM project_memory ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        cols = ["user_requirement", "architecture_plan", "review_feedback", "quality_score"]
        return [dict(zip(cols, row)) for row in rows]
    except MyException:
        raise
    except Exception as e:
        logger.error("fetch_recent_memory_failed", error=str(e))
        raise MyException(e, sys) from e
