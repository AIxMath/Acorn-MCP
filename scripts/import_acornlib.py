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

    # Process item names based on kind
    for item in items:
        # Store the simple identifier name (last part after dot)
        identifier_name = item.name.split('.')[-1] if '.' in item.name else item.name
        item.identifier_name = identifier_name

        # For attributes members (methods/constants), keep the qualified name (Type.member)
        # For other items, use only the simple identifier
        if item.kind in ('attributes_method', 'attributes_constant'):
            # Keep qualified name like "List.range" or "Nat.range"
            # Name is already set correctly by parser
            pass
        else:
            # Store only the simple identifier in name column
            # Uniqueness is ensured by (file_path, name) composite constraint
            item.name = identifier_name

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
