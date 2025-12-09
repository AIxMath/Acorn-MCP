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

## Usage

### Running the Web Interface

Start the FastAPI server:
```bash
python -m acorn_mcp.api_server
```

Then open your browser to `http://localhost:8000` to access the web interface.

### Running the MCP Server

The MCP server allows LLMs to interact with the theorem and definition databases:
```bash
python -m acorn_mcp.mcp_server
```

The MCP server communicates via stdio and can be integrated with LLM clients that support the Model Context Protocol.

### Importing the Acorn standard library into the database

Parse all `.ac` files in `acornlib/src` and insert the discovered theorems/definitions:
```bash
python -m scripts.import_acornlib
```
Add `--dry-run` to see counts without writing.

### Available MCP Tools

The MCP server provides the following tools for LLMs:

- `add_theorem`: Add a new theorem (requires: name, theorem_head, proof)
- `get_theorem`: Retrieve a theorem by name
- `list_theorems`: List all theorems
- `add_definition`: Add a new definition (requires: name, definition)
- `get_definition`: Retrieve a definition by name
- `list_definitions`: List all definitions
- `get_acorn_syntax`: Return the condensed Acorn syntax reference
- `check_acorn_syntax`: Validate a snippet of Acorn code and report issues

### API Endpoints

The FastAPI server provides the following endpoints:

**Theorems:**
- `GET /api/theorems`: List all theorems
- `GET /api/theorems/{name}`: Get a specific theorem
- `POST /api/theorems`: Create a new theorem

**Definitions:**
- `GET /api/definitions`: List all definitions
- `GET /api/definitions/{name}`: Get a specific definition
- `POST /api/definitions`: Create a new definition

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
