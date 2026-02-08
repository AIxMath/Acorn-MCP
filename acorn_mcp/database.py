"""Database module for managing theorems and definitions.

WARNING: SQLite Concurrency Limitation
---------------------------------------
SQLite uses file-level locking. If you run BOTH api_server.py AND mcp_server.py
simultaneously, they will compete for the same database file and may encounter
'database is locked' errors during concurrent writes.

RECOMMENDED USAGE:
- For Formalizer integration: Run ONLY api_server.py
- For Claude Desktop MCP: Run ONLY mcp_server.py
- Never run both servers at the same time unless you accept potential lock conflicts

The ThreadPoolExecutor in this module only handles concurrency within a single
process. It does NOT prevent inter-process locking issues.

For high-concurrency production use, consider migrating to PostgreSQL.
"""
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




async def init_database():
    """Initialize the database with all required tables."""
    def _init():
        conn = _connect()
        try:
            # Create unified items table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE,
                    name TEXT NOT NULL,
                    identifier_name TEXT,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(file_path, name)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_kind ON items(kind)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_name ON items(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_uuid ON items(uuid)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_file_path ON items(file_path)")
            
            # Create theorems table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS theorems (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    theorem_head TEXT NOT NULL,
                    proof TEXT,
                    raw TEXT NOT NULL,
                    file_path TEXT,
                    line_number INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_theorems_name ON theorems(name)")
            
            # Create definitions table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS definitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    definition TEXT NOT NULL,
                    kind TEXT,
                    file_path TEXT,
                    line_number INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_definitions_name ON definitions(name)")
            
            # Create dependencies table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dependencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    dependency_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_name, source_type, target_name, dependency_type)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_source ON dependencies(source_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_target ON dependencies(target_name)")
            
            conn.commit()
        finally:
            conn.close()

    await _run_in_executor(_init)


# Unified items table functions

# WARNING: GHOST DATA RISK!
# This database has TWO parallel storage systems:
#   1. items table (via add_item) - generic storage for MCP server
#   2. theorems/definitions tables (via add_theorem/add_definition) - specialized storage for API
#
# CRITICAL RULE: For theorems and definitions accessed via Formalizer:
#   - MUST use add_theorem() / add_definition() (writes to dedicated tables)
#   - NEVER use add_item() with kind="theorem" or kind="definition"
#   - Reason: search_theorems() only queries 'theorems' table, not 'items' table
#
# If you violate this rule, data written via add_item will be "ghost data" -
# it exists in the database but is invisible to search_theorems/search_definitions.

async def add_item(name: str, kind: str, source: str,
                   uuid: Optional[str] = None, identifier_name: Optional[str] = None,
                   file_path: Optional[str] = None, line_number: Optional[int] = None) -> Dict:
    """Add a new item to the unified items table.
    
    WARNING: For theorems and definitions used by Formalizer, use add_theorem()
    or add_definition() instead. This function writes to 'items' table which is
    NOT queried by the /api/theorems and /api/definitions endpoints.
    """
    def _insert():
        conn = _connect()
        try:
            cursor = conn.execute(
                """INSERT INTO items (uuid, name, identifier_name, kind, source, file_path, line_number)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (uuid, name, identifier_name, kind, source, file_path, line_number)
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "uuid": uuid,
                "name": name,
                "identifier_name": identifier_name,
                "kind": kind,
                "source": source,
                "file_path": file_path,
                "line_number": line_number
            }
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Item with name '{name}' already exists") from exc
        finally:
            conn.close()

    return await _run_in_executor(_insert)


async def get_item(name: str) -> Optional[Dict]:
    """Get an item by name."""
    def _get():
        conn = _connect()
        try:
            cursor = conn.execute("SELECT * FROM items WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    return await _run_in_executor(_get)


async def get_item_by_uuid(uuid: str) -> Optional[Dict]:
    """Get an item by UUID."""
    def _get():
        conn = _connect()
        try:
            cursor = conn.execute("SELECT * FROM items WHERE uuid = ?", (uuid,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    return await _run_in_executor(_get)


async def get_item_count(query: Optional[str] = None, kind: Optional[str] = None) -> int:
    """Return total number of items (optionally filtered)."""
    def _count():
        conn = _connect()
        try:
            conditions = []
            params = []

            if query:
                conditions.append("(name LIKE ? OR source LIKE ?)")
                term = f"%{query.strip()}%"
                params.extend([term, term])

            if kind:
                conditions.append("kind = ?")
                params.append(kind)

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            cursor = conn.execute(f"SELECT COUNT(*) FROM items{where_clause}", params)
            (count,) = cursor.fetchone()
            return count
        finally:
            conn.close()

    return await _run_in_executor(_count)


async def get_items(limit: int, offset: int = 0, query: Optional[str] = None, kind: Optional[str] = None) -> List[Dict]:
    """Return a slice of items ordered by recency.
    
    WARNING: Search Performance Issue
    ----------------------------------
    The query parameter uses LIKE %query% which causes full table scan in SQLite.
    This is acceptable for small datasets but becomes VERY SLOW at scale (> 10k rows).
    
    FUTURE OPTIMIZATION:
    - Migrate to SQLite FTS5 (Full-Text Search) module for text search
    - Or use PostgreSQL with native full-text search capabilities
    """
    if limit < 1:
        raise ValueError("Limit must be at least 1")
    if limit > MAX_PAGE_SIZE:
        raise ValueError(f"Limit cannot exceed {MAX_PAGE_SIZE}")

    def _list():
        conn = _connect()
        try:
            # Build WHERE clause
            where_clauses = []
            params = []
            
            if query:
                where_clauses.append("(name LIKE ? OR source LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%"])
            
            if kind:
                where_clauses.append("kind = ?")
                params.append(kind)

            where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            cursor = conn.execute(
                f"SELECT * FROM items{where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (*params, limit, offset)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    return await _run_in_executor(_list)


async def get_all_items() -> List[Dict]:
    """Get all items from the database.
    
    WARNING: Performance Issue - Memory Bomb Risk
    -----------------------------------------------
    This function executes SELECT * FROM items without LIMIT, loading ALL data
    into memory at once. This is fine for small datasets (< 1000 items) but will
    cause serious problems at scale:
    
    - 10,000 items: Several hundred MB RAM
    - 100,000 items: Gigabytes of RAM, potential OOM (Out of Memory) crash
    
    FUTURE OPTIMIZATION NEEDED:
    - For export: Use streaming responses (yield data in chunks)
    - For large queries: Add pagination or cursor-based iteration
    - Consider migrating to PostgreSQL for better large-data handling
    
    Current use case (MCP server with small dataset) is fine, but avoid using
    this in production with growing data.
    """
    def _list_all():
        conn = _connect()
        try:
            cursor = conn.execute("SELECT * FROM items ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    return await _run_in_executor(_list_all)


# Legacy theorem/definition functions (kept for backward compatibility)

async def add_theorem(name: str, theorem_head: str, proof: str, raw: str,
                      file_path: Optional[str] = None, line_number: Optional[int] = None) -> Dict:
    """Add a new theorem to the database.
    
    This writes to the 'theorems' table and is the CORRECT way to store theorems
    for Formalizer integration. Data written here is queryable via /api/theorems.
    """
    def _insert():
        conn = _connect()
        try:
            cursor = conn.execute(
                """INSERT INTO theorems (name, theorem_head, proof, raw, file_path, line_number)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, theorem_head, proof, raw, file_path, line_number)
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "theorem_head": theorem_head,
                "proof": proof,
                "raw": raw,
                "file_path": file_path,
                "line_number": line_number
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


async def add_definition(name: str, definition: str, kind: Optional[str] = None,
                        file_path: Optional[str] = None, line_number: Optional[int] = None) -> Dict:
    """Add a new definition to the database.
    
    This writes to the 'definitions' table and is the CORRECT way to store definitions
    for Formalizer integration. Data written here is queryable via /api/definitions.
    """
    def _insert():
        conn = _connect()
        try:
            cursor = conn.execute(
                """INSERT INTO definitions (name, definition, kind, file_path, line_number)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, definition, kind, file_path, line_number)
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "definition": definition,
                "kind": kind,
                "file_path": file_path,
                "line_number": line_number
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


async def add_dependency(source_name: str, source_type: str, target_name: str, dependency_type: str) -> Dict:
    """Add a dependency relationship."""
    def _insert():
        conn = _connect()
        try:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO dependencies (source_name, source_type, target_name, dependency_type)
                   VALUES (?, ?, ?, ?)""",
                (source_name, source_type, target_name, dependency_type)
            )
            conn.commit()
            return {
                "source_name": source_name,
                "source_type": source_type,
                "target_name": target_name,
                "dependency_type": dependency_type
            }
        finally:
            conn.close()

    return await _run_in_executor(_insert)


async def get_dependencies(name: str) -> List[Dict]:
    """Get all dependencies for a given item."""
    def _get():
        conn = _connect()
        try:
            cursor = conn.execute(
                "SELECT * FROM dependencies WHERE source_name = ? ORDER BY target_name",
                (name,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    return await _run_in_executor(_get)


async def get_all_items_with_dependencies() -> Dict[str, any]:
    """Get all theorems, definitions, and their dependencies for topological ordering."""
    def _get_all():
        conn = _connect()
        try:
            # Get all theorems
            cursor = conn.execute("SELECT * FROM theorems ORDER BY created_at ASC")
            theorems = [dict(row) for row in cursor.fetchall()]

            # Get all definitions
            cursor = conn.execute("SELECT * FROM definitions ORDER BY created_at ASC")
            definitions = [dict(row) for row in cursor.fetchall()]

            # Get all dependencies
            cursor = conn.execute("SELECT * FROM dependencies")
            dependencies = [dict(row) for row in cursor.fetchall()]

            return {
                "theorems": theorems,
                "definitions": definitions,
                "dependencies": dependencies
            }
        finally:
            conn.close()

    return await _run_in_executor(_get_all)
