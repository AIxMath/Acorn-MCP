"""MCP Server for theorem and definition management."""
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from acorn_mcp.database import (
    init_database,
    add_theorem,
    get_theorem,
    get_all_theorems,
    add_definition,
    get_definition,
    get_all_definitions,
    search_theorems
)
from acorn_mcp.syntax_checker import load_syntax_reference, check_syntax
from acorn_mcp.code_verifier import check_verification

# Create MCP server instance
app = Server("acorn-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for the LLM."""
    return [
        Tool(
            name="add_theorem",
            description="Add a new theorem to the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Fully qualified theorem name (e.g., 'group.inverse_inverse')"
                    },
                    "raw": {
                        "type": "string",
                        "description": "Complete theorem source including 'theorem' keyword, head, and proof. Example: 'theorem foo(x: Nat) { x = x } by { reflexivity }'"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Optional file path relative to acornlib/src (e.g., 'nat/nat_base.ac') to write the theorem to."
                    }
                },
                "required": ["name", "raw"]
            }
        ),
        Tool(
            name="get_theorem",
            description="Get a theorem by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the theorem to retrieve"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="list_theorems",
            description="List all theorems in the database",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="search_theorems",
            description="Search for theorems using semantic search (TF-IDF, Jaccard, tree edit distance)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="add_definition",
            description="Add a new definition to the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the definition"
                    },
                    "definition": {
                        "type": "string",
                        "description": "The definition text"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Optional file path relative to acornlib/src (e.g., 'nat/nat_base.ac') to write the definition to."
                    }
                },
                "required": ["name", "definition"]
            }
        ),
        Tool(
            name="get_definition",
            description="Get a definition by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the definition to retrieve"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="list_definitions",
            description="List all definitions in the database",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_acorn_syntax",
            description="Return the condensed Acorn syntax reference",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="check_acorn_syntax",
            description="Check Acorn source text for common syntax issues",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Acorn code to validate"
                    }
                },
                "required": ["source"]
            }
        ),
        Tool(
            name="verify_acorn_code",
            description="Verify Acorn code logic using the Acorn compiler",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Acorn code to verify"
                    }
                },
                "required": ["source"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from the LLM."""
    try:
        if name == "add_theorem":
            result = await add_theorem(
                arguments["name"],
                arguments["raw"],
                file_path=arguments.get("file_path")
            )
            return [TextContent(
                type="text",
                text=f"Successfully added theorem: {json.dumps(result, indent=2)}"
            )]
        
        elif name == "get_theorem":
            result = await get_theorem(arguments["name"])
            if result:
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Theorem '{arguments['name']}' not found"
                )]
        
        elif name == "list_theorems":
            result = await get_all_theorems()
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "search_theorems":
            result = await search_theorems(arguments["query"])
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "add_definition":
            result = await add_definition(
                arguments["name"],
                arguments["definition"],
                file_path=arguments.get("file_path")
            )
            return [TextContent(
                type="text",
                text=f"Successfully added definition: {json.dumps(result, indent=2)}"
            )]
        
        elif name == "get_definition":
            result = await get_definition(arguments["name"])
            if result:
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Definition '{arguments['name']}' not found"
                )]
        
        elif name == "list_definitions":
            result = await get_all_definitions()
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "get_acorn_syntax":
            reference = load_syntax_reference()
            return [TextContent(
                type="text",
                text=reference
            )]
        
        elif name == "check_acorn_syntax":
            report = check_syntax(arguments["source"])
            pretty = json.dumps(report, indent=2)
            return [TextContent(
                type="text",
                text=pretty
            )]
        
        elif name == "verify_acorn_code":
            report = check_verification(arguments["source"])
            pretty = json.dumps(report, indent=2)
            return [TextContent(
                type="text",
                text=pretty
            )]
        
        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def main():
    """Run the MCP server."""
    # Initialize database
    await init_database()
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
