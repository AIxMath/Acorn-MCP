# Repository Guidelines

## Project Structure & Module Organization
- `acorn_mcp/`: FastAPI API (`api_server.py`), MCP stdio server (`mcp_server.py`), SQLite helpers (`database.py`), and syntax utilities (`syntax_checker.py`).
- `static/`: Single-page UI served by the API root; keep assets referenced by `static/index.html`.
- `scripts/`: Maintenance helpers such as `scripts/import_acornlib.py` to bulk-import Acorn sources.
- `tests/`: Lightweight smoke checks (currently `tests/test_database.py`); expand here for new coverage.
- `acornlib/`: Checked-out Acorn standard library; treat as vendored input, not code you edit.
- Root files: `requirements.txt`, `LICENSE`, and the working database file `acorn_mcp.db`.

## Build, Test, and Development Commands
- Set up deps (optionally in a venv): `pip install -r requirements.txt`.
- Run API + UI locally: `python -m acorn_mcp.api_server` (serves `/` and JSON under `/api/*`).
- Run MCP server for tool access over stdio: `python -m acorn_mcp.mcp_server`.
- Import standard library into the DB: `python -m scripts.import_acornlib --dry-run` (preview) or without `--dry-run` to write.
- Smoke test the database flow: `python -m tests.test_database` (initializes `acorn_mcp.db`, inserts sample records, prints totals).

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and snake_case for functions/modules; PascalCase for classes and Pydantic models.
- Keep FastAPI endpoints and MCP tools asynchronous; prefer type hints for request/response shapes.
- Add concise docstrings at module/function level; keep public tool descriptions aligned across API and MCP definitions.
- Static assets: avoid bundlers; keep paths stable for `StaticFiles` mount and `index.html` references.

## Testing Guidelines
- Place new tests under `tests/` using `test_*.py` naming; keep them deterministic by starting from a clean `acorn_mcp.db` (delete or isolate the file before runs).
- Prefer async-friendly tests; if adopting pytest, mark async tests appropriately (`pytest-asyncio`) and keep fast feedback.
- When touching DB logic, cover both insert-path success and duplicate constraints (IntegrityError → ValueError).

## Commit & Pull Request Guidelines
- Use short, imperative commit messages (e.g., “Expand importer to cover axioms and structural declarations”).
- PRs should include: a clear summary of intent, commands/tests executed, and linked issues. Add screenshots/GIFs for UI changes.
- Keep changes scoped; avoid modifying `acornlib/` unless intentionally updating the vendored corpus.
