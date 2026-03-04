import sqlite3
import json

_db_path: str = "games.db"


def set_db_path(path: str) -> None:
    global _db_path
    _db_path = path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id    TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def save_game(state_data: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO games (game_id, state_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (state_data["game_id"], json.dumps(state_data)),
        )
        conn.commit()


def load_game(game_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT state_json FROM games WHERE game_id = ?", (game_id,)
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["state_json"])
