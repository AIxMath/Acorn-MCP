"""Database module for managing theorems and definitions."""
import atexit
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = ROOT_DIR / "acorn_mcp.db"

MAX_PAGE_SIZE = 100
DB_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="acorn-db")
atexit.register(DB_EXECUTOR.shutdown)


def _connect() -> sqlite3.Connection:
    """Create a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _run_in_executor(fn):
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(DB_EXECUTOR, fn)


def _ensure_raw_column(conn: sqlite3.Connection) -> None:
    """Add raw column to theorems table if it is missing."""
    cursor = conn.execute("PRAGMA table_info(theorems)")
    columns = {row["name"] for row in cursor.fetchall()}
    if "raw" not in columns:
        conn.execute("ALTER TABLE theorems ADD COLUMN raw TEXT")
        conn.execute("UPDATE theorems SET raw = theorem_head WHERE raw IS NULL")
        conn.commit()


async def init_database():
    """Initialize the database with theorem and definition tables."""
    def _init():
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS theorems (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    theorem_head TEXT NOT NULL,
                    proof TEXT NOT NULL,
                    raw TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS definitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    definition TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            _ensure_raw_column(conn)
            conn.commit()
        finally:
            conn.close()

    await _run_in_executor(_init)


async def add_theorem(name: str, theorem_head: str, proof: str, raw: str) -> Dict:
    """Add a new theorem to the database."""
    def _insert():
        conn = _connect()
        try:
            cursor = conn.execute(
                "INSERT INTO theorems (name, theorem_head, proof, raw) VALUES (?, ?, ?, ?)",
                (name, theorem_head, proof, raw)
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "theorem_head": theorem_head,
                "proof": proof,
                "raw": raw
            }
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Theorem with name '{name}' already exists") from exc
        finally:
            conn.close()

    return await _run_in_executor(_insert)


async def get_theorem(name: str) -> Optional[Dict]:
    """Get a theorem by name."""
    def _get():
        conn = _connect()
        try:
            cursor = conn.execute("SELECT * FROM theorems WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    return await _run_in_executor(_get)


def _build_search_clause(query: Optional[str], fields: List[str]) -> tuple[str, list]:
    """Build SQL WHERE clause and params for LIKE search."""
    if not query:
        return "", []
    term = f"%{query.strip()}%"
    clause = " WHERE " + " OR ".join(f"{field} LIKE ?" for field in fields)
    params = [term] * len(fields)
    return clause, params


async def get_theorem_count(query: Optional[str] = None) -> int:
    """Return total number of theorems (optionally filtered)."""
    def _count():
        conn = _connect()
        try:
            clause, params = _build_search_clause(
                query,
                ["name", "theorem_head", "proof", "raw"]
            )
            cursor = conn.execute(f"SELECT COUNT(*) FROM theorems{clause}", params)
            (count,) = cursor.fetchone()
            return count
        finally:
            conn.close()

    return await _run_in_executor(_count)


async def get_theorems(limit: int, offset: int = 0, query: Optional[str] = None) -> List[Dict]:
    """Return a slice of theorems ordered by recency."""
    if limit < 1:
        raise ValueError("Limit must be at least 1")
    if limit > MAX_PAGE_SIZE:
        raise ValueError(f"Limit cannot exceed {MAX_PAGE_SIZE}")

    def _list():
        conn = _connect()
        try:
            clause, params = _build_search_clause(
                query,
                ["name", "theorem_head", "proof", "raw"]
            )
            cursor = conn.execute(
                f"SELECT * FROM theorems{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (*params, limit, offset)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    return await _run_in_executor(_list)


async def get_all_theorems() -> List[Dict]:
    """Get all theorems from the database."""
    def _list_all():
        conn = _connect()
        try:
            cursor = conn.execute("SELECT * FROM theorems ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    return await _run_in_executor(_list_all)


async def add_definition(name: str, definition: str) -> Dict:
    """Add a new definition to the database."""
    def _insert():
        conn = _connect()
        try:
            cursor = conn.execute(
                "INSERT INTO definitions (name, definition) VALUES (?, ?)",
                (name, definition)
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "definition": definition
            }
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Definition with name '{name}' already exists") from exc
        finally:
            conn.close()

    return await _run_in_executor(_insert)


async def get_definition(name: str) -> Optional[Dict]:
    """Get a definition by name."""
    def _get():
        conn = _connect()
        try:
            cursor = conn.execute("SELECT * FROM definitions WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    return await _run_in_executor(_get)


async def get_definition_count(query: Optional[str] = None) -> int:
    """Return total number of definitions."""
    def _count():
        conn = _connect()
        try:
            clause, params = _build_search_clause(query, ["name", "definition"])
            cursor = conn.execute(f"SELECT COUNT(*) FROM definitions{clause}", params)
            (count,) = cursor.fetchone()
            return count
        finally:
            conn.close()

    return await _run_in_executor(_count)


async def get_definitions(limit: int, offset: int = 0, query: Optional[str] = None) -> List[Dict]:
    """Return a slice of definitions ordered by recency."""
    if limit < 1:
        raise ValueError("Limit must be at least 1")
    if limit > MAX_PAGE_SIZE:
        raise ValueError(f"Limit cannot exceed {MAX_PAGE_SIZE}")

    def _list():
        conn = _connect()
        try:
            clause, params = _build_search_clause(query, ["name", "definition"])
            cursor = conn.execute(
                f"SELECT * FROM definitions{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (*params, limit, offset)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    return await _run_in_executor(_list)


async def get_all_definitions() -> List[Dict]:
    """Get all definitions from the database."""
    def _list_all():
        conn = _connect()
        try:
            cursor = conn.execute("SELECT * FROM definitions ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    return await _run_in_executor(_list_all)
