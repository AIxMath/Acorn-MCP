"""FastAPI backend for Acorn MCP frontend."""
from contextlib import asynccontextmanager
from math import ceil
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from acorn_mcp.database import (
    MAX_PAGE_SIZE,
    init_database,
    add_item,
    get_item,
    get_item_by_uuid,
    get_item_count,
    get_items,
    add_theorem,
    get_theorem,
    get_theorem_count,
    get_theorems,
    add_definition,
    get_definition,
    get_definition_count,
    get_definitions,
    get_dependencies,
)
from acorn_mcp.export import export_ordered, export_acorn_file

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
    raw: str


class DefinitionCreate(BaseModel):
    name: str
    definition: str


class ItemCreate(BaseModel):
    name: str
    kind: str
    source: str


@app.get("/")
async def read_root():
    """Serve the main HTML page."""
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="Frontend assets not found")
    return FileResponse(str(INDEX_FILE))


@app.get("/theorems.html")
async def read_theorems_page():
    """Serve the theorems page."""
    theorems_file = STATIC_DIR / "theorems.html"
    if not theorems_file.exists():
        raise HTTPException(status_code=404, detail="Theorems page not found")
    return FileResponse(str(theorems_file))


@app.get("/definitions.html")
async def read_definitions_page():
    """Serve the definitions page."""
    definitions_file = STATIC_DIR / "definitions.html"
    if not definitions_file.exists():
        raise HTTPException(status_code=404, detail="Definitions page not found")
    return FileResponse(str(definitions_file))


@app.get("/create.html")
async def read_create_page():
    """Serve the create page."""
    create_file = STATIC_DIR / "create.html"
    if not create_file.exists():
        raise HTTPException(status_code=404, detail="Create page not found")
    return FileResponse(str(create_file))


@app.get("/browse.html")
async def read_browse_page():
    """Serve the unified browse page."""
    browse_file = STATIC_DIR / "browse.html"
    if not browse_file.exists():
        raise HTTPException(status_code=404, detail="Browse page not found")
    return FileResponse(str(browse_file))


@app.get("/api/theorems")
async def list_theorems(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = Query(None, description="Optional search query")
):
    """Get paginated theorems."""
    total = await get_theorem_count(query=q)
    total_pages = max(1, ceil(total / page_size)) if total else 1
    safe_page = min(page, total_pages)
    offset = (safe_page - 1) * page_size
    theorems = await get_theorems(limit=page_size, offset=offset, query=q)
    return {
        "theorems": theorems,
        "total": total,
        "page": safe_page,
        "page_size": page_size,
        "pages": total_pages,
        "query": q
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
            theorem.proof,
            theorem.raw
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/definitions")
async def list_definitions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = Query(None, description="Optional search query")
):
    """Get paginated definitions."""
    total = await get_definition_count(query=q)
    total_pages = max(1, ceil(total / page_size)) if total else 1
    safe_page = min(page, total_pages)
    offset = (safe_page - 1) * page_size
    definitions = await get_definitions(limit=page_size, offset=offset, query=q)
    return {
        "definitions": definitions,
        "total": total,
        "page": safe_page,
        "page_size": page_size,
        "pages": total_pages,
        "query": q
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


@app.get("/api/export")
async def export_items():
    """Export all items in dependency order."""
    return await export_ordered()


@app.get("/api/export/acorn")
async def export_acorn():
    """Export all items as a single Acorn file."""
    content = await export_acorn_file()
    return PlainTextResponse(content, media_type="text/plain")


@app.get("/api/dependencies/{item_name}")
async def get_item_dependencies(item_name: str):
    """Get all dependencies for a specific item."""
    deps = await get_dependencies(item_name)
    return {
        "item": item_name,
        "dependencies": deps,
        "count": len(deps)
    }


# Unified items endpoints

@app.get("/api/items")
async def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = Query(None, description="Optional search query"),
    kind: str | None = Query(None, description="Filter by item kind")
):
    """Get paginated items from the unified items table."""
    total = await get_item_count(query=q, kind=kind)
    total_pages = max(1, ceil(total / page_size)) if total else 1
    safe_page = min(page, total_pages)
    offset = (safe_page - 1) * page_size
    items = await get_items(limit=page_size, offset=offset, query=q, kind=kind)
    return {
        "items": items,
        "total": total,
        "page": safe_page,
        "page_size": page_size,
        "pages": total_pages,
        "query": q,
        "kind": kind
    }


@app.get("/api/items/{name}")
async def read_item(name: str):
    """Get a specific item by name."""
    item = await get_item(name)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.get("/api/items/uuid/{uuid}")
async def read_item_by_uuid(uuid: str):
    """Get a specific item by UUID."""
    item = await get_item_by_uuid(uuid)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/api/items")
async def create_item(item: ItemCreate):
    """Create a new item."""
    try:
        result = await add_item(
            item.name,
            item.kind,
            item.source
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
