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
    get_all_definitions
)
from acorn_mcp.syntax_checker import load_syntax_reference, check_syntax

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
                        "description": "Name of the theorem"
                    },
                    "theorem_head": {
                        "type": "string",
                        "description": "Statement of the theorem"
                    },
                    "proof": {
                        "type": "string",
                        "description": "Proof of the theorem"
                    }
                },
                "required": ["name", "theorem_head", "proof"]
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
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from the LLM."""
    try:
        if name == "add_theorem":
            result = await add_theorem(
                arguments["name"],
                arguments["theorem_head"],
                arguments["proof"]
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
        
        elif name == "add_definition":
            result = await add_definition(
                arguments["name"],
                arguments["definition"]
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
