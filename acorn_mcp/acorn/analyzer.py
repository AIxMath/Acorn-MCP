"""Dependency analyzer for Acorn code."""
from typing import Set
from acorn_mcp.acorn.ast import AcornItem, Theorem, Definition, TypeClass
from acorn_mcp.type_inference import extract_dependencies_with_types


class DependencyAnalyzer:
    """Analyzes dependencies in Acorn code."""

    def analyze(self, item: AcornItem) -> Set[str]:
        """Extract dependencies from an Acorn item.

        Returns:
            Set of qualified dependency names
        """
        if isinstance(item, Theorem):
            return self._analyze_theorem(item)
        elif isinstance(item, Definition):
            return self._analyze_definition(item)
        elif isinstance(item, TypeClass):
            return self._analyze_typeclass(item)
        else:
            # For other items, extract from source
            return extract_dependencies_with_types(item.source, "")

    def _analyze_theorem(self, theorem: Theorem) -> Set[str]:
        """Analyze theorem dependencies."""
        full_text = f"{theorem.head}\n{theorem.proof}"
        deps = extract_dependencies_with_types(full_text, theorem.head)

        # Remove self-reference
        deps.discard(theorem.name)
        if '.' in theorem.name:
            deps.discard(theorem.name.split('.')[-1])

        return deps

    def _analyze_definition(self, defn: Definition) -> Set[str]:
        """Analyze definition dependencies."""
        deps = extract_dependencies_with_types(defn.source, defn.signature)

        # Remove self-reference
        deps.discard(defn.name)
        if '.' in defn.name:
            deps.discard(defn.name.split('.')[-1])

        return deps

    def _analyze_typeclass(self, typeclass: TypeClass) -> Set[str]:
        """Analyze typeclass dependencies."""
        deps = extract_dependencies_with_types(typeclass.source, "")

        # Add extends relationships
        deps.update(typeclass.extends)

        # Remove self-reference
        deps.discard(typeclass.name)

        return deps
