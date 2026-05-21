import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from api_backend.config import Config

DB_PATH: Path = Config.DATA_DIR / "audit_cache.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audits (
            doc_id       TEXT PRIMARY KEY,
            created_at   TEXT NOT NULL,
            updated_at   TEXT,
            results_json TEXT NOT NULL
        )
        """
    )
    # Migraciones idempotentes para DBs existentes
    for col in ("ALTER TABLE audits ADD COLUMN updated_at TEXT",
                "ALTER TABLE audits ADD COLUMN source_hash TEXT"):
        try:
            conn.execute(col)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn


def save(doc_id: str, result: dict, source_hash: str | None = None) -> None:
    slim = {k: v for k, v in result.items() if k not in ("reporte_txt", "reporte_csv")}
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audits (doc_id, created_at, source_hash, results_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                updated_at   = ?,
                source_hash  = ?,
                results_json = excluded.results_json
            """,
            (doc_id, now, source_hash, json.dumps(slim), now, source_hash),
        )


def load(doc_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT results_json FROM audits WHERE doc_id = ?", (doc_id,)
        ).fetchone()
    return json.loads(row[0]) if row else None


def exists(doc_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM audits WHERE doc_id = ?", (doc_id,)
        ).fetchone()
    return row is not None


def get_meta(doc_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT created_at, updated_at, source_hash FROM audits WHERE doc_id = ?", (doc_id,)
        ).fetchone()
    if row is None:
        return None
    return {"created_at": row[0], "updated_at": row[1], "source_hash": row[2]}


def get_all() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT doc_id, created_at, updated_at, source_hash, results_json FROM audits"
        ).fetchall()
    return [
        {
            "doc_id": r[0],
            "created_at": r[1],
            "updated_at": r[2],
            "source_hash": r[3],
            "results": json.loads(r[4]),
        }
        for r in rows
    ]