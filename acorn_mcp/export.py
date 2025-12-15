"""Export all items in topological order."""
from typing import Dict, List, Set
from acorn_mcp.database import get_all_items_with_dependencies


def topological_sort(items: List[Dict], dependencies: List[Dict]) -> List[Dict]:
    """Sort items in topological order based on dependencies.

    Returns items ordered such that dependencies come before dependents.
    """
    # Build adjacency list and in-degree count
    adj_list: Dict[str, List[str]] = {}
    in_degree: Dict[str, int] = {}
    item_map: Dict[str, Dict] = {}

    # Initialize with all items
    for item in items:
        name = item["name"]
        adj_list[name] = []
        in_degree[name] = 0
        item_map[name] = item

    # Build dependency graph
    for dep in dependencies:
        source = dep["source_name"]
        target = dep["target_name"]

        # Only track dependencies where both source and target exist in our items
        if source in item_map and target in item_map:
            adj_list[target].append(source)  # target -> source (reversed for topological sort)
            in_degree[source] = in_degree.get(source, 0) + 1

    # Kahn's algorithm for topological sort
    queue = [name for name, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        # Sort to make output deterministic
        queue.sort()
        current = queue.pop(0)
        result.append(item_map[current])

        for neighbor in adj_list.get(current, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # If there are remaining items (cycles or disconnected), add them sorted
    remaining = [item for item in items if item["name"] not in [r["name"] for r in result]]
    remaining.sort(key=lambda x: x["name"])
    result.extend(remaining)

    return result


async def export_ordered() -> Dict:
    """Export all items in dependency order.

    Returns a dict with:
    - items: list of all items (theorems and definitions) in topological order
    - stats: statistics about the export
    """
    data = await get_all_items_with_dependencies()

    theorems = data["theorems"]
    definitions = data["definitions"]
    dependencies = data["dependencies"]

    # Combine all items
    all_items = []

    for thm in theorems:
        all_items.append({
            "name": thm["name"],
            "type": "theorem",
            "theorem_head": thm["theorem_head"],
            "proof": thm["proof"],
            "raw": thm["raw"],
            "file_path": thm.get("file_path"),
            "line_number": thm.get("line_number"),
            "created_at": thm["created_at"]
        })

    for dfn in definitions:
        all_items.append({
            "name": dfn["name"],
            "type": "definition",
            "kind": dfn.get("kind", "define"),
            "definition": dfn["definition"],
            "file_path": dfn.get("file_path"),
            "line_number": dfn.get("line_number"),
            "created_at": dfn["created_at"]
        })

    # Sort items topologically
    sorted_items = topological_sort(all_items, dependencies)

    return {
        "items": sorted_items,
        "stats": {
            "total_items": len(sorted_items),
            "theorems": len(theorems),
            "definitions": len(definitions),
            "dependencies": len(dependencies)
        }
    }


async def export_acorn_file() -> str:
    """Export all items as a single Acorn file in dependency order.

    Returns a string containing valid Acorn code.
    """
    data = await export_ordered()
    items = data["items"]

    lines = [
        "// Acorn MCP Export",
        "// Generated from database",
        f"// Total items: {data['stats']['total_items']}",
        "",
    ]

    for item in items:
        lines.append(f"// {item['type']}: {item['name']}")
        if item.get("file_path"):
            lines.append(f"// Source: {item['file_path']}:{item.get('line_number', '?')}")

        if item["type"] == "theorem":
            lines.append(item["raw"])
        else:  # definition
            lines.append(item["definition"])

        lines.append("")  # Empty line between items

    return "\n".join(lines)
