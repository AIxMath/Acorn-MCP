"""Type inference and operator resolution for Acorn code."""
import re
from typing import Dict, Set, Optional, List, Tuple
from dataclasses import dataclass


# Operator mapping: operator -> method name
OPERATORS = {
    '>': 'gt',
    '<': 'lt',
    '>=': 'gte',
    '<=': 'lte',
    '+': 'add',
    '-': 'sub',
    '*': 'mul',
    '/': 'div',
    '%': 'mod',
}

# Unary operators
UNARY_OPERATORS = {
    '-': 'neg',
}


@dataclass
class TypeContext:
    """Maintains type information for variables in scope."""
    # variable_name -> type_name
    variables: Dict[str, str]
    # Known type names from definitions/theorems
    known_types: Set[str]

    def __init__(self):
        self.variables = {}
        self.known_types = set()

    def add_variable(self, name: str, type_name: str):
        """Add a variable with its type."""
        self.variables[name] = type_name

    def get_type(self, var_name: str) -> Optional[str]:
        """Get the type of a variable."""
        return self.variables.get(var_name)

    def add_known_type(self, type_name: str):
        """Register a known type."""
        self.known_types.add(type_name)

    def copy(self) -> 'TypeContext':
        """Create a copy of this context."""
        new_ctx = TypeContext()
        new_ctx.variables = self.variables.copy()
        new_ctx.known_types = self.known_types.copy()
        return new_ctx


def extract_type_annotations(text: str) -> Dict[str, str]:
    """Extract variable type annotations from function/theorem signatures.

    Examples:
        "define foo(n: Nat, x: Real)" -> {"n": "Nat", "x": "Real"}
        "theorem bar[F: Field](x: Int)" -> {"F": "Field", "x": "Int"}
    """
    annotations = {}

    # Pattern for type annotations: name: Type
    # Handles both regular params and type params in brackets
    pattern = r'([a-z_][a-z0-9_]*)\s*:\s*([A-Z][A-Za-z0-9_<>\[\],\s]*?)(?=[,\)\]])'

    for match in re.finditer(pattern, text):
        var_name = match.group(1)
        type_name = match.group(2).strip()
        # Clean up type name (remove extra spaces, handle generics)
        type_name = re.sub(r'\s+', '', type_name)
        annotations[var_name] = type_name

    return annotations


def extract_quantified_variables(text: str) -> Dict[str, str]:
    """Extract type annotations from forall/exists quantifiers.

    Examples:
        "forall(x: Nat, y: Real)" -> {"x": "Nat", "y": "Real"}
    """
    annotations = {}

    # Pattern for quantifiers: forall(vars...) or exists(vars...)
    quantifier_pattern = r'(?:forall|exists)\s*\(\s*([^)]+)\s*\)'

    for match in re.finditer(quantifier_pattern, text):
        inner = match.group(1)
        # Extract individual variable declarations
        for var_decl in inner.split(','):
            var_decl = var_decl.strip()
            if ':' in var_decl:
                parts = var_decl.split(':')
                if len(parts) == 2:
                    var_name = parts[0].strip()
                    type_name = parts[1].strip()
                    annotations[var_name] = type_name

    return annotations


def resolve_operator_type(operator: str, left_type: Optional[str],
                          right_type: Optional[str] = None,
                          is_unary: bool = False) -> Optional[str]:
    """Resolve an operator to its qualified method name.

    Args:
        operator: The operator symbol (+, -, *, etc.)
        left_type: Type of the left operand (or sole operand for unary)
        right_type: Type of the right operand (for binary operators)
        is_unary: Whether this is a unary operator

    Returns:
        Qualified method name (e.g., "Nat.add", "Real.mul") or None
    """
    if is_unary:
        method = UNARY_OPERATORS.get(operator)
        if method and left_type:
            return f"{left_type}.{method}"
        return None

    method = OPERATORS.get(operator)
    if not method or not left_type:
        return None

    # For binary operators, use the type of the left operand
    # (In Acorn, the left operand's type determines the method)
    return f"{left_type}.{method}"


def infer_literal_type(literal: str) -> Optional[str]:
    """Infer the type of a literal value.

    Examples:
        "Nat.0" -> "Nat"
        "Int.5" -> "Int"
        "Real.3.14" -> "Real"
        "true" -> "Bool"
    """
    # Qualified literals: Type.value
    if '.' in literal and literal[0].isupper():
        return literal.split('.')[0]

    # Boolean literals
    if literal in ('true', 'false'):
        return 'Bool'

    # Unqualified numeric literals are ambiguous
    # Could be Nat, Int, or Real depending on context
    return None


def extract_dependencies_with_types(text: str, signature: str = "") -> Set[str]:
    """Extract qualified dependencies from Acorn code using type inference.

    This function performs basic type inference to resolve operators to their
    qualified method names (e.g., x + y -> Nat.add if x: Nat).

    Args:
        text: The Acorn code to analyze
        signature: The function/theorem signature for type annotations

    Returns:
        Set of qualified identifiers (types and method names)
    """
    dependencies = set()

    # Build initial type context from signature
    ctx = TypeContext()
    sig_annotations = extract_type_annotations(signature)
    for var, typ in sig_annotations.items():
        ctx.add_variable(var, typ)
        dependencies.add(typ)  # The type itself is a dependency

    # Extract quantified variables
    quant_annotations = extract_quantified_variables(text)
    for var, typ in quant_annotations.items():
        ctx.add_variable(var, typ)
        dependencies.add(typ)

    # Extract explicit type references (Type.method, Type.value)
    qualified_pattern = r'\b([A-Z][A-Za-z0-9_]*)\.([a-z_][a-z0-9_]*)\b'
    for match in re.finditer(qualified_pattern, text):
        type_name = match.group(1)
        member_name = match.group(2)
        dependencies.add(type_name)
        dependencies.add(f"{type_name}.{member_name}")

    # Extract standalone type names (capitalized identifiers)
    type_pattern = r'\b([A-Z][A-Za-z0-9_]+)\b'
    for match in re.finditer(type_pattern, text):
        type_name = match.group(1)
        # Filter out keywords
        if type_name not in {'If', 'Then', 'Else', 'Match', 'Case', 'True', 'False'}:
            dependencies.add(type_name)

    # Resolve operators to qualified method names
    # This is a simplified approach - full type inference would require AST traversal

    # Find binary operators with context
    # Pattern: identifier operator identifier
    binary_op_pattern = r'([a-z_][a-z0-9_]*)\s*([+\-*/%]|>=?|<=?)\s*([a-z_][a-z0-9_]*)'
    for match in re.finditer(binary_op_pattern, text):
        left_var = match.group(1)
        operator = match.group(2)
        right_var = match.group(3)

        # Try to infer the type of the left operand
        left_type = ctx.get_type(left_var)

        if left_type:
            qualified = resolve_operator_type(operator, left_type)
            if qualified:
                dependencies.add(qualified)
                dependencies.add(left_type)  # Add the type itself

    # Find method calls on variables: variable.method(...)
    method_call_pattern = r'([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\s*\('
    for match in re.finditer(method_call_pattern, text):
        var_name = match.group(1)
        method_name = match.group(2)

        var_type = ctx.get_type(var_name)
        if var_type:
            dependencies.add(var_type)
            dependencies.add(f"{var_type}.{method_name}")

    # Find property access: variable.property (not followed by '(')
    property_pattern = r'([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)(?!\s*\()'
    for match in re.finditer(property_pattern, text):
        var_name = match.group(1)
        prop_name = match.group(2)

        var_type = ctx.get_type(var_name)
        if var_type:
            dependencies.add(var_type)
            dependencies.add(f"{var_type}.{prop_name}")

    # Find standalone function calls: function_name(...)
    # These are lowercase identifiers followed by '(' that aren't method calls
    # Pattern: word boundary, lowercase identifier, optional whitespace, opening paren
    # But NOT preceded by a dot (which would make it a method call)
    func_call_pattern = r'(?<!\.)(?<![A-Za-z0-9_])([a-z_][a-z0-9_]*)\s*\('
    for match in re.finditer(func_call_pattern, text):
        func_name = match.group(1)
        # Skip common keywords and known variables
        if (func_name not in {'if', 'while', 'for', 'match', 'forall', 'exists', 'let', 'satisfy'}
            and func_name not in ctx.variables):
            # Also skip single-letter names (likely variables, not functions)
            if len(func_name) > 1:
                dependencies.add(func_name)

    return dependencies


def extract_theorem_dependencies(name: str, head: str, proof: str, raw: str) -> Set[str]:
    """Extract dependencies from a theorem.

    Args:
        name: Theorem name (not used for extraction)
        head: Theorem head with signature
        proof: Proof body
        raw: Raw source (used for additional context)

    Returns:
        Set of qualified dependencies
    """
    # Combine head and proof for full context
    full_text = f"{head}\n{proof}"

    # Extract signature from head (everything before the body)
    # Pattern: theorem name[params](args) { body }
    sig_match = re.match(r'theorem\s+[a-z_][a-z0-9_]*(?:\[[^\]]+\])?\s*\([^)]*\)', head)
    signature = sig_match.group(0) if sig_match else head

    return extract_dependencies_with_types(full_text, signature)


def extract_definition_dependencies(name: str, body: str) -> Set[str]:
    """Extract dependencies from a definition.

    Args:
        name: Definition name (not used for extraction)
        body: Definition body

    Returns:
        Set of qualified dependencies
    """
    # Extract signature from body
    # Pattern: define/inductive/etc name(params) -> ReturnType { body }
    sig_match = re.match(r'(?:define|inductive|structure|typeclass)\s+[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?\s*(?:\([^)]*\))?(?:\s*->\s*[A-Za-z0-9_<>\[\]]+)?', body)
    signature = sig_match.group(0) if sig_match else ""

    return extract_dependencies_with_types(body, signature)
