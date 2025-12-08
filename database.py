"""Database module for managing theorems and definitions."""
import aiosqlite
import os
from typing import List, Dict, Optional

DATABASE_PATH = "acorn_mcp.db"


async def init_database():
    """Initialize the database with theorem and definition tables."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Create theorems table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS theorems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                theorem_head TEXT NOT NULL,
                proof TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create definitions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                definition TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()


async def add_theorem(name: str, theorem_head: str, proof: str) -> Dict:
    """Add a new theorem to the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            cursor = await db.execute(
                "INSERT INTO theorems (name, theorem_head, proof) VALUES (?, ?, ?)",
                (name, theorem_head, proof)
            )
            await db.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "theorem_head": theorem_head,
                "proof": proof
            }
        except aiosqlite.IntegrityError:
            raise ValueError(f"Theorem with name '{name}' already exists")


async def get_theorem(name: str) -> Optional[Dict]:
    """Get a theorem by name."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM theorems WHERE name = ?",
            (name,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def get_all_theorems() -> List[Dict]:
    """Get all theorems from the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM theorems ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def add_definition(name: str, definition: str) -> Dict:
    """Add a new definition to the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            cursor = await db.execute(
                "INSERT INTO definitions (name, definition) VALUES (?, ?)",
                (name, definition)
            )
            await db.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "definition": definition
            }
        except aiosqlite.IntegrityError:
            raise ValueError(f"Definition with name '{name}' already exists")


async def get_definition(name: str) -> Optional[Dict]:
    """Get a definition by name."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM definitions WHERE name = ?",
            (name,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def get_all_definitions() -> List[Dict]:
    """Get all definitions from the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM definitions ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
