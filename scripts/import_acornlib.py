"""Parse Acorn library files and import items into the MCP database.

This script scans `acornlib/src` for `.ac` files, extracts theorems and
definitions (Acorn `define` blocks), and writes them into the MCP SQLite
database using the existing async helpers.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, List, Optional, Tuple

from acorn_mcp.database import (
    init_database,
    add_theorem,
    add_definition,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
ACORNLIB_SRC = ROOT_DIR / "acornlib" / "src"


@dataclass
class ParsedTheorem:
    kind: str  # "theorem" or "axiom"
    name: str
    head: str
    proof: str
    file: Path
    line: int


@dataclass
class ParsedDefinition:
    kind: str  # "define", "inductive", "structure", "typeclass"
    name: str
    body: str  # stored text (header + block)
    file: Path
    line: int


def _char_iter(segment: str) -> Iterable[Tuple[int, str]]:
    """Yield (index, char) while skipping everything after // on the same line."""
    i = 0
    while i < len(segment):
        if segment[i : i + 2] == "//":
            return
        yield i, segment[i]
        i += 1


def _capture_block(lines: List[str], start_line: int, start_col: int) -> Tuple[str, int, int]:
    """Capture text inside a {...} block starting at lines[start_line][start_col-1]=='{'.

    Returns (content_without_outer_braces, end_line, end_col_after_closing_brace).
    """
    brace = 1
    collected: List[str] = []
    for idx in range(start_line, len(lines)):
        line = lines[idx]
        segment = line[start_col:] if idx == start_line else line
        seg_for_scan = segment
        for j, ch in _char_iter(seg_for_scan):
            if ch == "{":
                brace += 1
            elif ch == "}":
                brace -= 1
                if brace == 0:
                    # Closing brace is at j; store content up to j (exclusive)
                    collected.append(segment[:j])
                    return "\n".join(collected).strip(), idx, j + 1 if idx == start_line else j + 1
        collected.append(segment)
        start_col = 0  # after first line, continue from col 0
    raise ValueError("Unclosed brace block encountered")


def _find_keyword(segment: str, keyword: str) -> Optional[int]:
    """Return index of keyword in segment before // comments, or None if absent."""
    for i, _ in _char_iter(segment):
        if segment.startswith(keyword, i):
            return i
    return None


def _module_name(path: Path) -> str:
    rel = path.relative_to(ACORNLIB_SRC).with_suffix("")
    return ".".join(rel.parts)


def parse_acorn_file(path: Path) -> Tuple[List[ParsedTheorem], List[ParsedDefinition]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    theorems: List[ParsedTheorem] = []
    definitions: List[ParsedDefinition] = []
    module = _module_name(path)

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Theorem/Axiom parsing
        if stripped.startswith("theorem") or stripped.startswith("axiom"):
            start_line_no = i + 1
            raw_name = None
            kw = "axiom" if stripped.startswith("axiom") else "theorem"
            m = re.match(rf"{kw}\s+([A-Za-z0-9_]+)", stripped)
            if m:
                raw_name = m.group(1)
            name = f"{module}.{raw_name}" if raw_name else f"{module}.{kw}_{start_line_no}"

            brace_pos = line.find("{")
            if brace_pos == -1:
                i += 1
                continue

            head, head_end_line, head_end_col = _capture_block(lines, i, brace_pos + 1)

            # Look for proof block starting with "by {"
            proof = ""
            search_line = head_end_line
            search_col = head_end_col
            proof_found = False
            if kw == "theorem":  # only theorems have proofs
                while search_line < len(lines) and not proof_found:
                    remainder = lines[search_line][search_col:] if search_col < len(lines[search_line]) else ""
                    by_pos = _find_keyword(remainder, "by")
                    if by_pos is not None:
                        brace_after_by = remainder.find("{", by_pos)
                        if brace_after_by != -1:
                            proof, proof_end_line, proof_end_col = _capture_block(
                                lines, search_line, search_col + brace_after_by + 1
                            )
                            i = proof_end_line + 1
                            proof_found = True
                            break
                    search_line += 1
                    search_col = 0

            if not proof_found:
                i = head_end_line + 1

            theorems.append(
                ParsedTheorem(
                    kind=kw,
                    name=name,
                    head=head.strip(),
                    proof=proof.strip(),
                    file=path,
                    line=start_line_no,
                )
            )
            continue

        # Definition parsing (define, inductive, structure, typeclass)
        def_kw = None
        for candidate in ("define", "inductive", "structure", "typeclass"):
            if stripped.startswith(candidate):
                def_kw = candidate
                break

        if def_kw:
            # Extract name right after the keyword
            start_line_no = i + 1
            raw_name = None
            m = re.match(rf"{def_kw}\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
            if m:
                raw_name = m.group(1)
            name = f"{module}.{raw_name}" if raw_name else f"{module}.{def_kw}_{start_line_no}"

            brace_pos = line.find("{")
            if brace_pos == -1:
                i += 1
                continue

            body, def_end_line, def_end_col = _capture_block(lines, i, brace_pos + 1)
            header = line[:brace_pos].strip()
            rendered = f"{header} {{\n{body}\n}}"
            definitions.append(
                ParsedDefinition(
                    kind=def_kw,
                    name=name,
                    body=rendered.strip(),
                    file=path,
                    line=start_line_no,
                )
            )
            i = def_end_line + 1
            continue

        i += 1

    return theorems, definitions


def parse_acornlib() -> Tuple[List[ParsedTheorem], List[ParsedDefinition]]:
    if not ACORNLIB_SRC.exists():
        raise SystemExit(f"acornlib source not found at {ACORNLIB_SRC}")
    theorems: List[ParsedTheorem] = []
    definitions: List[ParsedDefinition] = []
    for path in sorted(ACORNLIB_SRC.rglob("*.ac")):
        t, d = parse_acorn_file(path)
        theorems.extend(t)
        definitions.extend(d)
    return theorems, definitions


async def import_items(theorems: List[ParsedTheorem], definitions: List[ParsedDefinition], dry_run: bool) -> None:
    await init_database()

    thm_added = thm_skipped = 0
    def_added = def_skipped = 0

    if dry_run:
        print(f"[dry-run] Parsed {len(theorems)} theorems, {len(definitions)} definitions.")
        return

    for thm in theorems:
        try:
            await add_theorem(thm.name, thm.head, thm.proof)
            thm_added += 1
        except ValueError:
            thm_skipped += 1
        except Exception as exc:  # pragma: no cover - defensive
            thm_skipped += 1
            print(f"[warn] Failed to add theorem {thm.name} ({thm.file}:{thm.line}): {exc}", file=sys.stderr)

    for dfn in definitions:
        try:
            await add_definition(dfn.name, dfn.body)
            def_added += 1
        except ValueError:
            def_skipped += 1
        except Exception as exc:  # pragma: no cover - defensive
            def_skipped += 1
            print(f"[warn] Failed to add definition {dfn.name} ({dfn.file}:{dfn.line}): {exc}", file=sys.stderr)

    print(f"Theorems: added {thm_added}, skipped {thm_skipped}")
    print(f"Definitions: added {def_added}, skipped {def_skipped}")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Import Acorn library items into the MCP database.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report counts without writing to the database.",
    )
    args = parser.parse_args(argv)

    theorems, definitions = parse_acornlib()
    asyncio.run(import_items(theorems, definitions, args.dry_run))


if __name__ == "__main__":
    main()
