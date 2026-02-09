# Acorn-MCP

A Model Context Protocol (MCP) server for managing mathematical theorems and definitions with an intuitive web interface.

## Layout
- `acorn_mcp/`: Python package for the MCP server, API server, database access, and syntax checker
- `static/`: Frontend assets served by the API server
- `docs/`: Acorn background and condensed syntax reference
- `tests/`: Simple database smoke test
- `acornlib/`: Checked-out Acorn standard library (not modified by this server)

## Features

- **Theorem Database**: Store and manage theorems with name, statement, and proof
- **Definition Database**: Store and manage mathematical definitions
- **MCP Server**: Provides tools for LLM to interact with the knowledge base
- **Web Interface**: Beautiful, responsive UI to view and add theorems and definitions
- **RESTful API**: FastAPI-powered backend for frontend-backend communication

## Architecture

The project consists of three main components:

1. **Database Layer** (`acorn_mcp/database.py`): SQLite database with async operations for theorems and definitions
2. **MCP Server** (`acorn_mcp/mcp_server.py`): Model Context Protocol server that LLMs can use to access the knowledge base
3. **API Server** (`acorn_mcp/api_server.py`): FastAPI backend providing REST endpoints for the web interface
4. **Frontend** (`static/index.html`): Interactive web interface for viewing and managing content
5. **Syntax Checker** (`acorn_mcp/syntax_checker.py`): Lightweight syntax validation for Acorn code
6. **Code Verifier** (`acorn_mcp/code_verifier.py`): Acorn compiler integration for logical verification

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AIxMath/Acorn-MCP.git
cd Acorn-MCP
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## End-to-end Setup

### 1. Install Dependencies

Optionally use a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Download Acorn Standard Library

The `acornlib` directory contains the Acorn standard library (theorems, definitions, and basic types):
```bash
# Clone the acornlib repository
git clone https://github.com/acornprover/acornlib.git
```

> **Note**: Place `acornlib` in the same directory as this project, or set the `ACORN_LIB_PATH` environment variable to point to it.

### 3. Install Acorn Compiler

The code verification feature requires the Acorn compiler. Install it using the provided script:
```bash
bash scripts/install-acorn.sh
```

This will:
- Download the latest Acorn binary for Linux
- Install it to `~/.local/bin/acorn`
- Verify the installation

> **Important**: Ensure `~/.local/bin` is in your `PATH`. Add this to your `~/.bashrc` or `~/.zshrc`:
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> ```

Verify installation:
```bash
acorn --version
```

### 4. Pre-populate Database (Optional)

Import theorems and definitions from `acornlib`:
```bash
python -m scripts.import_acornlib --dry-run   # Preview what will be imported
python -m scripts.import_acornlib             # Write to acorn_mcp.db
```

This parses all `.ac` files in `acornlib/src` and imports:
- **Theorems**: `theorem` blocks (statement + proof) and `axiom` blocks
- **Definitions**: `define`, `inductive`, `structure`, and `typeclass` blocks

### 5. Start API Server

Start the FastAPI server (serves web UI at `/` and REST API at `/api/*`):
```bash
python -m acorn_mcp.api_server
```

The server will start on `http://localhost:8000`. Open your browser to:
- **Web Interface**: `http://localhost:8000` - Browse and add theorems/definitions
- **API Documentation**: `http://localhost:8000/docs` - Interactive API docs

### 6. Start MCP Server (Optional)

For LLM integration via Model Context Protocol, start the MCP server in a separate terminal:
```bash
python -m acorn_mcp.mcp_server
```

The MCP server communicates via stdio and exposes tools for LLM clients (see [Available MCP Tools](#available-mcp-tools) below).


### Available MCP Tools


The MCP server provides the following tools for LLMs:

- `add_theorem`: Add a new theorem (requires: name, theorem_head, proof, raw)
- `get_theorem`: Retrieve a theorem by name
- `list_theorems`: List all theorems
- `add_definition`: Add a new definition (requires: name, definition)
- `get_definition`: Retrieve a definition by name
- `list_definitions`: List all definitions
- `get_acorn_syntax`: Return the condensed Acorn syntax reference
- `check_acorn_syntax`: Validate a snippet of Acorn code and report issues
- `verify_acorn_code`: Verify Acorn code logic using the Acorn compiler

### Importer coverage

The `scripts/import_acornlib.py` parser imports:
- Theorems: `theorem` blocks (statement + optional `by` proof) and `axiom` blocks (treated as theorems with no proof).
- Definitions: `define`, `inductive`, `structure`, and `typeclass` blocks (stored with their headers and bodies). Inductive types are treated as definitions.

### API Endpoints

The FastAPI server provides the following endpoints:

**Theorems:**
- `GET /api/theorems`: List all theorems (pagination via `page`/`page_size`, filter with `q`)
- `GET /api/theorems/{name}`: Get a specific theorem
- `POST /api/theorems`: Create a new theorem

**Definitions:**
- `GET /api/definitions`: List all definitions (pagination via `page`/`page_size`, filter with `q`)
- `GET /api/definitions/{name}`: Get a specific definition
- `POST /api/definitions`: Create a new definition

**Code Validation:**
- `POST /api/syntax/check`: Check Acorn syntax
  - Request body: `{"source": "acorn code"}`
  - Response: `{"is_valid": bool, "errors": [...], "warnings": [...]}`
- `POST /api/code/verify`: Verify code with Acorn compiler
  - Request body: `{"source": "acorn code"}`
  - Response: `{"is_valid": bool, "errors": [...], "compiler_available": bool}`

## Database Schema

### Theorems Table
- `id`: Auto-incrementing primary key
- `name`: Unique theorem name
- `theorem_head`: The statement of the theorem
- `proof`: The proof of the theorem
- `created_at`: Timestamp of creation

### Definitions Table
- `id`: Auto-incrementing primary key
- `name`: Unique definition name
- `definition`: The definition text
- `created_at`: Timestamp of creation

## Example Usage

### Adding a Theorem via API
```bash
curl -X POST http://localhost:8000/api/theorems \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pythagorean Theorem",
    "theorem_head": "In a right triangle, the square of the hypotenuse equals the sum of squares of the other two sides",
    "proof": "Let a and b be the legs and c be the hypotenuse. Then a² + b² = c²"
  }'
```

### Adding a Definition via API
```bash
curl -X POST http://localhost:8000/api/definitions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Prime Number",
    "definition": "A natural number greater than 1 that has no positive divisors other than 1 and itself"
  }'
```

## Development

The project uses:
- **Python 3.7+**
- **FastAPI**: Modern web framework for building APIs
- **MCP (Model Context Protocol)**: For LLM integration
- **aiosqlite**: Async SQLite database operations
- **Uvicorn**: ASGI server

## License

See LICENSE file for details.
