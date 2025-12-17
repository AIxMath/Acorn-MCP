"""Identifier extraction and scope analysis for Acorn code."""
import re
from typing import List, Set, Dict, Tuple
from dataclasses import dataclass
from acorn_mcp.acorn.ast import AcornItem


@dataclass
class IdentifierInfo:
    """Information about an identifier usage or definition."""
    name: str
    kind: str  # 'definition', 'reference', 'type', 'parameter'
    scope: str  # Qualified name of containing item
    line: int = 0
    col: int = 0


class IdentifierExtractor:
    """Extract identifiers from Acorn source code."""

    # Patterns for identifier types
    QUALIFIED_ID = re.compile(r'\b([A-Z][A-Za-z0-9_]*(?:\.[a-z_][A-Za-z0-9_]*)+)\b')
    TYPE_ID = re.compile(r'\b([A-Z][A-Za-z0-9_]*)\b')
    VAR_ID = re.compile(r'\b([a-z_][a-z0-9_]*)\b')

    def extract_defined_identifiers(self, item: AcornItem) -> List[str]:
        """Extract all identifiers defined by this item.

        Returns a list of fully qualified names that this item makes available.
        """
        defined = [item.name]

        # For typeclasses, add member names
        if hasattr(item, 'members') and item.members:
            for member in item.members:
                if hasattr(member, 'name'):
                    # Typeclass members
                    defined.append(f"{item.name}.{member.name}")
                elif isinstance(member, dict) and 'name' in member:
                    defined.append(f"{item.name}.{member['name']}")

        # For structures, add field accessors
        if hasattr(item, 'fields') and item.fields:
            for field_name, _ in item.fields:
                defined.append(f"{item.name}.{field_name}")

        return defined

    def extract_referenced_identifiers(self, source: str) -> Set[str]:
        """Extract all identifiers referenced in source code.

        Returns a set of identifier names (may be qualified or simple).
        """
        references = set()

        # Find all qualified identifiers (e.g., Complex.add, Real.0)
        for match in self.QUALIFIED_ID.finditer(source):
            references.add(match.group(1))

        # Find type names (capitalized identifiers)
        for match in self.TYPE_ID.finditer(source):
            name = match.group(1)
            # Skip keywords
            if name not in {'Bool', 'True', 'False', 'Nat', 'Int', 'Real'}:
                references.add(name)

        # Find variable/function names (lowercase identifiers)
        for match in self.VAR_ID.finditer(source):
            name = match.group(1)
            # Skip common keywords
            if name not in {'if', 'else', 'then', 'let', 'define', 'match',
                           'by', 'forall', 'exists', 'function', 'return',
                           'true', 'false', 'and', 'or', 'not', 'implies'}:
                references.add(name)

        return references

    def build_identifier_index(self, items: List[AcornItem]) -> Dict[str, AcornItem]:
        """Build an index mapping identifier names to their defining items.

        Args:
            items: List of parsed Acorn items

        Returns:
            Dictionary mapping identifier names to the items that define them
        """
        index = {}

        for item in items:
            # Add the item's main name
            index[item.name] = item

            # Add member names for items with members
            defined_ids = self.extract_defined_identifiers(item)
            for ident in defined_ids:
                index[ident] = item

        return index

    def find_identifier_definition(self, identifier: str, items: List[AcornItem]) -> AcornItem | None:
        """Find the item that defines a given identifier.

        Args:
            identifier: The identifier to search for (may be qualified)
            items: List of all parsed items

        Returns:
            The AcornItem that defines this identifier, or None if not found
        """
        index = self.build_identifier_index(items)
        return index.get(identifier)

    def extract_all_identifiers(self, source: str, scope: str = "") -> List[IdentifierInfo]:
        """Extract all identifiers with their context information.

        Args:
            source: Source code to analyze
            scope: Qualified name of containing scope

        Returns:
            List of IdentifierInfo objects
        """
        identifiers = []
        lines = source.split('\n')

        for line_num, line in enumerate(lines, 1):
            # Find all identifiers in this line
            for match in self.QUALIFIED_ID.finditer(line):
                identifiers.append(IdentifierInfo(
                    name=match.group(1),
                    kind='reference',
                    scope=scope,
                    line=line_num,
                    col=match.start()
                ))

            for match in self.TYPE_ID.finditer(line):
                name = match.group(1)
                if name not in {'Bool', 'True', 'False'}:
                    identifiers.append(IdentifierInfo(
                        name=name,
                        kind='type',
                        scope=scope,
                        line=line_num,
                        col=match.start()
                    ))

        return identifiers


def export_identifier_map(items: List[AcornItem]) -> Dict[str, Dict]:
    """Export a JSON-serializable map of all identifiers and their definitions.

    Args:
        items: List of parsed Acorn items

    Returns:
        Dictionary mapping identifier names to definition info:
        {
            "Complex.add": {
                "defined_in": "complex.Complex_attributes",
                "kind": "attributes_method",
                "file": "complex.ac",
                "line": 34
            },
            ...
        }
    """
    extractor = IdentifierExtractor()
    result = {}

    for item in items:
        # Add main identifier
        result[item.name] = {
            "defined_in": item.name,
            "kind": item.kind,
            "file": str(item.location.file) if item.location else None,
            "line": item.location.line if item.location else None,
        }

        # Add all defined sub-identifiers
        defined_ids = extractor.extract_defined_identifiers(item)
        for ident in defined_ids:
            if ident != item.name:  # Skip the main name (already added)
                result[ident] = {
                    "defined_in": item.name,
                    "kind": item.kind,
                    "file": str(item.location.file) if item.location else None,
                    "line": item.location.line if item.location else None,
                }

    return result
