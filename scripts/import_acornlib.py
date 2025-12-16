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
from typing import Iterable, List, Optional, Tuple, Set

from acorn_mcp.database import (
    init_database,
    add_theorem,
    add_definition,
    add_dependency,
)
from acorn_mcp.type_inference import (
    extract_theorem_dependencies,
    extract_definition_dependencies,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
ACORNLIB_SRC = ROOT_DIR / "acornlib" / "src"


@dataclass
class ParsedTheorem:
    kind: str  # "theorem" or "axiom"
    name: str
    head: str  # includes free variables (theorem header + head block)
    proof: str
    raw: str  # from "theorem/axiom" through the end of the proof block (if present)
    file: Path
    line: int


@dataclass
class ParsedDefinition:
    kind: str  # "define", "inductive", "structure", "typeclass", "attributes"
    name: str
    body: str  # stored text (header + block)
    file: Path
    line: int
    target_type: Optional[str] = None  # For attributes blocks, the type they apply to


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

    Returns (content_without_outer_braces, end_line, end_col_after_closing_brace_in_line).
    """
    brace = 1
    collected: List[str] = []
    initial_start_col = start_col
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
                    closing_col = (initial_start_col if idx == start_line else 0) + j
                    return "\n".join(collected).strip(), idx, closing_col + 1
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


def _extract_identifiers(text: str) -> set[str]:
    """Extract potential identifiers from Acorn code text.

    This extracts type names and module-qualified identifiers while filtering
    out Acorn keywords and common noise.
    """
    # Acorn keywords and common non-identifier words to filter out
    keywords = {
        'If', 'Then', 'Else', 'Match', 'Case', 'Let', 'Define', 'Theorem',
        'Axiom', 'By', 'Proof', 'Import', 'From', 'As', 'Type', 'Struct',
        'Inductive', 'Typeclass', 'Attributes', 'True', 'False', 'And', 'Or',
        'Not', 'Forall', 'Exists', 'Function', 'Return', 'For', 'While',
        'Break', 'Continue', 'Try', 'Catch', 'Finally', 'Throw', 'Class',
        'Interface', 'Enum', 'Public', 'Private', 'Protected', 'Static',
        'Final', 'Abstract', 'Override', 'Virtual', 'Const', 'Var', 'Val',
        'Implies', 'Iff'
    }

    # Match patterns like: TypeName, Module.name, Module.SubModule.name
    # Must start with capital letter for type/module, or be a qualified name
    pattern = r'\b[A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\b'
    matches = re.findall(pattern, text)

    # Filter out keywords and single-letter identifiers
    filtered = set()
    for match in matches:
        # Get the first component (before any dots)
        first_part = match.split('.')[0]

        # Skip if it's a keyword or single letter
        if first_part not in keywords and len(first_part) > 1:
            filtered.add(match)

    return filtered


def _is_comment_or_blank(line: str) -> bool:
    stripped = line.strip()
    return stripped == "" or stripped.startswith("//")


def _slice_span(lines: List[str], start_line: int, start_col: int, end_line: int, end_col: int) -> str:
    """Extract text across lines[start_line: end_line] using half-open cols."""
    if start_line == end_line:
        return lines[start_line][start_col:end_col]
    parts = [lines[start_line][start_col:]]
    for idx in range(start_line + 1, end_line):
        parts.append(lines[idx])
    parts.append(lines[end_line][:end_col])
    return "\n".join(parts)


def _dedent_block(text: str) -> str:
    """Remove common leading whitespace from all lines in a text block.

    Similar to textwrap.dedent but preserves the first line.
    """
    lines = text.split('\n')
    if not lines:
        return text

    # Find minimum indentation (ignoring empty lines)
    min_indent = float('inf')
    for line in lines:
        if line.strip():  # Non-empty line
            leading_spaces = len(line) - len(line.lstrip())
            min_indent = min(min_indent, leading_spaces)

    if min_indent == float('inf') or min_indent == 0:
        return text

    # Remove the common indentation from all lines
    dedented_lines = []
    for line in lines:
        if line.strip():  # Non-empty line
            dedented_lines.append(line[min_indent:])
        else:  # Empty line
            dedented_lines.append(line)

    return '\n'.join(dedented_lines)


def parse_acorn_file(path: Path) -> Tuple[List[ParsedTheorem], List[ParsedDefinition]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    theorems: List[ParsedTheorem] = []
    definitions: List[ParsedDefinition] = []
    module = _module_name(path)

    # Track imports at the file level
    file_imports: Set[str] = set()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Parse import statements (e.g., "from nat import Nat")
        if stripped.startswith("from ") or stripped.startswith("import "):
            # Extract module names from import
            import_match = re.match(r"(?:from\s+([A-Za-z_][A-Za-z0-9_/.]*)\s+)?import\s+([A-Za-z_][A-Za-z0-9_,\s]*)", stripped)
            if import_match:
                module_path = import_match.group(1)
                imported_items = import_match.group(2)
                if module_path:
                    file_imports.add(module_path)
                # Add individual imported items
                for item in imported_items.split(','):
                    item = item.strip()
                    if item:
                        file_imports.add(item)
            i += 1
            continue

        # Theorem/Axiom parsing
        if stripped.startswith("theorem") or stripped.startswith("axiom"):
            start_idx = i
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

            kw_col = line.find(kw)
            _, head_end_line, head_end_col = _capture_block(lines, i, brace_pos + 1)
            # head_text should be from keyword through the closing } of the head block
            head_text = _slice_span(lines, i, kw_col, head_end_line, head_end_col).strip()

            def _maybe_capture_proof(line_idx: int, col_start: int) -> Optional[Tuple[str, int, int, int]]:
                """Returns (proof_content, by_line, by_col, proof_end_line, proof_end_col) or None."""
                remainder = lines[line_idx][col_start:] if col_start < len(lines[line_idx]) else ""
                by_pos = _find_keyword(remainder, "by")
                if by_pos is None:
                    return None
                by_absolute_col = col_start + by_pos
                brace_after_by = remainder.find("{", by_pos)
                if brace_after_by == -1:
                    return None
                proof_content, proof_end_line, proof_end_col = _capture_block(
                    lines, line_idx, col_start + brace_after_by + 1
                )
                return proof_content, line_idx, by_absolute_col, proof_end_line, proof_end_col

            proof = ""
            raw_end_line = head_end_line
            raw_end_col = head_end_col
            proof_result: Optional[Tuple[str, int, int, int, int]] = None
            if kw == "theorem":  # only theorems have proofs
                # First, check on the same line as the head closing brace.
                proof_result = _maybe_capture_proof(head_end_line, head_end_col)
                if proof_result is None:
                    # Then, check the next non-blank, non-comment line.
                    probe_line = head_end_line + 1
                    while probe_line < len(lines) and _is_comment_or_blank(lines[probe_line]):
                        probe_line += 1
                    if probe_line < len(lines):
                        proof_result = _maybe_capture_proof(probe_line, 0)

            if proof_result:
                proof_content, _, _, proof_end_line, proof_end_col = proof_result
                proof = _dedent_block(proof_content.strip())
                raw_end_line = proof_end_line
                raw_end_col = proof_end_col
                i = proof_end_line + 1
            else:
                i = head_end_line + 1

            raw_text = _slice_span(lines, start_idx, kw_col, raw_end_line, raw_end_col).strip()
            theorems.append(
                ParsedTheorem(
                    kind=kw,
                    name=name,
                    head=head_text,
                    proof=proof,
                    raw=raw_text,
                    file=path,
                    line=start_line_no,
                )
            )
            continue

        # Definition parsing (define, inductive, structure, typeclass, attributes)
        def_kw = None
        for candidate in ("attributes", "define", "inductive", "structure", "typeclass"):
            if stripped.startswith(candidate):
                def_kw = candidate
                break

        if def_kw:
            # Extract name right after the keyword
            start_line_no = i + 1
            raw_name = None
            target_type = None  # For attributes blocks

            if def_kw == "attributes":
                # attributes blocks: "attributes TypeName {"
                # Generate a unique name by appending line number to avoid conflicts
                m = re.match(r"attributes\s+([A-Za-z_][A-Za-z0-9_<>\[\],\s]*?)\s*\{", stripped)
                if m:
                    target_type = m.group(1).strip()
                    raw_name = f"{target_type}_attributes_{start_line_no}"
            else:
                # Other definition types: "keyword name(...) {"
                m = re.match(rf"{def_kw}\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
                if m:
                    raw_name = m.group(1)

            name = f"{module}.{raw_name}" if raw_name else f"{module}.{def_kw}_{start_line_no}"

            brace_pos = line.find("{")
            if brace_pos == -1:
                i += 1
                continue

            try:
                body, def_end_line, _ = _capture_block(lines, i, brace_pos + 1)
                header = line[:brace_pos].strip()
                rendered = f"{header} {{\n{body}\n}}"
                definitions.append(
                    ParsedDefinition(
                        kind=def_kw,
                        name=name,
                        body=rendered.strip(),
                        file=path,
                        line=start_line_no,
                        target_type=target_type
                    )
                )
                i = def_end_line + 1
            except ValueError as e:
                print(f"[warn] Failed to parse {def_kw} at {path}:{start_line_no}: {e}", file=sys.stderr)
                i += 1
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

    thm_added = thm_skipped = thm_failed = 0
    def_added = def_skipped = def_failed = 0
    dep_added = 0

    if dry_run:
        print(f"[dry-run] Parsed {len(theorems)} theorems, {len(definitions)} definitions.")
        for thm in theorems[:5]:
            print(f"  Theorem: {thm.name} ({thm.file}:{thm.line})")
        for dfn in definitions[:5]:
            print(f"  Definition: {dfn.name} ({dfn.file}:{dfn.line}) [kind={dfn.kind}]")
        return

    # First pass: add all items
    print("=== Importing theorems ===")
    for thm in theorems:
        try:
            await add_theorem(
                thm.name, thm.head, thm.proof, thm.raw,
                file_path=str(thm.file.relative_to(ROOT_DIR)),
                line_number=thm.line
            )
            thm_added += 1
        except ValueError as e:
            thm_skipped += 1
            if "already exists" not in str(e):
                print(f"[skip] {thm.name}: {e}")
        except Exception as exc:
            thm_failed += 1
            print(f"[ERROR] Failed to add theorem {thm.name} ({thm.file}:{thm.line}): {exc}", file=sys.stderr)

    print(f"Theorems: added {thm_added}, skipped {thm_skipped}, failed {thm_failed}")

    print("\n=== Importing definitions ===")
    failed_details = []
    for dfn in definitions:
        try:
            await add_definition(
                dfn.name, dfn.body,
                kind=dfn.kind,
                file_path=str(dfn.file.relative_to(ROOT_DIR)),
                line_number=dfn.line
            )
            def_added += 1
        except ValueError as e:
            def_skipped += 1
            if "already exists" in str(e):
                failed_details.append(f"  Duplicate: {dfn.name} ({dfn.file.name}:{dfn.line}) [kind={dfn.kind}]")
            else:
                failed_details.append(f"  ValueError: {dfn.name} - {e}")
        except Exception as exc:
            def_failed += 1
            failed_details.append(f"  ERROR: {dfn.name} ({dfn.file.name}:{dfn.line}) [kind={dfn.kind}]: {exc}")

    print(f"Definitions: added {def_added}, skipped {def_skipped}, failed {def_failed}")
    if failed_details and (def_skipped > 0 or def_failed > 0):
        print("\nSkipped/Failed details (showing first 10):")
        for detail in failed_details[:10]:
            print(detail)

    # Second pass: extract and add dependencies
    print("\n=== Extracting dependencies ===")

    # Build a set of all known items (theorems + definitions) for validation
    all_item_names = set()
    for thm in theorems:
        all_item_names.add(thm.name)
        # Also add just the last component (e.g., "Real" from "real.Real")
        if '.' in thm.name:
            all_item_names.add(thm.name.split('.')[-1])

    for dfn in definitions:
        all_item_names.add(dfn.name)
        if '.' in dfn.name:
            all_item_names.add(dfn.name.split('.')[-1])

    for thm in theorems:
        # Use type inference to extract dependencies with operator resolution
        try:
            dependencies = extract_theorem_dependencies(thm.name, thm.head, thm.proof, thm.raw)

            for dep in dependencies:
                if dep and dep != thm.name:
                    # Check if it's a known item or a qualified name
                    base_name = dep.split('.')[0] if '.' in dep else dep
                    if dep in all_item_names or base_name in all_item_names or '.' in dep:
                        try:
                            await add_dependency(thm.name, "theorem", dep, "uses")
                            dep_added += 1
                        except Exception:
                            pass  # Silently skip duplicate dependencies
        except Exception as e:
            # Don't let dependency extraction failures stop the import
            print(f"[warn] Failed to extract dependencies for {thm.name}: {e}", file=sys.stderr)

    for dfn in definitions:
        # Use type inference to extract dependencies
        try:
            dependencies = extract_definition_dependencies(dfn.name, dfn.body)

            for dep in dependencies:
                if dep and dep != dfn.name:
                    base_name = dep.split('.')[0] if '.' in dep else dep
                    if dep in all_item_names or base_name in all_item_names or '.' in dep:
                        try:
                            await add_dependency(dfn.name, "definition", dep, "uses")
                            dep_added += 1
                        except Exception:
                            pass  # Silently skip duplicate dependencies
        except Exception as e:
            print(f"[warn] Failed to extract dependencies for {dfn.name}: {e}", file=sys.stderr)

    print(f"Dependencies: added {dep_added} relationships")
    print(f"\n=== Summary ===")
    print(f"Total theorems: {thm_added} added, {thm_skipped} skipped, {thm_failed} failed")
    print(f"Total definitions: {def_added} added, {def_skipped} skipped, {def_failed} failed")
    print(f"Total dependencies: {dep_added}")


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
