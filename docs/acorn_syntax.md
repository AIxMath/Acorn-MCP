# Acorn Syntax Reference

This file distills the canonical Acorn syntax rules from `acorn_background.md` into a quick reference. Use it for linting, validation, and editor support.

## Lexical Basics
- File extension: `.ac`
- One statement per line; line breaks are ignored inside `()` or immediately after infix operators.
- Block delimiters: `{ ... }`
- Comments: `// line comment` or `/* multi-line comment */`
- Built-in literals: `true`, `false`, numerals (type chosen by the active `numerals` declaration).

## Naming Rules
- Modules: lowercase alphanumeric plus `_`; filename = module name + `.ac`.
- Types, theorems, structures, inductives, typeclasses: `PascalCase` (start uppercase).
- Functions/definitions: `camelCase` (start lowercase).
- Variables: start lowercase.
- Type parameters: usually single uppercase letters in brackets, e.g., `List[T]`.

## Imports and Numerals
```acorn
import nat
from nat import Nat, divides
numerals Nat  // selects the type for numerals like 0,1,2
```

## Core Declarations
- **Inductive type**
  ```acorn
  inductive TypeName {
      ctor1
      ctor2(ArgType)
  }
  ```
- **Structure**
  ```acorn
  structure TypeName {
      field1: Type1
      field2: Type2
  }
  ```
- **Attributes / methods**
  ```acorn
  attributes TypeName {
      let constant = value
      define method(self, x: T) -> U { expression }
  }
  ```
- **Typeclass + instance**
  ```acorn
  typeclass M: ClassName {
      op: (M, M) -> M
      law(a: M, b: M) { op(a,b) = op(b,a) }
  }

  instance TypeName: ClassName {
      let op = impl
  }
  ```
- **Functions**
  ```acorn
  define fname(a: A, b: B) -> R { expression }
  let square: Nat -> Nat = function(n: Nat) { n * n }
  ```
- **Variables**
  ```acorn
  let name: Type = expr
  let name: Type satisfy { condition }
  let (a: A, b: B) satisfy { constraint }
  ```
- **Theorems**
  ```acorn
  theorem Name(args) { conclusion }
  theorem Name(args) { conclusion } by { proof_steps }
  theorem { 2 + 2 = 4 }
  ```

## Expressions and Control
- Arithmetic and boolean infix operators: `+ - * / % and or not implies = != < <= > >=`
- Conditional expression: `if condition { expr } else { expr }`
- Proof branches / case analysis use `if ... { ... } else { ... }`
- Pattern matching:
  ```acorn
  match value {
      Ctor(args) { body }
      Ctor2 { body }
  }
  ```
- Quantifiers:
  ```acorn
  exists(x: T) { predicate }
  forall(x: T) { predicate }
  ```

## Operator Methods
Map attribute names to operators: `add -> +`, `sub -> -`, `mul -> *`, `div -> /`, `mod -> %`, `neg -> -` (unary), `gt -> >`, `lt -> <`, `gte -> >=`, `lte -> <=`.

## Common Types (stdlib)
`Bool`, `Nat`, `Int`, `Rat`, `Real`, `Complex`, `List[T]`, `Set[K]`, `Option[T]`, `Pair[T,U]` plus the algebraic hierarchy (`Semigroup`, `Monoid`, `Group`, `Ring`, `Field`, `MetricSpace`, etc.).

## Structural/Typing Rules to Remember
- All binders and parameters require explicit type annotations.
- Numerals require an active `numerals` declaration to choose their type.
- `Nat` subtraction is bounded at zero; division by zero returns zero for totality.
- No LaTeX syntax; stay within Acorn keywords and operators.
- Avoid circular module dependencies; only standard library imports are currently supported.

This reference is intentionally concise; see `acorn_background.md` for the authoritative, full description.
