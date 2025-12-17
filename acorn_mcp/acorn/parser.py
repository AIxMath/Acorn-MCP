"""Parser for Acorn language source files."""
import re
import hashlib
from pathlib import Path
from typing import List, Tuple, Optional, Iterable
from acorn_mcp.acorn.ast import (
    AcornItem,
    Theorem,
    Definition,
    TypeClass,
    TypeClassMember,
    Structure,
    Inductive,
    AttributesBlock,
    ImportStatement,
    SourceLocation,
)


class AcornParser:
    """Parser for Acorn source files."""

    def __init__(self, source_root: Optional[Path] = None):
        """Initialize parser.

        Args:
            source_root: Root directory for computing module names
        """
        self.source_root = source_root
        self.identifier_index = {}  # Maps names to items for linking

    def _generate_uuid(self, name: str, file_path: Path) -> str:
        """Generate a deterministic UUID for an item based on its qualified name and file."""
        content = f"{file_path}::{name}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _extract_identifiers(self, source: str) -> set[str]:
        """Extract all identifiers referenced in source code.

        Returns identifiers like: Complex.add, Real.gt, AddGroup, etc.
        """
        identifiers = set()

        # Pattern 1: Qualified identifiers (Type.member or module.Type.member)
        # Examples: Complex.add, Real.0, int.Int.add
        qualified_pattern = re.compile(r'\b([a-z_][a-z0-9_]*\.)*[A-Z][A-Za-z0-9_]*(?:\.[a-z_A-Z][A-Za-z0-9_]*)+\b')
        for match in qualified_pattern.finditer(source):
            identifiers.add(match.group(0))

        # Pattern 2: Type names (capitalized)
        # Examples: Complex, Real, Int, AddGroup
        type_pattern = re.compile(r'\b[A-Z][A-Za-z0-9_]*\b')
        for match in type_pattern.finditer(source):
            name = match.group(0)
            # Skip common keywords
            if name not in {'Bool', 'True', 'False'}:
                identifiers.add(name)

        # Pattern 3: Function/value names in qualified context
        # Look for patterns like "Type.name" where we haven't caught it yet
        member_pattern = re.compile(r'\b([A-Z][A-Za-z0-9_]*)\.([a-z_][A-Za-z0-9_]*)\b')
        for match in member_pattern.finditer(source):
            identifiers.add(match.group(0))  # Full qualified name

        return identifiers

    def _enrich_item(self, item: AcornItem, path: Path):
        """Add UUID and extract identifiers for an item."""
        # Generate UUID
        if not item.uuid:
            item.uuid = self._generate_uuid(item.name, path)

        # Extract identifiers from source
        item.identifiers = self._extract_identifiers(item.source)

        # Add to index for later linking
        self.identifier_index[item.name] = item

    def parse_file(self, path: Path) -> Tuple[List[AcornItem], List[ImportStatement]]:
        """Parse an Acorn source file.

        Returns:
            Tuple of (items, imports)
        """
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        items: List[AcornItem] = []
        imports: List[ImportStatement] = []

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith('//'):
                i += 1
                continue

            # Parse imports
            if stripped.startswith('from ') or stripped.startswith('import '):
                import_stmt = self._parse_import(line)
                if import_stmt:
                    imports.append(import_stmt)
                i += 1
                continue

            # Parse instances
            if stripped.startswith('instance '):
                item, end_line = self._parse_instance(lines, i, path)
                if item:
                    items.append(item)
                    # Also add instance members as separate items
                    items.extend(self._expand_instance_members(item, path))
                i = end_line + 1
                continue

            # Parse theorems/axioms
            if stripped.startswith('theorem ') or stripped.startswith('axiom '):
                item, end_line = self._parse_theorem(lines, i, path)
                if item:
                    items.append(item)
                i = end_line + 1
                continue

            # Parse typeclasses
            if stripped.startswith('typeclass '):
                item, end_line = self._parse_typeclass(lines, i, path)
                if item:
                    items.append(item)
                    # Also add typeclass members as separate items
                    items.extend(self._expand_typeclass_members(item, path))
                i = end_line + 1
                continue

            # Parse structures
            if stripped.startswith('structure '):
                item, end_line = self._parse_structure(lines, i, path)
                if item:
                    items.append(item)
                i = end_line + 1
                continue

            # Parse inductive types
            if stripped.startswith('inductive '):
                item, end_line = self._parse_inductive(lines, i, path)
                if item:
                    items.append(item)
                i = end_line + 1
                continue

            # Parse definitions
            if stripped.startswith('define '):
                item, end_line = self._parse_definition(lines, i, path)
                if item:
                    items.append(item)
                i = end_line + 1
                continue

            # Parse attributes blocks
            if stripped.startswith('attributes '):
                item, end_line = self._parse_attributes(lines, i, path)
                if item:
                    # Don't add the attributes block itself, only the expanded members
                    # items.append(item)
                    items.extend(self._expand_attributes_members(item, path))
                i = end_line + 1
                continue

            i += 1

        # Enrich all items with UUIDs and extracted identifiers
        for item in items:
            self._enrich_item(item, path)

        return items, imports

    def _get_module_name(self, path: Path) -> str:
        """Compute module name from file path."""
        if self.source_root:
            rel = path.relative_to(self.source_root).with_suffix("")
            return ".".join(rel.parts)
        return path.stem

    def _parse_import(self, line: str) -> Optional[ImportStatement]:
        """Parse an import statement."""
        match = re.match(r"(?:from\s+([A-Za-z_][A-Za-z0-9_/.]*)\s+)?import\s+([A-Za-z_][A-Za-z0-9_,\s]*)", line)
        if not match:
            return None

        module = match.group(1)
        items_str = match.group(2)
        items = [item.strip() for item in items_str.split(',') if item.strip()]

        return ImportStatement(module=module, items=items, source=line.strip())

    def _capture_block(self, lines: List[str], start_line: int, start_col: int) -> Tuple[str, int, int]:
        """Capture text inside a {...} block.

        Returns: (content_without_outer_braces, end_line, end_col_after_closing_brace)
        """
        brace_count = 1
        collected: List[str] = []
        initial_col = start_col

        for idx in range(start_line, len(lines)):
            line = lines[idx]
            segment = line[start_col:] if idx == start_line else line

            # Simple brace counting (doesn't handle strings/comments perfectly)
            for j, ch in enumerate(segment):
                if ch == '{':
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found closing brace
                        collected.append(segment[:j])
                        closing_col = (initial_col if idx == start_line else 0) + j
                        content = "\n".join(collected)
                        return self._dedent(content), idx, closing_col + 1

            collected.append(segment)
            start_col = 0  # After first line, continue from column 0

        raise ValueError("Unclosed brace block")

    def _dedent(self, text: str) -> str:
        """Remove common leading whitespace."""
        lines = text.split('\n')
        if not lines:
            return text

        # Find minimum indentation
        min_indent = float('inf')
        for line in lines:
            if line.strip():
                leading = len(line) - len(line.lstrip())
                min_indent = min(min_indent, leading)

        if min_indent == float('inf') or min_indent == 0:
            return text

        # Remove common indentation
        dedented = []
        for line in lines:
            if line.strip():
                dedented.append(line[min_indent:])
            else:
                dedented.append(line)

        return '\n'.join(dedented)

    def _parse_theorem(self, lines: List[str], start: int, path: Path) -> Tuple[Optional[Theorem], int]:
        """Parse a theorem or axiom."""
        line = lines[start]
        stripped = line.lstrip()

        # Determine if theorem or axiom
        is_axiom = stripped.startswith('axiom')
        keyword = 'axiom' if is_axiom else 'theorem'

        # Extract name
        match = re.match(rf'{keyword}\s+([A-Za-z_][A-Za-z0-9_]*)', stripped)
        if not match:
            return None, start

        name = match.group(1)

        # Find opening brace of head block
        brace_pos = line.find('{')
        if brace_pos == -1:
            return None, start

        # Capture head block
        try:
            head_body, head_end_line, head_end_col = self._capture_block(lines, start, brace_pos + 1)

            # Build head text (keyword through closing })
            kw_col = line.find(keyword)
            head_parts = [line[kw_col:]]
            for idx in range(start + 1, head_end_line + 1):
                if idx < head_end_line:
                    head_parts.append(lines[idx])
                else:
                    head_parts.append(lines[idx][:head_end_col])

            head_text = '\n'.join(head_parts).strip()

            # Look for proof (theorems only)
            proof = ""
            raw_end_line = head_end_line
            raw_end_col = head_end_col

            if not is_axiom:
                # Check for "by {" after head
                remainder = lines[head_end_line][head_end_col:]
                by_match = re.search(r'by\s*\{', remainder)

                if by_match:
                    by_brace_pos = head_end_col + remainder.find('{', by_match.start())
                    proof_body, proof_end_line, proof_end_col = self._capture_block(
                        lines, head_end_line, by_brace_pos + 1
                    )
                    proof = self._dedent(proof_body)
                    raw_end_line = proof_end_line
                    raw_end_col = proof_end_col

            # Build raw text
            raw_parts = []
            for idx in range(start, raw_end_line + 1):
                if idx == start:
                    raw_parts.append(lines[idx][kw_col:])
                elif idx < raw_end_line:
                    raw_parts.append(lines[idx])
                else:
                    raw_parts.append(lines[idx][:raw_end_col])

            raw_text = '\n'.join(raw_parts).strip()

            return Theorem(
                name=name,
                kind="axiom" if is_axiom else "theorem",
                source=raw_text,
                location=SourceLocation(path, start + 1),
                head=head_text,
                proof=proof,
                raw=raw_text,
            ), raw_end_line

        except ValueError:
            return None, start

    def _parse_typeclass(self, lines: List[str], start: int, path: Path) -> Tuple[Optional[TypeClass], int]:
        """Parse a typeclass definition."""
        line = lines[start]

        # Pattern: typeclass [TypeParam:] Name extends Parent1, Parent2 {
        match = re.match(
            r'typeclass\s+(?:([A-Z]):\s+)?([A-Z][A-Za-z0-9_]*)\s*(?:extends\s+([A-Za-z0-9_,\s]+))?\s*\{',
            line
        )
        if not match:
            return None, start

        type_param = match.group(1) or 'Self'
        name = match.group(2)
        extends_str = match.group(3)
        extends = [p.strip() for p in extends_str.split(',')] if extends_str else []

        # Capture body
        brace_pos = line.find('{')
        try:
            body, end_line, _ = self._capture_block(lines, start, brace_pos + 1)

            # Parse members from body
            members = self._parse_typeclass_members(body, type_param)

            # Build full source
            source_lines = [lines[i] for i in range(start, end_line + 1)]
            source = '\n'.join(source_lines).strip()

            return TypeClass(
                name=name,
                kind="typeclass",
                source=source,
                location=SourceLocation(path, start + 1),
                type_param=type_param,
                extends=extends,
                members=members,
            ), end_line

        except ValueError:
            return None, start

    def _parse_typeclass_members(self, body: str, type_param: str) -> List[TypeClassMember]:
        """Parse members from typeclass body."""
        members = []
        lines = body.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped or stripped.startswith('///') or stripped.startswith('//'):
                i += 1
                continue

            # Look for member definition: name(params) { body }
            # or axiom: name(params: Type) { constraint }
            match = re.match(r'([a-z_][a-z0-9_]*)\s*(?:\(([^)]*)\))?\s*(?:\{|:)', stripped)
            if match:
                member_name = match.group(1)
                params = match.group(2) or ""

                # Capture until end of member (find matching brace or semicolon)
                member_lines = [line]
                if '{' in line:
                    brace_count = line.count('{') - line.count('}')
                    j = i + 1
                    while j < len(lines) and brace_count > 0:
                        member_lines.append(lines[j])
                        brace_count += lines[j].count('{') - lines[j].count('}')
                        j += 1
                    i = j
                else:
                    i += 1

                member_source = '\n'.join(member_lines)

                # Determine kind (method has implementation, axiom is constraint)
                kind = "method" if "define" in member_source or "->" in params else "axiom"

                members.append(TypeClassMember(
                    name=member_name,
                    kind=kind,
                    signature=f"{member_name}({params})",
                    body=member_source.strip(),
                    source=member_source,
                ))
                continue

            i += 1

        return members

    def _expand_typeclass_members(self, typeclass: TypeClass, path: Path) -> List[AcornItem]:
        """Expand typeclass members into separate items.

        Converts TypeClass.member_name placeholders to TypeClassName.member_name
        """
        items = []
        for member in typeclass.members:
            qualified_name = typeclass.get_member_qualified_name(member.name)

            if member.kind == "method":
                items.append(Definition(
                    name=qualified_name,
                    kind="typeclass_method",
                    source=member.source,
                    location=typeclass.location,
                    signature=member.signature,
                    body=member.body or "",
                ))
            else:  # axiom
                items.append(Theorem(
                    name=qualified_name,
                    kind="typeclass_axiom",
                    source=member.source,
                    location=typeclass.location,
                    head=member.signature,
                    proof="",
                    raw=member.source,
                ))

        return items

    def _expand_attributes_members(self, attrs_block: AttributesBlock, path: Path) -> List[AcornItem]:
        """Expand attributes block members into separate items.

        Creates individual Definition items for each method in the attributes block.
        """
        items = []
        for member in attrs_block.members:
            # Update location to match parent block
            member.location = attrs_block.location
            items.append(member)

        return items

    def _parse_structure(self, lines: List[str], start: int, path: Path) -> Tuple[Optional[Structure], int]:
        """Parse a structure definition."""
        line = lines[start]

        # Pattern: structure Name[TypeParams] {
        match = re.match(r'structure\s+([A-Z][A-Za-z0-9_]*)(?:\[([^\]]+)\])?\s*\{', line)
        if not match:
            return None, start

        name = match.group(1)
        type_params_str = match.group(2)
        type_params = [p.strip() for p in type_params_str.split(',')] if type_params_str else []

        brace_pos = line.find('{')
        try:
            body, end_line, end_col = self._capture_block(lines, start, brace_pos + 1)

            # Check for constraint block
            constraint = None
            final_line = end_line

            remainder = lines[end_line][end_col:]
            if 'constraint' in remainder and '{' in remainder:
                constraint_brace = end_col + remainder.find('{')
                constraint_body, constraint_end, _ = self._capture_block(lines, end_line, constraint_brace + 1)
                constraint = self._dedent(constraint_body)
                final_line = constraint_end

            # Build source
            source_lines = [lines[i] for i in range(start, final_line + 1)]
            source = '\n'.join(source_lines).strip()

            return Structure(
                name=name,
                kind="structure",
                source=source,
                location=SourceLocation(path, start + 1),
                type_params=type_params,
                constraint=constraint,
            ), final_line

        except ValueError:
            return None, start

    def _parse_inductive(self, lines: List[str], start: int, path: Path) -> Tuple[Optional[Inductive], int]:
        """Parse an inductive type definition."""
        line = lines[start]

        match = re.match(r'inductive\s+([A-Z][A-Za-z0-9_]*)(?:\[([^\]]+)\])?\s*\{', line)
        if not match:
            return None, start

        name = match.group(1)
        type_params_str = match.group(2)
        type_params = [p.strip() for p in type_params_str.split(',')] if type_params_str else []

        brace_pos = line.find('{')
        try:
            body, end_line, _ = self._capture_block(lines, start, brace_pos + 1)

            source_lines = [lines[i] for i in range(start, end_line + 1)]
            source = '\n'.join(source_lines).strip()

            return Inductive(
                name=name,
                kind="inductive",
                source=source,
                location=SourceLocation(path, start + 1),
                type_params=type_params,
            ), end_line

        except ValueError:
            return None, start

    def _parse_definition(self, lines: List[str], start: int, path: Path) -> Tuple[Optional[Definition], int]:
        """Parse a define statement."""
        line = lines[start]

        match = re.match(r'define\s+([a-z_][a-z0-9_]*)', line)
        if not match:
            return None, start

        name = match.group(1)

        brace_pos = line.find('{')
        if brace_pos == -1:
            return None, start

        try:
            body, end_line, _ = self._capture_block(lines, start, brace_pos + 1)

            source_lines = [lines[i] for i in range(start, end_line + 1)]
            source = '\n'.join(source_lines).strip()

            # Extract signature (everything before {)
            signature = line[:brace_pos].strip()

            return Definition(
                name=name,
                kind="define",
                source=source,
                location=SourceLocation(path, start + 1),
                signature=signature,
                body=self._dedent(body),
            ), end_line

        except ValueError:
            return None, start

    def _parse_attributes(self, lines: List[str], start: int, path: Path) -> Tuple[Optional[AttributesBlock], int]:
        """Parse an attributes block."""
        line = lines[start]

        # Pattern: attributes TypeName[TypeParams] { or attributes T: TypeClass {
        match = re.match(r'attributes\s+(?:([A-Z]):\s+)?([A-Z][A-Za-z0-9_<>\[\],\s]*?)\s*\{', line)
        if not match:
            return None, start

        type_param = match.group(1)  # Will be None for concrete types like Complex
        target_type = match.group(2).strip()

        # For typeclass constraints (e.g., "M: Monoid"), use the typeclass name
        # For concrete types (e.g., "Complex"), use the type name
        base_name = target_type if not type_param else target_type
        name = f"{base_name}_attributes"

        brace_pos = line.find('{')
        try:
            body, end_line, _ = self._capture_block(lines, start, brace_pos + 1)

            # Parse member definitions from body
            members = self._parse_attributes_members(body, base_name)

            source_lines = [lines[i] for i in range(start, end_line + 1)]
            source = '\n'.join(source_lines).strip()

            return AttributesBlock(
                name=name,
                kind="attributes",
                source=source,
                location=SourceLocation(path, start + 1),
                target_type=base_name,
                members=members,
            ), end_line

        except ValueError:
            return None, start

    def _parse_attributes_members(self, body: str, target_type: str) -> List[Definition]:
        """Parse let and define statements from attributes block."""
        members = []
        lines = body.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip comments and empty lines
            if not stripped or stripped.startswith('///') or stripped.startswith('//'):
                i += 1
                continue

            # Look for let statements (constants/values)
            # Pattern: let name: Type = value
            let_match = re.match(r'let\s+([a-zA-Z0-9_]+)\s*:', stripped)
            if let_match:
                member_name = let_match.group(1)
                qualified_name = f"{target_type}.{member_name}"

                # Capture until end of statement (usually one line, or until we hit a brace balance)
                member_lines = [line]
                if '{' in line:
                    brace_count = line.count('{') - line.count('}')
                    j = i + 1
                    while j < len(lines) and brace_count > 0:
                        member_lines.append(lines[j])
                        brace_count += lines[j].count('{') - lines[j].count('}')
                        j += 1
                    i = j
                else:
                    i += 1

                member_source = '\n'.join(member_lines)

                members.append(Definition(
                    name=qualified_name,
                    kind="attributes_constant",
                    source=member_source,
                    location=None,  # Will be set by caller
                    signature=member_source.strip(),
                    body=member_source.strip(),
                ))
                continue

            # Look for define statements (methods)
            define_match = re.match(r'define\s+([a-z_][a-z0-9_]*)', stripped)
            if define_match:
                member_name = define_match.group(1)
                qualified_name = f"{target_type}.{member_name}"

                # Capture member body
                member_lines = [line]
                if '{' in line:
                    brace_count = line.count('{') - line.count('}')
                    j = i + 1
                    while j < len(lines) and brace_count > 0:
                        member_lines.append(lines[j])
                        brace_count += lines[j].count('{') - lines[j].count('}')
                        j += 1
                    i = j
                else:
                    i += 1

                member_source = '\n'.join(member_lines)

                # Extract signature (everything before {)
                sig_match = re.search(r'(define\s+[^{]+)', member_source)
                signature = sig_match.group(1).strip() if sig_match else f"define {member_name}"

                members.append(Definition(
                    name=qualified_name,
                    kind="attributes_method",
                    source=member_source,
                    location=None,  # Will be set by caller
                    signature=signature,
                    body=member_source.strip(),
                ))
                continue

            i += 1

        return members

    def _parse_instance(self, lines: List[str], start: int, path: Path) -> Tuple[Optional['Instance'], int]:
        """Parse an instance statement."""
        from acorn_mcp.acorn.ast import Instance
        
        line = lines[start]

        # Pattern: instance TypeName: TypeClass { ... }
        # or: instance TypeName: TypeClass (no body)
        match = re.match(r'instance\s+([A-Z][A-Za-z0-9_]*):\s+([A-Z][A-Za-z0-9_]*)', line)
        if not match:
            return None, start

        type_name = match.group(1)
        typeclass_name = match.group(2)
        name = f"{type_name}_{typeclass_name}_instance"

        # Check if there's a body
        if '{' not in line:
            # No body instance (inherits everything)
            return Instance(
                name=name,
                kind="instance",
                source=line.strip(),
                location=SourceLocation(path, start + 1),
                type_name=type_name,
                typeclass_name=typeclass_name,
                members=[],
            ), start

        # Has body, parse it
        brace_pos = line.find('{')
        try:
            body, end_line, _ = self._capture_block(lines, start, brace_pos + 1)

            # Parse member let bindings from body
            members = self._parse_instance_members(body, type_name, typeclass_name)

            # Build source
            source_lines = [lines[i] for i in range(start, end_line + 1)]
            source = '\n'.join(source_lines).strip()

            return Instance(
                name=name,
                kind="instance",
                source=source,
                location=SourceLocation(path, start + 1),
                type_name=type_name,
                typeclass_name=typeclass_name,
                members=members,
            ), end_line

        except ValueError:
            return None, start

    def _parse_instance_members(self, body: str, type_name: str, typeclass_name: str) -> List[Definition]:
        """Parse let bindings from instance body."""
        members = []
        lines = body.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip comments and empty lines
            if not stripped or stripped.startswith('///') or stripped.startswith('//'):
                i += 1
                continue

            # Look for let statements
            # Pattern: let name: Type = value
            let_match = re.match(r'let\s+([a-zA-Z0-9_]+)\s*:', stripped)
            if let_match:
                member_name = let_match.group(1)
                # For instances, members bind to the type (e.g., Int.add from instance Int: AddSemigroup)
                qualified_name = f"{type_name}.{member_name}"

                # Capture until end of statement
                member_lines = [line]
                if '=' in line:
                    # Continue collecting lines until we have a complete statement
                    j = i + 1
                    while j < len(lines) and not stripped.rstrip().endswith('}'):
                        member_lines.append(lines[j])
                        stripped = lines[j].strip()
                        j += 1
                        if not stripped or (j < len(lines) and not lines[j].strip()):
                            break
                    i = j
                else:
                    i += 1

                member_source = '\n'.join(member_lines)

                members.append(Definition(
                    name=qualified_name,
                    kind="instance_member",
                    source=member_source,
                    location=None,  # Will be set by caller
                    signature=member_source.strip(),
                    body=member_source.strip(),
                ))
                continue

            i += 1

        return members

    def _expand_instance_members(self, instance: 'Instance', path: Path) -> List['AcornItem']:
        """Expand instance members into separate items."""
        items = []
        for member in instance.members:
            member.location = instance.location
            items.append(member)
        return items
