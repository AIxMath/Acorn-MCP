"""Abstract Syntax Tree definitions for Acorn language constructs."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Set


@dataclass
class SourceLocation:
    """Location in source file."""
    file: Path
    line: int
    column: Optional[int] = None


@dataclass
class AcornItem:
    """Base class for all Acorn items."""
    name: str
    kind: str
    source: str  # Full source text
    location: Optional[SourceLocation] = None
    dependencies: Set[str] = field(default_factory=set)
    identifiers: Set[str] = field(default_factory=set)  # Identifiers used in this item
    uuid: Optional[str] = None  # Unique identifier for this item

    def qualified_name(self, module: str) -> str:
        """Get the fully qualified name."""
        return f"{module}.{self.name}"


@dataclass
class Theorem(AcornItem):
    """Represents a theorem or axiom."""
    head: str = ""  # Theorem signature + head block
    proof: str = ""  # Proof body (empty for axioms)
    raw: str = ""  # Complete source including 'by' clause

    def __post_init__(self):
        if not self.kind:
            self.kind = "axiom" if not self.proof else "theorem"


@dataclass
class Definition(AcornItem):
    """Represents a define statement."""
    signature: str = ""  # Function signature
    body: str = ""  # Function body
    return_type: Optional[str] = None


@dataclass
class TypeClassMember:
    """Represents a member of a typeclass (method or axiom)."""
    name: str
    kind: str  # "method" or "axiom"
    signature: str
    body: Optional[str] = None  # For axioms/constraints
    source: str = ""  # Full source for this member


@dataclass
class TypeClass(AcornItem):
    """Represents a typeclass definition."""
    type_param: str = "Self"  # The placeholder type parameter (e.g., "A")
    extends: List[str] = field(default_factory=list)  # Parent typeclasses
    members: List[TypeClassMember] = field(default_factory=list)

    def get_member_qualified_name(self, member_name: str) -> str:
        """Get the qualified name for a typeclass member.

        Example: For typeclass AddGroup with member 'neg',
        returns 'AddGroup.neg' (not 'A.neg')
        """
        return f"{self.name}.{member_name}"


@dataclass
class Structure(AcornItem):
    """Represents a structure definition."""
    type_params: List[str] = field(default_factory=list)
    fields: List[tuple[str, str]] = field(default_factory=list)  # (name, type)
    constraint: Optional[str] = None  # Constraint block body


@dataclass
class Inductive(AcornItem):
    """Represents an inductive type definition."""
    type_params: List[str] = field(default_factory=list)
    constructors: List[tuple[str, Optional[str]]] = field(default_factory=list)  # (name, params)


@dataclass
class AttributesBlock(AcornItem):
    """Represents an attributes block for a type."""
    target_type: str = ""  # Type being extended
    members: List[Definition] = field(default_factory=list)


@dataclass
class Instance(AcornItem):
    """Represents a typeclass instance implementation."""
    type_name: str = ""  # Type implementing the typeclass (e.g., "Int")
    typeclass_name: str = ""  # Typeclass being implemented (e.g., "AddGroup")
    members: List[Definition] = field(default_factory=list)  # let bindings in body


@dataclass
class ImportStatement:
    """Represents an import statement."""
    module: Optional[str]  # Module path for 'from module import ...'
    items: List[str]  # Imported items
    source: str  # Full source line
