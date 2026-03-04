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
ACORNLIB_SRC = ROOT_DIR / "acornlib" / "src"

MAX_PAGE_SIZE = 100
DB_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="acorn-db")
atexit.register(DB_EXECUTOR.shutdown)



def _is_import_line(line: str) -> bool:
    """Check if a line is an Acorn import/numerals statement.
    
    Matches:
      - ``import module_name``
      - ``from module import Item1, Item2``
      - ``numerals TypeName``
    
    Comments and blank lines are NOT considered import lines.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
        return False
    return (stripped.startswith("import ")
            or stripped.startswith("from ")
            or stripped.startswith("numerals "))


def _split_imports_body(content: str) -> tuple[list[str], list[str]]:
    """Split Acorn source content into import lines and body lines.
    
    The import section is defined as the contiguous block of import/numerals
    lines (plus interleaved blank lines and comments) at the **top** of the
    content.  Everything after the first non-import, non-blank, non-comment
    line belongs to the body.
    
    Returns:
        (import_lines, body_lines) – each is a list of raw line strings
        (without trailing newline).
    """
    lines = content.split("\n")
    
    import_lines: list[str] = []
    body_start_idx = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            # Blank / comment – part of the import header while we haven't
            # seen any body yet.
            import_lines.append(line)
        elif _is_import_line(line):
            import_lines.append(line)
        else:
            # First real body line – everything from here on is body.
            body_start_idx = i
            break
    else:
        # Entire content is imports (or empty).
        return import_lines, []
    
    # Trim trailing blank lines from import section (they'll be re-added as
    # separators when we write the file).
    while import_lines and not import_lines[-1].strip():
        import_lines.pop()
    
    body_lines = lines[body_start_idx:]
    return import_lines, body_lines


def _read_file_sections(full_path: Path) -> tuple[list[str], list[str]]:
    """Read an existing .ac file and split into import lines and body lines."""
    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()
    return _split_imports_body(content)


def _append_to_file(relative_path: str, content: str) -> tuple[int, int | None]:
    """Append content to a file in acornlib/src with import deduplication.
    
    When appending to an existing file the function:
      1. Splits the new *content* into import lines and body lines.
      2. Reads the existing file and splits it the same way.
      3. Merges imports: new import lines that already exist in the file are
         dropped (exact-match after stripping whitespace).
      4. Writes back: merged imports + existing body + separator + new body.
    
    This prevents duplicate ``import`` / ``from … import`` / ``numerals``
    statements that would cause Acorn compiler errors when multiple entries
    from the same header are written to the same file.
    
    Returns:
        tuple[int, int | None]: (start_line_number, original_file_size)
        - start_line_number: The line number where the new *body* content
          starts (import lines inserted at the top are not counted here so
          that the caller can record the position of the theorem/definition).
        - original_file_size: Size of file before modification, or None if
          the file didn't exist.  Used for rollback via ``_rollback_file_write``.
    """
    if not relative_path:
        return None, None

    # Fix: Clients (translator.py, import_acornlib.py) send paths relative to
    # project root (e.g., "acornlib/src/Analysis-I/foo.ac").
    # Strip the prefix to avoid doubling.
    clean_rel_path = relative_path.replace("\\", "/")
    if clean_rel_path.startswith("acornlib/src/"):
        relative_path = clean_rel_path[len("acornlib/src/"):]

    full_path = ACORNLIB_SRC / relative_path

    # Ensure directory exists
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Split incoming content
    new_imports, new_body = _split_imports_body(content)

    original_size = None

    if full_path.exists() and full_path.stat().st_size > 0:
        original_size = full_path.stat().st_size

        # Read and split existing file
        existing_imports, existing_body = _read_file_sections(full_path)

        # Deduplicate imports: keep existing order, append only truly new ones
        existing_import_set = {line.strip() for line in existing_imports
                               if line.strip()}
        merged_imports = list(existing_imports)
        for imp in new_imports:
            if imp.strip() and imp.strip() not in existing_import_set:
                merged_imports.append(imp)
                existing_import_set.add(imp.strip())

        # Build final file content
        parts: list[str] = []

        # 1. Merged imports
        if merged_imports:
            parts.append("\n".join(merged_imports))

        # 2. Existing body
        if existing_body:
            parts.append("\n".join(existing_body))

        # 3. New body (separated by blank line)
        if new_body:
            parts.append("\n".join(new_body))

        final_content = "\n\n".join(p for p in parts if p) + "\n"

        # Calculate start line for the new body
        # = lines in (merged imports) + lines in (existing body) + 2 (blank separator)
        lines_before = 0
        if merged_imports:
            lines_before += len(merged_imports)
        if existing_body:
            lines_before += 1  # blank separator between imports and existing body
            lines_before += len(existing_body)
        # +2 for the blank separator line before new body
        start_line = lines_before + 2 if lines_before > 0 else 1

        # Rewrite the entire file
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(final_content)
    else:
        # New file – just write everything as-is
        if full_path.exists():
            original_size = 0
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        start_line = 1

    return start_line, original_size


def _rollback_file_write(relative_path: str, original_size: int | None) -> None:
    """Rollback a file write operation.
    
    Args:
        relative_path: Path to the file relative to acornlib/src
        original_size: Size of the file before the write operation. 
                       None implies the file did not exist.
    """
    if not relative_path:
        return

    # Fix: Strip prefix (same as _append_to_file)
    clean_rel_path = relative_path.replace("\\", "/")
    if clean_rel_path.startswith("acornlib/src/"):
        relative_path = clean_rel_path[len("acornlib/src/"):]

    full_path = ACORNLIB_SRC / relative_path
    
    if not full_path.exists():
        return

    try:
        if original_size is None:
            # File didn't exist before, so delete it
            full_path.unlink()
        else:
            # File existed, truncate to original size
            with open(full_path, "a", encoding="utf-8") as f:
                f.truncate(original_size)
    except Exception as e:
        # Log error but don't crash, rollback is best-effort
        print(f"Error during file rollback for {relative_path}: {e}")




def _connect() -> sqlite3.Connection:
    """Create a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _run_in_executor(fn):
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(DB_EXECUTOR, fn)




def sanitize_file_path(path: str) -> str:
    """Sanitize file path for Acorn compatibility.
    
    Acorn requires filenames to be lowercase and without spaces/hyphens/#/dots/().
    It does NOT support starting with a number.
    It does NOT support single quotes.
    
    This function:
    1. Converts to lowercase
    2. Removes single quotes and closing parentheses
    3. REPLACES spaces, hyphens, hashes, dots, opening parentheses, and other symbols
       with underscores ('_').
       Symbols: ~!@$%^&+?<>|{}[]=:;,
       (Preserving the final .ac extension)
    4. Strings leading non-alpha characters from filename (e.g. "1.1 Intro.ac" -> "intro.ac")
    5. Keeps slashes and underscores
    """
    if not path:
        return path
        
    import re
        
    # Convert to standard path format first
    clean_path = path.replace("\\", "/")
    
    # Lowercase
    clean_path = clean_path.lower()
    
    # Remove single quotes and closing parentheses (per user request)
    for char in ["'", ")"]:
        clean_path = clean_path.replace(char, "")
    
    # Check extension
    extension = ""
    if clean_path.endswith(".ac"):
        clean_path = clean_path[:-3]
        extension = ".ac"
        
    # Replace forbidden characters with underscores
    # Added '.' to the list as per user request (Acorn doesn't like dots in import names)
    # Added '(' to be replaced by '_'
    # Added extra symbols: ~!@$%^&+?<>|{}[]=:;,
    special_chars = [' ', '-', '#', '.', '(', '~', '!', '@', '$', '%', '^', '&', '+', '?', '<', '>', '|', '{', '}', '[', ']', '=', ':', ';', ',']
    
    for char in special_chars:
        clean_path = clean_path.replace(char, '_')
        
    # Handle filename vs directory logic
    # Path might be "dir/subdir/filename"
    parts = clean_path.split('/')
    filename = parts[-1]
    
    # Strip leading non-alpha characters from filename (new requirement)
    # Acorn imports cannot start with numbers/symbols
    # e.g. "1_1_intro" -> "intro"
    match = re.search(r'[a-z]', filename)
    if match:
        start_idx = match.start()
        clean_filename = filename[start_idx:]
    else:
        # If no letters found (e.g. "123"), keep as is (though it will fail import likely)
        clean_filename = filename
        
    parts[-1] = clean_filename
    clean_path = "/".join(parts)
        
    return clean_path + extension


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
    """Get an item by name.
    
    Searches across theorems, definitions, and items tables in that order.
    Returns the first match found, formatted as a unified item schema.
    """
    def _get():
        conn = _connect()
        try:
            # Try theorems first
            cursor = conn.execute("SELECT * FROM theorems WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                item = dict(row)
                # Map to unified schema
                return {
                    "id": item["id"],
                    "name": item["name"],
                    "kind": "theorem",
                    "source": item["raw"],
                    "uuid": None,
                    "identifier_name": None,
                    "file_path": item.get("file_path"),
                    "line_number": item.get("line_number"),
                    "created_at": item["created_at"],
                    # Preserve theorem-specific fields
                    "theorem_head": item.get("theorem_head"),
                    "proof": item.get("proof"),
                    "raw": item.get("raw")
                }
            
            # Try definitions
            cursor = conn.execute("SELECT * FROM definitions WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                item = dict(row)
                return {
                    "id": item["id"],
                    "name": item["name"],
                    "kind": item.get("kind", "definition"),
                    "source": item["definition"],
                    "uuid": None,
                    "identifier_name": None,
                    "file_path": item.get("file_path"),
                    "line_number": item.get("line_number"),
                    "created_at": item["created_at"],
                    # Preserve definition-specific field
                    "definition": item.get("definition")
                }
            
            # Try items table
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
    """Return total number of items (optionally filtered).
    
    Counts across unified view of theorems, definitions, and items tables.
    """
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
            
            # UNION ALL to create virtual view, then count
            union_query = f"""
                SELECT name, raw as source, 'theorem' as kind FROM theorems
                UNION ALL
                SELECT name, definition as source, COALESCE(kind, 'definition') as kind FROM definitions
                UNION ALL
                SELECT name, source, kind FROM items
            """
            
            cursor = conn.execute(f"SELECT COUNT(*) FROM ({union_query}){where_clause}", params)
            (count,) = cursor.fetchone()
            return count
        finally:
            conn.close()

    return await _run_in_executor(_count)


async def get_items(limit: int, offset: int = 0, query: Optional[str] = None, kind: Optional[str] = None) -> List[Dict]:
    """Return a slice of items ordered by recency.
    
    This creates a virtual unified view by performing UNION ALL across:
    - theorems table (mapped to items schema)
    - definitions table (mapped to items schema)  
    - items table (native schema)
    
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
            # Build WHERE clause components
            where_conditions = []
            params = []
            
            if query:
                # For union, we need to filter each subquery
                query_term = f"%{query}%"
                where_conditions.append("(name LIKE ? OR source LIKE ?)")
                params.extend([query_term, query_term])
            
            if kind:
                where_conditions.append("kind = ?")
                params.append(kind)
            
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # UNION ALL query combining all three tables
            # Map theorems: id, name, 'theorem' as kind, raw as source, NULL as uuid/identifier_name, file_path, line_number, created_at
            # Map definitions: id, name, kind (or 'definition'), definition as source, NULL as uuid/identifier_name, file_path, line_number, created_at
            # Map items: all fields as-is
            
            union_query = f"""
                SELECT 
                    id, name, 'theorem' as kind, raw as source, 
                    NULL as uuid, NULL as identifier_name,
                    file_path, line_number, created_at
                FROM theorems
                
                UNION ALL
                
                SELECT 
                    id, name, COALESCE(kind, 'definition') as kind, definition as source,
                    NULL as uuid, NULL as identifier_name,
                    file_path, line_number, created_at
                FROM definitions
                
                UNION ALL
                
                SELECT 
                    id, name, kind, source, uuid, identifier_name,
                    file_path, line_number, created_at
                FROM items
            """
            
            # Wrap in subquery to apply filters and ordering
            final_query = f"""
                SELECT * FROM ({union_query})
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            
            cursor = conn.execute(final_query, (*params, limit, offset))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    return await _run_in_executor(_list)



async def get_all_items() -> List[Dict]:
    """Get all items from the database.
    
    Returns unified view of all theorems, definitions, and items.
    
    WARNING: Performance Issue - Memory Bomb Risk
    -----------------------------------------------
    This function executes SELECT * without LIMIT, loading ALL data
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
            # UNION ALL across all three tables
            union_query = """
                SELECT 
                    id, name, 'theorem' as kind, raw as source,
                    NULL as uuid, NULL as identifier_name,
                    file_path, line_number, created_at
                FROM theorems
                
                UNION ALL
                
                SELECT 
                    id, name, COALESCE(kind, 'definition') as kind, definition as source,
                    NULL as uuid, NULL as identifier_name,
                    file_path, line_number, created_at
                FROM definitions
                
                UNION ALL
                
                SELECT 
                    id, name, kind, source, uuid, identifier_name,
                    file_path, line_number, created_at
                FROM items
                
                ORDER BY created_at DESC
            """
            cursor = conn.execute(union_query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    return await _run_in_executor(_list_all)


async def search_theorems(q: str, limit: int = 5) -> List[Dict]:
    """Search for theorems/axioms using TF-IDF, Jaccard, tree edit distance on Lark-parsed head AST token seq."""
    import re
    from collections import Counter, defaultdict
    from difflib import SequenceMatcher
    from pathlib import Path
    from lark import Lark, Tree, Token
    from typing import List, Dict, Any

    grammar_path = ROOT_DIR / "acorn_mcp" / "acorn" / "acorn.lark"
    lark_parser = Lark(grammar_path.read_text(), parser="lalr", propagate_positions=False)

    def flatten_tree(node: Any) -> List[str]:
        """Preorder token seq from Lark tree (labels + leaves)."""
        if isinstance(node, Token):
            return [node.value]
        seq = [node.data]
        for child in node.children:
            seq += flatten_tree(child)
        return seq

    def get_head_ast_seq(raw: str) -> List[str]:
        """Parse raw → theorem head expr tree → flatten token seq."""
        try:
            # CRITICAL FIX: raw field doesn't include 'theorem' keyword, so prepend it
            # to make it parseable by Lark grammar which expects 'theorem name(...) { ... }'
            if not raw.strip().startswith(('theorem ', 'axiom ')):
                # Extract function name from signature (before first paren or brace)
                match = re.match(r'([a-z_][a-z0-9_]*)', raw.strip())
                func_name = match.group(1) if match else 'unnamed'
                parseable_raw = f'theorem {raw}'
            else:
                parseable_raw = raw
            
            tree = lark_parser.parse(parseable_raw)
            for stmt in tree.children:
                if stmt.data == 'theorem_decl':
                    # Find head expr after first {
                    brace_count = 0
                    for i, child in enumerate(stmt.children):
                        if isinstance(child, Token) and child.value == '{':
                            brace_count += 1
                            if brace_count == 1:
                                head_tree = stmt.children[i+1] if i+1 < len(stmt.children) else None
                                if head_tree:
                                    seq = flatten_tree(head_tree)
                                    # Normalize generics/stop
                                    stop = {'theorem', 'axiom', 'let', 'define', 'if', 'else', 'match', 'forall', 'exists', 'and', 'or', 'not', 'implies', 'suc', 'self', 'other', 'pred', '{', '}', '(', ')', ':', '->', ',', 'true', 'false'}
                                    generics = re.findall(r'^[A-Z]$', ''.join(seq))
                                    gen_map = {g: f'#GEN{i+1}' for i, g in enumerate(set(generics))}
                                    norm_seq = []
                                    for t in seq:
                                        if t in gen_map:
                                            norm_seq.append(gen_map[t])
                                        elif t not in stop and re.match(r'^[a-z_][a-z0-9_]*$', t) and len(t) > 1:
                                            norm_seq.append(t.lower())
                                    return norm_seq
            return []
        except Exception as e:
            # Fallback regex words - extract from head/body
            # raw format: "func_name(...) { head_expr } by { proof }"
            head = re.search(r'\{([^}]*?)(?:\s+by\s*\{|$)', raw, re.DOTALL)
            head_text = head.group(1).strip() if head else raw
            words = re.findall(r'\b[a-z_][a-z0-9_]*\b', head_text.lower())
            stop = {'theorem', 'axiom', 'let', 'define', 'if', 'else', 'match', 'forall', 'exists', 'and', 'or', 'not', 'implies', 'suc', 'self', 'other', 'pred', 'nat'}
            return [w for w in words if w not in stop and len(w) > 1]


    def jaccard_sim(q_seq: List[str], doc_seq: List[str]) -> float:
        q_set = set(q_seq)
        doc_set = set(doc_seq)
        inter = q_set & doc_set
        union = q_set | doc_set
        return len(inter) / len(union) if union else 0.0

    def simple_tfidf_cosine(q_vec: Counter, doc_vec: Counter, df: Dict[str, int], N: int) -> float:
        q_tf = {w: freq * (1 + 1 / (df.get(w, 1) or 1)) for w, freq in q_vec.items()}
        doc_tf = {w: freq * (1 + 1 / (df.get(w, 1) or 1)) for w, freq in doc_vec.items()}
        dot = sum(q_tf.get(w, 0) * doc_tf.get(w, 0) for w in set(q_tf) | set(doc_tf))
        q_norm = sum(v**2 for v in q_tf.values()) ** 0.5
        doc_norm = sum(v**2 for v in doc_tf.values()) ** 0.5
        return dot / (q_norm * doc_norm) if q_norm and doc_norm else 0.0

    def _search():
        conn = _connect()
        try:
            cursor = conn.execute("SELECT * FROM theorems")
            candidates = [dict(row) for row in cursor.fetchall()]
            if not candidates:
                return []

            q_seq = get_head_ast_seq(q)
            q_words = q_seq  # seq is words already
            q_vec = Counter(q_seq)
            N = len(candidates)

            df = defaultdict(int)
            doc_seqs = []
            docs = []
            for doc in candidates:
                doc_seq = get_head_ast_seq(doc['raw'])
                docs.append(doc)
                doc_vec = Counter(doc_seq)
                doc_words_set = set(doc_seq)
                for w in doc_words_set:
                    df[w] += 1
                doc_seqs.append(doc_vec)

            scores = []
            for i, doc in enumerate(docs):
                doc_seq = get_head_ast_seq(doc['raw'])
                doc_vec = doc_seqs[i]

                jacc = jaccard_sim(q_seq, doc_seq)
                tfidf = simple_tfidf_cosine(q_vec, doc_vec, df, N)
                tree_edit = SequenceMatcher(None, ' '.join(q_seq), ' '.join(doc_seq)).ratio()

                avg_score = (jacc + tfidf + tree_edit) / 3
                scores.append((avg_score, doc))

            top = sorted(scores, reverse=True, key=lambda x: x[0])[:limit]
            return [{'score': score, **item} for score, item in top]
        finally:
            conn.close()
    return await _run_in_executor(_search)


# Legacy theorem/definition functions (kept for backward compatibility)

async def add_theorem(name: str, raw: str,
                      file_path: Optional[str] = None, line_number: Optional[int] = None,
                      persist_to_file: bool = True) -> Dict:
    """Add a new theorem to the database.
    
    This writes to the 'theorems' table and is the CORRECT way to store theorems
    for Formalizer integration. Data written here is queryable via /api/theorems.
    
    Args:
        name: Fully qualified theorem name (e.g., 'group.inverse_inverse')
        raw: Complete theorem source code including 'theorem' keyword, head, and proof
             Example: "theorem foo(x: Nat) { x = x } by { reflexivity }"
        file_path: Optional source file path
        line_number: Optional line number in source file
        persist_to_file: If True (default), writes/appends content to file_path.
                         Set to False when importing from existing files to prevent duplication.
    
    Returns:
        Dict containing the inserted theorem data
    
    The function automatically parses:
    - theorem_head: The head portion (function signature and statement)
    - proof: The proof block content (if present)
    - raw: Normalized form (removes 'theorem' keyword prefix for database storage)
    """
    import re
    
    def _parse_and_insert():
        # Capturing variables from outer scope. 
        # Since we might update line_number if writing to file, we use a local var for the INSERT.
        # But we can't easily modify the outer 'line_number' arg if it's immutable (int/None).
        # Use local variable 'insert_line_number'.
        insert_line_number = line_number
        original_size = None

        # Sanitize path if provided
        # This modification ensures all paths stored in DB and used for file creation
        # comply with Acorn's strict naming requirements (lowercase, no spaces/hyphens/#)
        sanitized_path = sanitize_file_path(file_path) if file_path else None

        # If file_path is provided and persistence is enabled, write to file first
        if sanitized_path and persist_to_file:
            insert_line_number, original_size = _append_to_file(sanitized_path, raw)

        conn = _connect()
        try:
            # Parse the raw source to extract components
            raw_stripped = raw.strip()
            
            # Extract theorem head
            # Pattern: (theorem|axiom) name(...) { head_expr } [by { proof }]
            # Goal: Extract everything from keyword to end of first brace block
            
            # Check if raw starts with theorem/axiom keyword
            has_keyword = raw_stripped.startswith(('theorem ', 'axiom '))
            
            # Remove keyword if present for normalized storage
            if has_keyword:
                # Find where the keyword ends
                keyword_match = re.match(r'^(theorem|axiom)\s+', raw_stripped)
                if keyword_match:
                    normalized_raw = raw_stripped[keyword_match.end():]
                else:
                    normalized_raw = raw_stripped
            else:
                normalized_raw = raw_stripped
            
            # Extract head: everything up to 'by {' or end of string
            # Head format: name(...) { statement }
            by_match = re.search(r'\s+by\s*\{', normalized_raw)
            
            if by_match:
                # Has proof
                head_end = by_match.start()
                theorem_head = normalized_raw[:head_end].strip()
                
                # Extract proof: content between 'by {' and final '}'
                proof_start = by_match.end()
                # Find matching closing brace
                brace_count = 1
                i = proof_start
                while i < len(normalized_raw) and brace_count > 0:
                    if normalized_raw[i] == '{':
                        brace_count += 1
                    elif normalized_raw[i] == '}':
                        brace_count -= 1
                    i += 1
                
                if brace_count == 0:
                    proof = normalized_raw[proof_start:i-1].strip()
                else:
                    # Unmatched braces, take everything after 'by {'
                    proof = normalized_raw[proof_start:].strip()
            else:
                # No proof (axiom or unproven theorem)
                theorem_head = normalized_raw.strip()
                proof = ""
            
            # Insert into database
            cursor = conn.execute(
                """INSERT INTO theorems (name, theorem_head, proof, raw, file_path, line_number)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, theorem_head, proof, normalized_raw, sanitized_path, insert_line_number)
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "theorem_head": theorem_head,
                "proof": proof,
                "raw": normalized_raw,
                "file_path": sanitized_path,
                "line_number": insert_line_number
            }
        except Exception as e:
            # Rollback file write if DB insert fails
            if sanitized_path and persist_to_file:
                _rollback_file_write(sanitized_path, original_size)
            
            if isinstance(e, sqlite3.IntegrityError):
                raise ValueError(f"Theorem with name '{name}' already exists") from e
            raise e
        finally:
            conn.close()

    return await _run_in_executor(_parse_and_insert)


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
                         file_path: Optional[str] = None, line_number: Optional[int] = None,
                         persist_to_file: bool = True) -> Dict:
    """Add a new definition to the database.
    
    This writes to the 'definitions' table and is the CORRECT way to store definitions
    for Formalizer integration. Data written here is queryable via /api/definitions.

    Args:
        persist_to_file: If True (default), writes/appends content to file_path.
                         Set to False when importing from existing files.
    """
    def _insert():
        # Use local var for line number to handle potential file writing update
        insert_line_number = line_number
        original_size = None
        
        # Sanitize path if provided
        sanitized_path = sanitize_file_path(file_path) if file_path else None

        # If file_path is provided and persistence is enabled, write to file
        if sanitized_path and persist_to_file:
            insert_line_number, original_size = _append_to_file(sanitized_path, definition)

        conn = _connect()
        try:
            cursor = conn.execute(
                """INSERT INTO definitions (name, definition, kind, file_path, line_number)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, definition, kind, sanitized_path, insert_line_number)
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "definition": definition,
                "kind": kind,
                "file_path": sanitized_path,
                "line_number": insert_line_number
            }
        except Exception as e:
            # Rollback file write if DB insert fails
            if sanitized_path and persist_to_file:
                _rollback_file_write(sanitized_path, original_size)
            
            if isinstance(e, sqlite3.IntegrityError):
                raise ValueError(f"Definition with name '{name}' already exists") from e
            raise e
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