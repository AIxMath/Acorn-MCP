"""Test script to verify database operations."""
import asyncio
from database import (
    init_database,
    add_theorem,
    get_all_theorems,
    add_definition,
    get_all_definitions
)

async def test_database():
    # Initialize database
    await init_database()
    print("✓ Database initialized")
    
    # Add sample theorems
    try:
        await add_theorem(
            "Pythagorean Theorem",
            "In a right triangle, the square of the hypotenuse equals the sum of squares of the other two sides.",
            "Let a and b be the legs and c be the hypotenuse of a right triangle. By the geometric interpretation, we can arrange four copies of the triangle around a square with side length c. The outer square has area (a+b)² and consists of the four triangles (total area 2ab) plus the inner square (area c²). Thus (a+b)² = 4(ab/2) + c², which simplifies to a² + 2ab + b² = 2ab + c², giving a² + b² = c²."
        )
        print("✓ Added Pythagorean Theorem")
    except ValueError as e:
        print(f"  (Theorem already exists: {e})")
    
    try:
        await add_theorem(
            "Fundamental Theorem of Arithmetic",
            "Every integer greater than 1 can be represented uniquely as a product of prime numbers, up to the order of the factors.",
            "The proof proceeds in two parts: existence and uniqueness. Existence follows by strong induction on n. Base case: n=2 is prime. Inductive step: if n is prime, we're done; otherwise n=ab where 1<a,b<n, and by the inductive hypothesis both a and b are products of primes, thus so is n. Uniqueness is proven by contradiction using the fact that if a prime p divides a product ab, then p divides a or p divides b."
        )
        print("✓ Added Fundamental Theorem of Arithmetic")
    except ValueError as e:
        print(f"  (Theorem already exists: {e})")
    
    # Add sample definitions
    try:
        await add_definition(
            "Prime Number",
            "A natural number greater than 1 that has no positive divisors other than 1 and itself. Equivalently, a prime number is a natural number greater than 1 that is not a product of two smaller natural numbers."
        )
        print("✓ Added Prime Number definition")
    except ValueError as e:
        print(f"  (Definition already exists: {e})")
    
    try:
        await add_definition(
            "Group",
            "A set G together with a binary operation • that satisfies four axioms: closure (for all a,b in G, a•b is in G), associativity (for all a,b,c in G, (a•b)•c = a•(b•c)), identity (there exists e in G such that for all a in G, e•a = a•e = a), and inverse (for all a in G, there exists b in G such that a•b = b•a = e)."
        )
        print("✓ Added Group definition")
    except ValueError as e:
        print(f"  (Definition already exists: {e})")
    
    # Verify
    theorems = await get_all_theorems()
    definitions = await get_all_definitions()
    
    print(f"\n✓ Total theorems: {len(theorems)}")
    print(f"✓ Total definitions: {len(definitions)}")
    print("\nTest completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_database())
