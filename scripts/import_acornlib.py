"""Parse Acorn library files and import items into the MCP database.

This script scans `acornlib/src` for `.ac` files, extracts all items using
the Acorn parser module, and writes them into the MCP SQLite database.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List

from acorn_mcp.database import (
    init_database,
    add_item,
    add_theorem,
    add_definition,
)
from acorn_mcp.acorn import AcornParser
from acorn_mcp.acorn.ast import AcornItem

ROOT_DIR = Path(__file__).resolve().parents[1]
ACORNLIB_SRC = ROOT_DIR / "acornlib" / "src"


def parse_acornlib() -> List[AcornItem]:
    """Parse all Acorn library files and return items."""
    if not ACORNLIB_SRC.exists():
        raise SystemExit(f"acornlib source not found at {ACORNLIB_SRC}")

    parser = AcornParser(source_root=ACORNLIB_SRC)
    all_items: List[AcornItem] = []

    for path in sorted(ACORNLIB_SRC.rglob("*.ac")):
        try:
            items, imports = parser.parse_file(path)
            all_items.extend(items)
        except Exception as e:
            print(f"[error] Failed to parse {path}: {e}", file=sys.stderr)

    return all_items


async def import_items(items: List[AcornItem], dry_run: bool) -> None:
    """Import parsed items into the database."""
    await init_database()

    # Get module name for each item
    def get_module(item: AcornItem) -> str:
        rel = item.location.file.relative_to(ACORNLIB_SRC).with_suffix("")
        return ".".join(rel.parts)

    if dry_run:
        print(f"[dry-run] Parsed {len(items)} items.")
        # Count by type
        by_kind = {}
        for item in items:
            by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
        print("Breakdown by kind:")
        for kind, count in sorted(by_kind.items()):
            print(f"  {kind}: {count}")
        return

    # Import all items into unified table
    print("=== Importing items ===")
    added = skipped = failed = 0
    failed_details = []

    for item in items:
        try:
            # Determine module name to ensure uniqueness
            try:
                module_name = get_module(item)
            except Exception:
                module_name = "unknown"

            # Enforce qualified names for EVERYTHING in theorems/definitions tables
            # to prevent 'UNIQUE constraint failed' errors.
            # Example: "inverse_inverse" -> "group.inverse_inverse"
            # Example: "List.map" -> "collections.list.List.map"
            if module_name and module_name != ".":
                if item.kind in ('attributes_method', 'attributes_constant', 'typeclass_method', 'typeclass_field', 'typeclass_axiom'):
                    # These already have "Type.member" name from parser
                    item.name = f"{module_name}.{item.name}"
                elif '.' not in item.name:
                    # Simple names get module prefix
                    item.name = f"{module_name}.{item.name}"
                else:
                    # Already has dot but not one of the special member kinds?
                    # Safer to prepend module anyway if it doesn't look like it includes module.
                    # But parser usually gives simple names or Type.member.
                    # Let's simple prepend module to ensure global uniqueness.
                    # Check if already starts with module to avoid double prefixing (unlikely with this logic)
                    if not item.name.startswith(module_name + "."):
                        item.name = f"{module_name}.{item.name}"

            # Route items to specific tables based on kind
            if item.kind in ('theorem', 'axiom', 'typeclass_axiom'):
                # Reconstruct raw source with theorem keyword for parsing
                # The parser stores raw without keyword, but add_theorem expects it with keyword
                raw_with_keyword = f"{item.kind} {getattr(item, 'raw', item.source)}"
                
                await add_theorem(
                    name=item.name,
                    raw=raw_with_keyword,
                    file_path=str(item.location.file.relative_to(ROOT_DIR)),
                    line_number=item.location.line
                )
            elif item.kind in ('define', 'definition', 'structure', 'inductive', 'typeclass', 
                             'typeclass_method', 'typeclass_field', 
                             'attributes_method', 'attributes_constant', 'instance'):
                await add_definition(
                    name=item.name,
                    definition=item.source,
                    kind=item.kind,
                    file_path=str(item.location.file.relative_to(ROOT_DIR)),
                    line_number=item.location.line
                )
            else:
                # Fallback for anything else
                await add_item(
                    name=item.name,
                    kind=item.kind,
                    source=item.source,
                    uuid=item.uuid,
                    identifier_name=item.identifier_name,
                    file_path=str(item.location.file.relative_to(ROOT_DIR)),
                    line_number=item.location.line
                )
            added += 1
        except ValueError as e:
            skipped += 1
            if "already exists" in str(e):
                failed_details.append(f"  Duplicate: {item.name} ({item.location.file.name}:{item.location.line}) [kind={item.kind}]")
            else:
                failed_details.append(f"  ValueError: {item.name} - {e}")
        except Exception as exc:
            failed += 1
            failed_details.append(f"  ERROR: {item.name} ({item.location.file.name}:{item.location.line}) [kind={item.kind}]: {exc}")

    print(f"Items: added {added}, skipped {skipped}, failed {failed}")
    if failed_details and (skipped > 0 or failed > 0):
        print("\nSkipped/Failed details (showing first 10):")
        for detail in failed_details[:10]:
            print(detail)

    print(f"\n=== Summary ===")
    print(f"Total items: {added} added, {skipped} skipped, {failed} failed")


def main(argv: List[str] | None = None) -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Import Acorn library items into the MCP database.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report counts without writing to the database.",
    )
    args = parser.parse_args(argv)

    items = parse_acornlib()
    asyncio.run(import_items(items, args.dry_run))


if __name__ == "__main__":
    main()
