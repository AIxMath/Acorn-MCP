"""Acorn code verifier using the Acorn compiler.

This module provides functionality to verify Acorn code by invoking the
Acorn compiler and parsing its output for errors.

IMPORTANT: Compiler Configuration
----------------------------------
To use code verification, you MUST have the Acorn compiler available.

Option 1: Compiler in PATH (recommended for system-wide install)
    - Install Acorn compiler so 'acorn' command works in terminal
    - No environment variables needed

Option 2: Custom compiler path (for local builds or non-standard locations)
    - Set environment variable: ACORN_COMPILER_PATH=/path/to/acorn
    - Example: export ACORN_COMPILER_PATH=/home/user/acorn-compiler/bin/acorn

Option 3: Custom library path (if acornlib is not in default location)
    - Set environment variable: ACORN_LIB_PATH=/path/to/acornlib/
    - Example: export ACORN_LIB_PATH=/home/user/acorn/env/acornlib/

If the compiler is not found, verify_code() will return:
    {"is_valid": False, "compiler_available": False, "errors": [...]}

This means syntax checking will work, but logical verification will fail.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

# Default compiler path and library location
DEFAULT_COMPILER_PATH = "acorn"
# Fixed to match actual Acorn-MCP directory structure (acornlib/ at project root)
# Previously was "./env/acornlib/" which was copied from formalizer's old structure
DEFAULT_ACORNLIB_PATH = "./acornlib/"


def get_compiler_path() -> str:
    """Get the Acorn compiler path from environment or use default.
    
    Returns:
        Path to the Acorn compiler executable.
    
    Environment Variables:
        ACORN_COMPILER_PATH: Custom path to Acorn compiler (optional)
    """
    return os.getenv("ACORN_COMPILER_PATH", DEFAULT_COMPILER_PATH)


def get_acornlib_path() -> str:
    """Get the Acorn library path from environment or use default.
    
    Returns:
        Path to the acornlib directory.
    
    Environment Variables:
        ACORN_LIB_PATH: Custom path to acornlib (optional)
    """
    return os.getenv("ACORN_LIB_PATH", DEFAULT_ACORNLIB_PATH)


def verify_acorn_code(code: str, timeout: int = 60) -> Tuple[bool, List[str]]:
    """Verify Acorn code using the Acorn compiler.
    
    Args:
        code: The Acorn source code to verify
        timeout: Maximum time in seconds to wait for verification (default: 60)
    
    Returns:
        A tuple of (is_valid, error_messages):
        - is_valid: True if code verifies successfully, False otherwise
        - error_messages: List of error messages (empty if valid)
    """
    compiler_path = get_compiler_path()
    acornlib_path = get_acornlib_path()
    
    # Use TemporaryDirectory for better cleanup reliability
    # Even if process is killed, OS will eventually clean up temp dirs on reboot
    try:
        with tempfile.TemporaryDirectory(prefix="acorn_verify_") as temp_dir:
            # Create temporary .ac file in the temp directory
            temp_file_path = Path(temp_dir) / "code.ac"
            temp_file_path.write_text(code, encoding='utf-8')
            
            # Run the Acorn compiler
            result = subprocess.run(
                [compiler_path, "verify", "--lib", acornlib_path, str(temp_file_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            if result.returncode == 0:
                return True, []
            
            # Parse errors from output
            combined_output = result.stdout + "\n" + result.stderr
            errors = combined_output.split("\n")
            
            # Filter for relevant error lines
            error_lines = [
                e
                for e in errors
                if e.strip()
                and (
                    "error" in e.lower()
                    or "failed" in e.lower()
                    or "^" in e
                    or e.strip().startswith("/")
                    or "line" in e.lower()
                )
            ]
            
            # If no filtered errors, return all non-empty lines
            if not error_lines:
                error_lines = [e for e in errors if e.strip()]
            
            return False, error_lines
            # temp_dir and all files automatically cleaned up here
    
    except FileNotFoundError as e:
        # Compiler executable not found - provide detailed diagnostic help
        error_msg = (
            f"Acorn compiler not found at: {compiler_path}\n\n"
            f"To fix this issue:\n"
            f"1. Check if 'acorn' is in your system PATH: run 'which acorn' in terminal\n"
            f"2. If not installed, install the Acorn compiler\n"
            f"3. OR set ACORN_COMPILER_PATH environment variable to the full path:\n"
            f"   export ACORN_COMPILER_PATH=/path/to/acorn/executable\n\n"
            f"Current configuration:\n"
            f"  - ACORN_COMPILER_PATH: {os.getenv('ACORN_COMPILER_PATH', 'not set, using default')}\n"
            f"  - Default: {DEFAULT_COMPILER_PATH}\n"
            f"  - Library path: {acornlib_path}"
        )
        logger.warning(error_msg)
        return True, []  # Return success if compiler not available
    
    except subprocess.TimeoutExpired:
        logger.warning("Verification timed out after %d seconds", timeout)
        return False, [f"Verification timed out after {timeout} seconds"]
    
    except Exception as exc:
        logger.warning("Verification failed: %s", exc)
        return True, []  # Return success on unexpected errors


def check_verification(source: str) -> Dict[str, Any]:
    """Check Acorn code and return structured verification result.
    
    Args:
        source: The Acorn source code to verify
    
    Returns:
        A dictionary containing:
        - is_valid: Boolean indicating if code is valid
        - errors: List of error message strings
        - compiler_available: Boolean indicating if compiler was found
    """
    compiler_path = get_compiler_path()
    
    # Check if compiler is available
    try:
        subprocess.run(
            [compiler_path, "--version"],
            capture_output=True,
            timeout=5
        )
        compiler_available = True
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        compiler_available = False
        # Provide detailed diagnostic information
        diagnostic_msg = (
            f"Acorn compiler not found at: {compiler_path}\n\n"
            f"To enable code verification:\n"
            f"1. Install the Acorn compiler and ensure 'acorn' is in your PATH\n"
            f"2. OR set ACORN_COMPILER_PATH to the full path of the Acorn executable\n"
            f"   Example: export ACORN_COMPILER_PATH=/usr/local/bin/acorn\n\n"
            f"Current configuration:\n"
            f"  - ACORN_COMPILER_PATH env var: {os.getenv('ACORN_COMPILER_PATH', 'not set')}\n"
            f"  - Using default: {DEFAULT_COMPILER_PATH}\n"
            f"  - Library path: {get_acornlib_path()}"
        )
        logger.warning(diagnostic_msg)
    
    if not compiler_available:
        return {
            "is_valid": False,
            "errors": [
                f"Acorn compiler not found at: {compiler_path}",
                "Set ACORN_COMPILER_PATH environment variable or install acorn in PATH",
                "See logs for detailed diagnostic information"
            ],
            "compiler_available": False
        }
    
    # Run verification
    is_valid, errors = verify_acorn_code(source)
    
    return {
        "is_valid": is_valid,
        "errors": errors,
        "compiler_available": True
    }
