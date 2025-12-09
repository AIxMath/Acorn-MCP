# Acorn Formal Language - Complete Background Knowledge

This document provides comprehensive information about the Acorn formal language for AI-powered translation of mathematical structures.

## Overview

Acorn is a theorem prover designed to make formal mathematics accessible. It uses AI to verify proofs and is line-oriented with strong static typing. File extension: `.ac`

**Key Philosophy**: You express WHAT is true, not WHY it's true. The AI fills in the tactics and detailed reasoning during verification.

## Critical Differences from Mathematical Notation

1. **No LaTeX syntax** - Use Acorn's own syntax, not mathematical notation
2. **Explicit types required** - All variables must have type annotations
3. **Classical logic** - Law of excluded middle is built-in (non-constructive)
4. **Axiom of choice** - Skolemization is built into the kernel
5. **No Curry-Howard** - Proofs and types are separate; typechecking happens before proving

## File Structure and Imports

### Import Syntax
```acorn
// Import entire module
import nat
theorem example(n: nat.Nat) {
    nat.divides(2, n) or nat.divides(2, n + 1)
}

// Import specific items
from nat import Nat, divides
numerals Nat  // Makes numerals like 0, 1, 2 use this type

theorem example(n: Nat) {
    divides(2, n) or divides(2, n + 1)
}
```

### Module System
- Module names: lowercase, alphanumeric + underscore
- File name = module name + `.ac`
- Currently: can only import from standard library
- Use `problem { ... }` blocks to prevent exports

## Basic Syntax

### Comments
```acorn
// Single-line comment
/* Multi-line
   comment */
```

### Line Breaks
- One statement per line (line-oriented)
- Line breaks ignored inside `()` or after infix operators
- Blocks use `{ ... }` braces

## Types and Type System

### Type Names
- Type names: Start with **uppercase** letter (e.g., `Nat`, `Real`, `Bool`)
- Variable names: Start with **lowercase** letter (e.g., `n`, `x`, `epsilon`)

### Built-in Types
```acorn
Bool       // true, false
Nat        // Natural numbers: 0, 1, 2, ...
Int        // Integers: ..., -1, 0, 1, ...
Rat        // Rational numbers (fractions)
Real       // Real numbers (Dedekind cuts)
Complex    // Complex numbers (re + im*i)
```

### Function Types
```acorn
Nat -> Nat              // Single argument
(Nat, Nat) -> Nat       // Multiple arguments
Nat -> (Nat -> Nat)     // Curried (same as above)
T -> Bool               // Predicate on type T
```

### Generic Types
```acorn
List[T]           // List of T
Set[K]            // Set with elements of type K
Option[T]         // Optional value of type T
Pair[T, U]        // Pair of T and U
```

## Standard Library Types and Operations

### Natural Numbers (Nat)
```acorn
from nat import Nat
numerals Nat

// Constructors
Nat.0              // Zero
n.suc              // Successor of n (n+1)

// Operations
a + b              // Addition
a * b              // Multiplication
a - b              // Bounded subtraction (caps at 0!)
a < b, a <= b      // Comparison
a.divides(b)       // True if a divides b
a.is_prime         // True if a is prime
a.factorial        // Factorial
a.exp(b)           // Exponentiation (a^b)
```

### Integers (Int)
```acorn
from int import Int
numerals Int

// Constructors
Int.from_nat(n)    // Natural to integer
Int.neg_suc(n)     // -(n+1) for negative integers

// Operations
a + b, a - b, a * b
a.abs              // Absolute value
a.is_positive, a.is_negative
a <= b, a < b
a.divides(b)
a.exp(b)
```

### Rational Numbers (Rat)
```acorn
from rat import Rat
numerals Rat

// Construction
Rat.new(num, denom)      // Creates reduced fraction
Rat.from_int(n)          // Integer to rational
Rat.from_nat(n)          // Natural to rational

// Operations
a + b, a - b, a * b, a / b
a.reciprocal             // 1/a (returns 0 for 0)
a.abs
a.is_positive, a.is_negative
a <= b, a < b
a.is_close(b, eps)       // |a - b| < eps
```

### Real Numbers (Real)
```acorn
from real import Real
numerals Real

// Construction (via Dedekind cuts)
Real.from_rat(r)
Real.from_int(n)

// Operations
a + b, a - b, a * b, a / b
a.reciprocal             // Returns 0 for 0
a.abs
a.is_positive, a.is_negative
a <= b, a < b
a.is_close(b, eps)
```

### Complex Numbers (Complex)
```acorn
from complex import Complex

// Construction
Complex.new(re, im)      // re + im*i
Complex.from_real(r)     // Real to complex
Complex.i                // Imaginary unit (i² = -1)

// Operations
z + w, z - w, z * w, z / w
z.conj                   // Complex conjugate
z.abs_squared            // |z|²
z.reciprocal
z.is_real, z.is_imaginary
```

### Lists
```acorn
from list import List

// Construction
List.nil[T]              // Empty list
List.cons(head, tail)    // Prepend element
List.singleton(x)        // Single-element list

// Operations
xs.length
xs.append(x)             // Add to end
xs + ys                  // Concatenation
xs.contains(x)           // Membership
xs.map(f)                // Apply function
xs.filter(f)             // Keep elements where f is true
xs.unique                // Remove duplicates
```

### Sets
```acorn
from set import Set

// Construction
Set.new(contains_fun)    // From membership function
Set.singleton(x)         // {x}
Set.empty_set[K]         // ∅
Set.universal_set[K]     // All elements of type K

// Operations
s.contains(x)            // x ∈ s
s.union(t)               // s ∪ t
s.intersection(t)        // s ∩ t
s.difference(t)          // s \ t
s.c                      // Complement
s.subset(t)              // s ⊆ t
s.is_empty
```

## Defining Structures

### Inductive Types
```acorn
inductive TypeName {
    constructor1
    constructor2(ArgType)
    constructor3(Nat, TypeName)  // Can be recursive
}

// Example: Natural numbers
inductive Nat {
    0
    suc(Nat)
}

// Example: Binary tree
inductive Tree {
    leaf(Nat)
    node(Tree, Tree)
}

// Generic inductive type
inductive List[T] {
    nil
    cons(T, List[T])
}
```

**Automatic induction principle**: When you define an inductive type, Acorn automatically creates an induction theorem for it.

### Structure Types
```acorn
structure TypeName {
    field1: Type1
    field2: Type2
}

// Example
structure LatticePoint {
    x: Int
    y: Int
}

// Generic structure
structure Pair[T, U] {
    first: T
    second: U
}

// With constraints
structure OrderedIntPair {
    first: Int
    second: Int
} constraint {
    first <= second
} by {
    // Proof that constraint is satisfiable
    let first: Int = 0
    let second: Int = 1
    first <= second
}
```

**Automatic methods**:
- `TypeName.new(arg1, arg2)` - Constructor
- `obj.field1`, `obj.field2` - Field accessors

## Defining Functions and Variables

### Simple Functions
```acorn
define function_name(arg1: Type1, arg2: Type2) -> ReturnType {
    expression
}

// Example
define square(n: Nat) -> Nat {
    n * n
}

// Predicate (function returning Bool)
define is_even(n: Nat) -> Bool {
    exists(d: Nat) { 2 * d = n }
}
```

### Anonymous Functions
```acorn
let square: Nat -> Nat = function(n: Nat) {
    n * n
}
```

### Functions with Match
```acorn
define is_three_leaf(t: Tree) -> Bool {
    match t {
        Tree.leaf(n) {
            n = 3
        }
        Tree.node(left, right) {
            false
        }
    }
}
```

### Recursive Functions
```acorn
define reverse(t: Tree) -> Tree {
    match t {
        Tree.leaf(k) {
            Tree.leaf(k)
        }
        Tree.node(left, right) {
            Tree.node(reverse(right), reverse(left))
        }
    }
}
```

### Let-Satisfy (Functional Specification)
```acorn
let function_name(arg: Type) -> ret: ReturnType satisfy {
    condition_using_arg_and_ret
} by {
    proof_that_such_ret_exists
}

// Example: Predecessor function
let predecessor(n: Nat) -> p: Nat satisfy {
    if n = 0 {
        p = 0
    } else {
        p.suc = n
    }
}
```

### Simple Variables
```acorn
let name: Type = expression

// Examples
let two: Nat = 2
let origin: LatticePoint = LatticePoint.new(0, 0)
```

### Variables with Satisfaction
```acorn
let name: Type satisfy {
    condition
}

// Example
let n: Nat satisfy {
    exists(d: Nat) { 2 * d = n }
}

// Multiple variables
let (a: Nat, b: Nat) satisfy {
    a + b = 10
}
```

## Attributes

Add methods and constants to existing types:

```acorn
attributes TypeName {
    let constant_name = value

    define method_name(self, other: OtherType) -> ReturnType {
        expression
    }
}

// Example
attributes LatticePoint {
    let origin = LatticePoint.new(0, 0)

    define swap(self) -> LatticePoint {
        LatticePoint.new(self.y, self.x)
    }
}

// Generic attributes
attributes List[T] {
    define contains(self, item: T) -> Bool {
        match self {
            List.nil { false }
            List.cons(head, tail) {
                if head = item { true } else { tail.contains(item) }
            }
        }
    }
}
```

### Operators as Attributes
```acorn
attributes LatticePoint {
    define add(self, other: LatticePoint) -> LatticePoint {
        LatticePoint.new(self.x + other.x, self.y + other.y)
    }
}

// Now can use: p1 + p2
```

**Operator names**:
- `add` → `+`
- `sub` → `-`
- `mul` → `*`
- `div` → `/`
- `mod` → `%`
- `neg` → unary `-`
- `gt` → `>`
- `lt` → `<`
- `gte` → `>=`
- `lte` → `<=`

## Theorems and Proofs

### Basic Theorem
```acorn
theorem theorem_name(arg1: Type1, arg2: Type2) {
    statement
}

// Example
theorem add_commutes(a: Nat, b: Nat) {
    a + b = b + a
}
```

### Theorem with Proof
```acorn
theorem theorem_name(args) {
    conclusion
} by {
    step1
    step2
    step3
}

// Example
theorem threeven_plus_three(n: Nat) {
    threeven(n) implies threeven(n + 3)
} by {
    let d: Nat satisfy { 3 * d = n }
    3 * (d + 1) = n + 3
}
```

### Anonymous Theorems
```acorn
theorem {
    2 + 2 = 4
}
```

## Quantifiers

### Existential Quantifier
```acorn
exists(x: Type) {
    property
}

// Multiple variables
exists(a: Nat, b: Nat) {
    a + b = 10
}

// Higher-order
exists(f: Nat -> Nat) {
    forall(n: Nat) { f(n) > n }
}
```

### Universal Quantifier
```acorn
forall(x: Type) {
    property
}

// Example
forall(n: Nat) {
    n + 0 = n
}
```

### Forall as Statement (Multi-step)
```acorn
forall(x: Type) {
    step1
    step2
    conclusion
}
// Outside the block, can use: forall(x: Type) { conclusion }
```

## Control Flow

### If-Else Expressions
```acorn
let result = if condition {
    value_if_true
} else {
    value_if_false
}

// Example
let max = if a < b { b } else { a }
```

### If Statements (Proof)
```acorn
if condition {
    step1
    step2
    conclusion
}
// Outside: can use (condition implies conclusion)

// Proof by contradiction
if condition {
    step1
    step2
    false  // Proven contradiction
}
// Outside: can use (not condition)
```

### If-Else Statements (Case Analysis)
```acorn
if case1 {
    proof_of_goal_assuming_case1
} else {
    proof_of_goal_assuming_not_case1
}
// Outside: goal is proven
```

### Match Expressions
```acorn
match value {
    Constructor1(args) {
        expression1
    }
    Constructor2 {
        expression2
    }
}
```

### Match Statements (Proof)
```acorn
match value {
    Constructor1(args) {
        steps_for_case1
        goal
    }
    Constructor2 {
        steps_for_case2
        goal
    }
}
// Outside: goal is proven
```

## Induction

Induction is **automatic** - no special syntax needed. Just prove:
1. Base case
2. Inductive step

The AI will apply induction automatically.

```acorn
theorem reverse_reverse(t: Tree) {
    reverse(reverse(t)) = t
} by {
    // Base case
    forall(k: Nat) {
        reverse_reverse(Tree.leaf(k))
    }

    // Inductive step
    forall(a: Tree, b: Tree) {
        if reverse_reverse(a) and reverse_reverse(b) {
            reverse(reverse(Tree.node(a, b))) = Tree.node(a, b)
            reverse_reverse(Tree.node(a, b))
        }
    }
}
```

**Self-reference in proofs**: Inside a theorem's proof, the theorem name refers to a function that returns `Bool` (not yet proven true).

## Generics

### Generic Types
```acorn
structure Pair[T, U] {
    first: T
    second: U
}

inductive List[T] {
    nil
    cons(T, List[T])
}
```

### Generic Functions
```acorn
define identity[T](x: T) -> T {
    x
}

// Type parameters usually inferred
let five: Nat = identity(5)  // Don't need identity[Nat](5)
```

### Generic Theorems
```acorn
theorem swap_involutive[T](p: Pair[T, T]) {
    p.swap.swap = p
}
```

### Generic Variables
```acorn
let is_finite[T]: Bool = exists(xs: List[T]) {
    forall(x: T) { xs.contains(x) }
}
```

## Typeclasses

Define abstract interfaces with required operations and laws:

```acorn
typeclass M: MetricSpace {
    distance: (M, M) -> Real

    self_distance_is_zero(x: M) {
        x.distance(x) = 0
    }

    dist_zero_imp_eq(x: M, y: M) {
        x.distance(y) = 0 implies x = y
    }

    symmetric(x: M, y: M) {
        x.distance(y) = y.distance(x)
    }

    triangle(x: M, y: M, z: M) {
        x.distance(z) <= x.distance(y) + y.distance(z)
    }
}
```

### Extending Typeclasses
```acorn
typeclass S: Semigroup {
    mul: (S, S) -> S
    mul_associative(a: S, b: S, c: S) {
        a * (b * c) = (a * b) * c
    }
}

typeclass M: Monoid extends Semigroup {
    1: M
    mul_identity_left(a: M) { M.1 * a = a }
    mul_identity_right(a: M) { a * M.1 = a }
}
```

### Instance Declarations
```acorn
instance TypeName: TypeclassName {
    let attribute1: Type1 = value1
    let attribute2: Type2 = value2
}

// Example
define discrete(x: Color, y: Color) -> Real {
    if x = y { 0 } else { 1 }
}

instance Color: MetricSpace {
    let distance: (Color, Color) -> Real = discrete
}
```

### Using Typeclasses in Theorems
```acorn
theorem distance_non_negative[M: MetricSpace](x: M, y: M) {
    not x.distance(y).is_negative
}
```

## Common Algebraic Structures (Standard Library)

### Hierarchy
```
Semigroup → Monoid → Group → CommGroup
AddSemigroup → AddMonoid → AddGroup → AddCommGroup
Semiring → Ring → CommRing → Field
PartialOrder → LinearOrder
```

### Key Typeclasses
- `Semigroup`: Has `mul`, associative
- `Monoid`: Semigroup + identity (`1`)
- `Group`: Monoid + inverses
- `CommGroup`: Commutative group
- `Ring`: AddCommGroup + Monoid + distributivity
- `Field`: CommRing + multiplicative inverses
- `LinearOrder`: Total order (all elements comparable)
- `MetricSpace`: Distance function

## Logical Operators

```acorn
// Boolean operators
p and q
p or q
not p
p implies q

// Equality and inequality
a = b
a != b

// Comparisons (if type has LinearOrder)
a < b
a <= b
a > b
a >= b

// Set membership
x.contains(element)  // or s.contains(x)
```

## Common Patterns

### Defining Predicates
```acorn
define is_even(n: Nat) -> Bool {
    exists(d: Nat) { 2 * d = n }
}

define is_prime(n: Nat) -> Bool {
    1 < n and not n.is_composite
}
```

### Case Analysis
```acorn
let (q: Nat, r: Nat) satisfy {
    r < 2 and n = q * 2 + r
}
if r = 0 {
    // n is even
} else {
    r = 1
    // n is odd
}
```

### Currying
```acorn
define add(a: Nat, b: Nat) -> Nat { a + b }

let add_five: Nat -> Nat = add(5)
// add_five(3) = 8
```

## Important Rules and Conventions

### Naming Conventions
- **Types**: PascalCase (`NaturalNumber`, `MetricSpace`)
- **Functions/definitions**: camelCase (`isEven`, `factorial`)
- **Theorems**: PascalCase (`FundamentalTheoremOfCalculus`)
- **Variables**: lowercase (`x`, `n`, `epsilon`)

### Critical Don'ts
1. **Don't use LaTeX notation** - Use Acorn syntax
2. **Don't redefine stdlib types** - Import `Nat`, `Real`, etc.
3. **Don't create circular dependencies** - A can't depend on B if B depends on A
4. **Don't use -i flags** - No interactive commands (git rebase -i, etc.)
5. **Don't forget type annotations** - Type inference is limited
6. **Don't mix typeclass and type attributes** - `x.distance(y)` works for `x: M` where `M: MetricSpace`, not for specific types

### Division by Zero Convention
In Acorn, division by zero returns zero (makes functions total):
```acorn
Real.0.reciprocal = Real.0
Rat.0.reciprocal = Rat.0
// Division a / b is defined as a * b.reciprocal
```

### Bounded Subtraction on Nat
```acorn
// Natural number subtraction caps at zero
5 - 3 = 2
3 - 5 = 0  // Not negative!
```

## Proof Techniques

### Direct Proof
```acorn
theorem name(args) {
    conclusion
} by {
    step1
    step2
    conclusion
}
```

### Proof by Contradiction
```acorn
if claim {
    derivation
    false  // Contradiction
}
// Outside: not claim
```

### Proof by Cases
```acorn
if case1 {
    goal_from_case1
} else {
    goal_from_not_case1
}
```

### Proof by Induction
```acorn
// Base case
goal(base_value)

// Inductive step
forall(k: Type) {
    if goal(k) {
        goal(k.successor)
    }
}
```

## Example: Complete Acorn File

```acorn
from nat import Nat
numerals Nat

// Define a predicate
define is_even(n: Nat) -> Bool {
    exists(k: Nat) { 2 * k = n }
}

// Simple theorem
theorem zero_is_even {
    is_even(0)
}

// Theorem with proof
theorem even_plus_two(n: Nat) {
    is_even(n) implies is_even(n + 2)
} by {
    let k: Nat satisfy { 2 * k = n }
    2 * (k + 1) = n + 2
}

// Theorem with induction
theorem even_or_odd(n: Nat) {
    is_even(n) or is_even(n + 1)
} by {
    // Base case
    is_even(0)
    is_even(0) or is_even(1)

    // Inductive step
    forall(m: Nat) {
        if is_even(m) or is_even(m + 1) {
            if is_even(m) {
                is_even(m + 2)
                is_even(m + 1) or is_even(m + 2)
            } else {
                is_even(m + 1)
                is_even(m + 1) or is_even(m + 2)
            }
        }
    }
}
```

## Compilation and Verification

Acorn has two phases:

1. **Compilation**: Check syntax, types, name resolution
   - Red squiggles = compilation errors
   - Must fix these first

2. **Proving**: Search for proofs of statements
   - Yellow squiggles = can't find proof
   - Need to add more steps or detail

## Key Differences from Other Provers

### vs. Lean/Coq
- **No tactics** - You write steps, AI finds proofs
- **Classical logic** - LEM and AC built-in
- **No Curry-Howard** - Proofs ≠ programs
- **AI-assisted** - Don't specify proof strategies

### vs. Isabelle
- **Line-oriented** - One thing per line
- **Strong typing** - All types explicit
- **Simpler syntax** - Fewer keywords

### Design Philosophy
"You write WHAT is true. The AI figures out WHY it's true."

---

## Translation Guidelines

When translating mathematical structures to Acorn:

1. **Use stdlib types**: Import `Nat`, `Real`, `Set`, etc. Never redefine them.

2. **Be explicit with types**: All variables need type annotations.

3. **Match structure to Acorn construct**:
   - Axiom → `theorem` with no proof (or `axiom` keyword)
   - Definition → `define` or `structure`
   - Theorem → `theorem` with optional `by` proof
   - Lemma → `theorem` (no distinction)
   - Proposition → `theorem`

4. **Handle dependencies**: If structure A uses B, make sure to reference it correctly.

5. **Translate quantifiers carefully**:
   - "For all x ∈ ℕ" → `forall(x: Nat)`
   - "There exists x ∈ ℝ" → `exists(x: Real)`
   - "For all x, y" → `forall(x: Type, y: Type)`

6. **Translate notation**:
   - "x ∈ S" → `S.contains(x)`
   - "A ⊆ B" → `A.subset(B)`
   - "f: X → Y" → `f: X -> Y`
   - "|x|" → `x.abs`
   - "x⁻¹" → `x.inverse` or `x.reciprocal`

7. **Break down complex statements**: If a theorem is complex, split it into steps in the `by` block.

8. **Use match for case analysis**: When mathematical proof has cases, use `match` or `if-else`.

9. **Trust the standard library**: Many properties (commutativity, associativity, etc.) are already proven for stdlib types.

10. **Remember proof strategies**:
    - Induction: prove base + inductive step
    - Contradiction: assume negation, derive `false`
    - Cases: use `if-else` or `match`

---

**This is the complete, accurate Acorn language specification. When translating, follow these rules exactly.**
