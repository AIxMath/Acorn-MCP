"""Lightweight syntax checker for the Acorn language.

The checker implements a small set of structural and naming validations
derived from `docs/acorn_background.md` and summarized in
`docs/acorn_syntax.md`. It is not a full parser, but it catches common
authoring mistakes early.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List, Tuple, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
SYNTAX_REFERENCE_PATH = ROOT_DIR / "docs" / "acorn_syntax.md"

def load_syntax_reference() -> str:
    """Return the Acorn syntax reference text."""
    return SYNTAX_REFERENCE_PATH.read_text(encoding="utf-8")


def _strip_comments_preserve_lines(text: str) -> Tuple[str, bool]:
    """Remove // and /* */ comments while preserving newlines for line numbers."""
    result: List[str] = []
    in_single = False
    in_multi = False
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_single:
            if ch == "\n":
                in_single = False
                result.append(ch)
            else:
                result.append(" ")
        elif in_multi:
            if ch == "*" and nxt == "/":
                in_multi = False
                result.extend("  ")
                i += 1
            elif ch == "\n":
                result.append("\n")
            else:
                result.append(" ")
        else:
            if ch == "/" and nxt == "/":
                in_single = True
                result.extend("  ")
                i += 1
            elif ch == "/" and nxt == "*":
                in_multi = True
                result.extend("  ")
                i += 1
            else:
                result.append(ch)
        i += 1
    return "".join(result), in_multi


def _check_brackets(lines: List[str]) -> List[Dict[str, Any]]:
    """Ensure (), {}, [] are balanced."""
    errors: List[Dict[str, Any]] = []
    stack: List[Tuple[str, int]] = []
    pairs = {"(": ")", "{": "}", "[": "]"}
    closing = {")", "}", "]"}

    for lineno, line in enumerate(lines, start=1):
        for ch in line:
            if ch in pairs:
                stack.append((pairs[ch], lineno))
            elif ch in closing:
                if not stack:
                    errors.append({
                        "line": lineno,
                        "message": f"Unmatched closing '{ch}'."
                    })
                else:
                    expected, expected_line = stack.pop()
                    if ch != expected:
                        errors.append({
                            "line": lineno,
                            "message": f"Mismatched bracket: expected '{expected}' from line {expected_line}, found '{ch}'."
                        })
    while stack:
        expected, expected_line = stack.pop()
        errors.append({
            "line": expected_line,
            "message": f"Unclosed '{expected}'."
        })
    return errors


def _validate_binders(keyword: str, line: str, lineno: int, errors: List[Dict[str, Any]]):
    """Ensure forall/exists binders include type annotations."""
    for match in re.finditer(rf"\b{keyword}\s*\(([^)]*)\)", line):
        binders = match.group(1).split(",")
        for binder in binders:
            binder = binder.strip()
            if not binder:
                continue
            if ":" not in binder:
                errors.append({
                    "line": lineno,
                    "message": f"{keyword} binder '{binder}' is missing a type annotation (use name: Type)."
                })


def _validate_params(signature: str, lineno: int, errors: List[Dict[str, Any]]):
    """Validate that function/theorem parameters include type annotations."""
    params = [p.strip() for p in signature.split(",") if p.strip()]
    for param in params:
        if ":" not in param:
            errors.append({
                "line": lineno,
                "message": f"Parameter '{param}' is missing a type annotation."
            })
        else:
            type_part = param.split(":", 1)[1].strip()
            # Types should start uppercase per spec (supports generics e.g., List[T]).
            if type_part and not re.match(r"[A-Z]", type_part):
                errors.append({
                    "line": lineno,
                    "message": f"Type '{type_part}' should start with an uppercase letter."
                })


def check_syntax(source: str) -> Dict[str, Any]:
    """Validate Acorn source text and return errors/warnings."""
    stripped, in_multi = _strip_comments_preserve_lines(source)
    stripped_lines = stripped.splitlines()
    original_lines = source.splitlines()

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if in_multi:
        errors.append({
            "line": len(stripped_lines),
            "message": "Unterminated /* */ comment."
        })

    errors.extend(_check_brackets(stripped_lines))

    for lineno, (line, raw_line) in enumerate(zip(stripped_lines, original_lines), start=1):
        # Imports
        if match := re.match(r"\s*import\s+([A-Za-z0-9_]+)", line):
            module = match.group(1)
            if not re.match(r"^[a-z0-9_]+$", module):
                errors.append({
                    "line": lineno,
                    "message": "Module names must be lowercase alphanumeric with underscores."
                })

        if match := re.match(r"\s*from\s+([A-Za-z0-9_]+)\s+import\b", line):
            module = match.group(1)
            if not re.match(r"^[a-z0-9_]+$", module):
                errors.append({
                    "line": lineno,
                    "message": "Module names must be lowercase alphanumeric with underscores."
                })

        # Numerals target type
        if match := re.match(r"\s*numerals\s+([A-Za-z0-9_]+)", line):
            type_name = match.group(1)
            if not re.match(r"[A-Z]", type_name):
                errors.append({
                    "line": lineno,
                    "message": "numerals target type should start with an uppercase letter (e.g., Nat, Int)."
                })

        # Type declarations
        for keyword in ("inductive", "structure", "typeclass", "attributes"):
            if match := re.match(rf"\s*{keyword}\s+([A-Za-z0-9_]+)", line):
                type_name = match.group(1)
                if not re.match(r"[A-Z]", type_name):
                    errors.append({
                        "line": lineno,
                        "message": f"{keyword} names should start with an uppercase letter."
                    })

        if match := re.match(r"\s*instance\s+([A-Za-z0-9_]+)\s*:\s*([A-Za-z0-9_]+)", line):
            impl_type, cls = match.groups()
            if not re.match(r"[A-Z]", impl_type):
                errors.append({
                    "line": lineno,
                    "message": "Instance type should start with an uppercase letter."
                })
            if not re.match(r"[A-Z]", cls):
                errors.append({
                    "line": lineno,
                    "message": "Typeclass name should start with an uppercase letter."
                })

        # Define
        if match := re.match(r"\s*define\s+([A-Za-z_][A-Za-z0-9_]*)", line):
            name = match.group(1)
            if not re.match(r"[a-z]", name):
                warnings.append({
                    "line": lineno,
                    "message": "Function names typically start lowercase (camelCase)."
                })
            sig_match = re.search(r"\(([^)]*)\)", line)
            ret_match = re.search(r"\)\s*->\s*([A-Za-z0-9_\[\], ]+)", line)
            if sig_match:
                _validate_params(sig_match.group(1), lineno, errors)
            if not ret_match:
                errors.append({
                    "line": lineno,
                    "message": "Define statements require an explicit return type with '-> ReturnType'."
                })
            else:
                ret_type = ret_match.group(1).strip()
                if ret_type and not re.match(r"[A-Z]", ret_type):
                    errors.append({
                        "line": lineno,
                        "message": f"Return type '{ret_type}' should start with an uppercase letter."
                    })

        # Let bindings must include type annotations before '='
        if re.match(r"\s*let\s+", line):
            if "=" in line:
                prefix = line.split("=", 1)[0]
                if ":" not in prefix:
                    errors.append({
                        "line": lineno,
                        "message": "Let bindings require an explicit type annotation before '='."
                    })

        # forall/exists binder validation
        _validate_binders("forall", line, lineno, errors)
        _validate_binders("exists", line, lineno, errors)

        # Theorem parameters (if present)
        if match := re.match(r"\s*theorem\s+[A-Za-z0-9_]*\s*\(([^)]*)\)", line):
            _validate_params(match.group(1), lineno, errors)

        # Detect likely LaTeX usage
        if "$" in line or "\\" in line:
            warnings.append({
                "line": lineno,
                "message": "Possible LaTeX syntax detected; Acorn uses its own keywords and operators."
            })

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }
