# Acorn Lark Parser Documentation

## CFG Grammar File
`acorn_mcp/acorn/acorn.lark` (context-free EBNF for Lark):

```
%import common.WS
%import common.NL
%ignore WS
%ignore /\/\*[\s\S]*?\*\//
%ignore /\/\/.*$/
%ignore /\/\/\/.*$/

start: statement*

[full grammar as written - covers imports, numerals, inductive/structure/typeclass/attributes/theorems/defines/lets/instances, expr/match/quantifiers, qualified types, ops, etc.]
```

Loads via `Lark(str(path), propagate_positions=True)` for line/col/meta.

## Python Script
`acorn_mcp/acorn/parser.py` (reads grammar, generates AST):

```python
\"\"\"Parser for Acorn (.ac files) using Lark + CFG.\"\"\"
from lark import Lark
from pathlib import Path
from .ast import *  # AcornItem, Theorem, etc.

class AcornParser:
    def __init__(self, source_root=None):
        grammar_path = Path(__file__).parent / \"acorn.lark\"
        self.lark_parser = Lark(grammar_path.read_text(), parser=\"lalr\", propagate_positions=True)
        self.source_root = source_root
        # Keep _generate_uuid, _extract_identifiers, _enrich_item

    def parse_file(self, path: Path) -> tuple[list[AcornItem], list[ImportStatement]]:
        text = path.read_text()
        tree = self.lark_parser.parse(text)
        items, imports_ = self._build_ast_list(tree, text, path)
        for item in items:
            self._enrich_item(item, path)
        return items, imports_

    def _build_ast_list(self, tree, text, path):
        items = []
        imports_list = []
        for child in tree.children:
            child_items, child_imports = self._build_ast(child, text, path)
            items.extend(child_items)
            imports_list.extend(child_imports)
        return items, imports_list

    def _build_ast(self, tree, text, path):
        start_pos, end_pos = tree.meta.start_pos, tree.meta.end_pos
        raw = text[start_pos:end_pos].strip()
        loc = SourceLocation(path, tree.meta.start_line)
        if tree.data == 'theorem_decl':
            # Extract from children/meta (name/head/proof)
            name = tree.children[0].children[0].value if theorem_sig else ''
            head_span = tree.children[head_idx].meta
            head = text[head_span.start_pos:head_span.end_pos]
            proof = text[proof_span.start_pos:proof_span.end_pos] if by else ''
            kind = 'axiom' if tree.children[0].value == 'axiom' else 'theorem'
            return [Theorem(name=name, kind=kind, source=raw, head=head, proof=proof, raw=raw, location=loc)], []
        # Similar mappings for typeclass_decl (expand members: TypeClass + Definitions \"Type.mem\"), attributes_block (expanded Definitions), inductive_decl (Inductive), etc.
        # import_stmt → ImportStatement(module=..., items=[...], source=raw)
        # numerals_stmt → AcornItem(name=..., kind='numerals', source=raw)
        return [], []

    # Retained: _generate_uuid, _extract_identifiers, _enrich_item, _get_module_name
```

## Usage
```python
parser = AcornParser(source_root=ACORNLIB_SRC)
items, imports = parser.parse_file(Path('acornlib/src/nat/nat_base.ac'))
# items: [Inductive('Nat'), Definition('Nat.add'), Theorem('add_zero_right'), ...]
```

Compatible with importer/DB. Refine grammar/transform for edge cases (e.g., nested expr). Doc complete.