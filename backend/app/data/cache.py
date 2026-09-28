import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "cache.sqlite"
TTL = timedelta(hours=12)


def _connect() -> sqlite3.Connection:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_cache (
            code TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS report_cache (
            code TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS blob_cache (
            code TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
        """
    )
    return conn


def get_cached(code: str) -> dict | None:
    return _read("quote_cache", code)


def set_cached(code: str, payload: dict) -> None:
    _write("quote_cache", code, payload)


def get_report_cached(code: str) -> dict | None:
    return _read("report_cache", code)


def set_report_cached(code: str, payload: dict) -> None:
    _write("report_cache", code, payload)


def get_blob_cached(key: str) -> dict | None:
    return _read("blob_cache", key)


def set_blob_cached(key: str, payload: dict) -> None:
    _write("blob_cache", key, payload)


def _read(table: str, code: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            f"SELECT payload, fetched_at FROM {table} WHERE code = ?",
            (code,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    fetched_at = datetime.fromisoformat(row[1])
    if datetime.now(timezone.utc) - fetched_at > TTL:
        return None
    return json.loads(row[0])


def _write(table: str, code: str, payload: dict) -> None:
    conn = _connect()
    try:
        conn.execute(
            f"""
            INSERT INTO {table} (code, payload, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                payload = excluded.payload,
                fetched_at = excluded.fetched_at
            """,
            (code, json.dumps(payload, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
