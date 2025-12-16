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
    add_theorem,
    add_definition,
)
from acorn_mcp.acorn import AcornParser
from acorn_mcp.acorn.ast import AcornItem, Theorem, Definition, TypeClass

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

    # Build qualified names
    for item in items:
        module = get_module(item)
        # For typeclass-expanded items, name is already qualified
        if '.' not in item.name:
            item.name = f"{module}.{item.name}"

    thm_added = thm_skipped = thm_failed = 0
    def_added = def_skipped = def_failed = 0

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

    # First pass: add all items
    print("=== Importing theorems ===")
    for item in items:
        if isinstance(item, Theorem):
            try:
                await add_theorem(
                    item.name,
                    item.head,
                    item.proof,
                    item.raw,
                    file_path=str(item.location.file.relative_to(ROOT_DIR)),
                    line_number=item.location.line
                )
                thm_added += 1
            except ValueError as e:
                thm_skipped += 1
                if "already exists" not in str(e):
                    print(f"[skip] {item.name}: {e}")
            except Exception as exc:
                thm_failed += 1
                print(f"[ERROR] Failed to add theorem {item.name} ({item.location.file}:{item.location.line}): {exc}", file=sys.stderr)

    print(f"Theorems: added {thm_added}, skipped {thm_skipped}, failed {thm_failed}")

    print("\n=== Importing definitions ===")
    failed_details = []
    for item in items:
        if isinstance(item, Definition) or isinstance(item, TypeClass) or (not isinstance(item, Theorem)):
            # For non-theorems, store as definitions
            try:
                # Build body text based on item type
                if isinstance(item, Definition):
                    body = item.source
                else:
                    body = item.source

                await add_definition(
                    item.name,
                    body,
                    kind=item.kind,
                    file_path=str(item.location.file.relative_to(ROOT_DIR)),
                    line_number=item.location.line
                )
                def_added += 1
            except ValueError as e:
                def_skipped += 1
                if "already exists" in str(e):
                    failed_details.append(f"  Duplicate: {item.name} ({item.location.file.name}:{item.location.line}) [kind={item.kind}]")
                else:
                    failed_details.append(f"  ValueError: {item.name} - {e}")
            except Exception as exc:
                def_failed += 1
                failed_details.append(f"  ERROR: {item.name} ({item.location.file.name}:{item.location.line}) [kind={item.kind}]: {exc}")

    print(f"Definitions: added {def_added}, skipped {def_skipped}, failed {def_failed}")
    if failed_details and (def_skipped > 0 or def_failed > 0):
        print("\nSkipped/Failed details (showing first 10):")
        for detail in failed_details[:10]:
            print(detail)

    print(f"\n=== Summary ===")
    print(f"Total theorems: {thm_added} added, {thm_skipped} skipped, {thm_failed} failed")
    print(f"Total definitions: {def_added} added, {def_skipped} skipped, {def_failed} failed")


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
