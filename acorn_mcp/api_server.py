"""FastAPI backend for Acorn MCP frontend."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from acorn_mcp.database import (
    init_database,
    add_theorem,
    get_theorem,
    get_all_theorems,
    add_definition,
    get_definition,
    get_all_definitions
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
async def list_theorems():
    """Get all theorems."""
    theorems = await get_all_theorems()
    return {"theorems": theorems}


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
async def list_definitions():
    """Get all definitions."""
    definitions = await get_all_definitions()
    return {"definitions": definitions}


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
