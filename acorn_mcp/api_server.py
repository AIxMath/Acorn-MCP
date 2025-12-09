"""FastAPI backend for Acorn MCP frontend."""
from contextlib import asynccontextmanager
from math import ceil
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from acorn_mcp.database import (
    MAX_PAGE_SIZE,
    init_database,
    add_theorem,
    get_theorem,
    get_theorem_count,
    get_theorems,
    add_definition,
    get_definition,
    get_definition_count,
    get_definitions
)

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_database()
    yield


app = FastAPI(title="Acorn MCP API", lifespan=lifespan)

# Pydantic models for request validation
class TheoremCreate(BaseModel):
    name: str
    theorem_head: str
    proof: str


class DefinitionCreate(BaseModel):
    name: str
    definition: str


@app.get("/")
async def read_root():
    """Serve the main HTML page."""
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="Frontend assets not found")
    return FileResponse(str(INDEX_FILE))


@app.get("/api/theorems")
async def list_theorems(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE)
):
    """Get paginated theorems."""
    total = await get_theorem_count()
    total_pages = max(1, ceil(total / page_size)) if total else 1
    safe_page = min(page, total_pages)
    offset = (safe_page - 1) * page_size
    theorems = await get_theorems(limit=page_size, offset=offset)
    return {
        "theorems": theorems,
        "total": total,
        "page": safe_page,
        "page_size": page_size,
        "pages": total_pages
    }


@app.get("/api/theorems/{name}")
async def read_theorem(name: str):
    """Get a specific theorem by name."""
    theorem = await get_theorem(name)
    if not theorem:
        raise HTTPException(status_code=404, detail="Theorem not found")
    return theorem


@app.post("/api/theorems")
async def create_theorem(theorem: TheoremCreate):
    """Create a new theorem."""
    try:
        result = await add_theorem(
            theorem.name,
            theorem.theorem_head,
            theorem.proof
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/definitions")
async def list_definitions(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE)
):
    """Get paginated definitions."""
    total = await get_definition_count()
    total_pages = max(1, ceil(total / page_size)) if total else 1
    safe_page = min(page, total_pages)
    offset = (safe_page - 1) * page_size
    definitions = await get_definitions(limit=page_size, offset=offset)
    return {
        "definitions": definitions,
        "total": total,
        "page": safe_page,
        "page_size": page_size,
        "pages": total_pages
    }


@app.get("/api/definitions/{name}")
async def read_definition(name: str):
    """Get a specific definition by name."""
    definition = await get_definition(name)
    if not definition:
        raise HTTPException(status_code=404, detail="Definition not found")
    return definition


@app.post("/api/definitions")
async def create_definition(definition: DefinitionCreate):
    """Create a new definition."""
    try:
        result = await add_definition(
            definition.name,
            definition.definition
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
