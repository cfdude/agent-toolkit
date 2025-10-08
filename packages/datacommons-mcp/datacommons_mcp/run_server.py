#!/usr/bin/env python3
"""
Entry point for Claude Desktop extension mode.

This module handles API key configuration from Claude Desktop UI and starts the MCP server.
Separate from cli.py to maintain backward compatibility with CLI usage modes.
"""

import os
import subprocess
import sys
from pathlib import Path


def ensure_dependencies() -> None:
    """
    Ensure required dependencies are installed and compatible with current Python version.

    If bundled dependencies are incompatible (wrong Python version), install them
    to a user-specific cache directory.
    """
    # Try importing pydantic_core to check if bundled dependencies work
    try:
        import pydantic_core  # noqa: F401
        # If import succeeds, bundled dependencies are compatible
        return
    except (ImportError, ModuleNotFoundError) as e:
        # Bundled dependencies are missing or incompatible with this Python version
        print(
            f"Bundled dependencies incompatible with Python {sys.version_info.major}.{sys.version_info.minor}: {e}",
            file=sys.stderr,
        )
        print("Installing compatible dependencies...", file=sys.stderr)

        # Create user-specific cache directory for this Python version
        cache_dir = Path.home() / ".cache" / "datacommons-mcp" / f"py{sys.version_info.major}{sys.version_info.minor}"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Check if already installed in cache
        if (cache_dir / "pydantic_core").exists():
            # Add cache to path and try again
            sys.path.insert(0, str(cache_dir))
            try:
                import pydantic_core  # noqa: F401
                print(f"✓ Using cached dependencies from {cache_dir}", file=sys.stderr)
                return
            except (ImportError, ModuleNotFoundError):
                # Cache is corrupted, reinstall
                print("Cache corrupted, reinstalling...", file=sys.stderr)

        # Install dependencies to cache
        packages = [
            "fastmcp>=2.12.4",
            "requests>=2.32.0",
            "datacommons-client>=2.1.0",
            "pydantic>=2.11.0",
            "pydantic-settings>=2.11.0",
            "python-dateutil>=2.9.0",
        ]

        try:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--target",
                    str(cache_dir),
                    "--upgrade",
                    "--quiet",
                ] + packages,
                stderr=subprocess.PIPE,
            )

            # Add cache to path
            sys.path.insert(0, str(cache_dir))

            # Verify installation
            import pydantic_core  # noqa: F401
            print(f"✓ Dependencies installed successfully to {cache_dir}", file=sys.stderr)

        except subprocess.CalledProcessError as install_error:
            print(
                f"ERROR: Failed to install dependencies: {install_error}",
                file=sys.stderr,
            )
            print(
                "Please ensure 'pip' is available in your Python installation.",
                file=sys.stderr,
            )
            sys.exit(1)


def main() -> None:
    """
    Initialize and run the DataCommons MCP server in extension mode.

    Validates API key configuration from environment and starts the FastMCP server.
    Exits with code 1 if API key is not configured.
    """
    # Ensure dependencies are compatible with current Python version
    ensure_dependencies()

    debug_mode = os.environ.get("DC_DEBUG", "").lower() in ("1", "true", "yes")

    # Debug logging (opt-in only)
    if debug_mode:
        print("=" * 60, file=sys.stderr)
        print("DataCommons MCP Server - Debug Mode", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"Command line args: {sys.argv}", file=sys.stderr)
        print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'not set')}", file=sys.stderr)

    # Get and validate API key
    api_key_raw = os.environ.get("DC_API_KEY", "")
    api_key = api_key_raw.strip()  # Strip whitespace

    if debug_mode and api_key_raw != api_key:
        print(
            f"Stripped whitespace from API key ({len(api_key_raw)} → {len(api_key)} chars)",
            file=sys.stderr,
        )

    # Check for unsubstituted variable placeholders
    if api_key and api_key.startswith("$"):
        if debug_mode:
            print(
                f"Warning: DC_API_KEY looks like unsubstituted variable: {api_key}",
                file=sys.stderr,
            )
        api_key = ""  # Treat as not set

    # Validate API key is present
    if not api_key:
        print("\n" + "=" * 60, file=sys.stderr)
        print("ERROR: DC_API_KEY not configured", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            "\nPlease configure your DataCommons API key in Claude Desktop:",
            file=sys.stderr,
        )
        print("  1. Go to Settings → Developer → Extensions", file=sys.stderr)
        print("  2. Find the 'datacommons-mcp' extension", file=sys.stderr)
        print("  3. Click 'Configure' and enter your API key", file=sys.stderr)
        print(
            "  4. Get your API key at: https://apikeys.datacommons.org", file=sys.stderr
        )
        print("=" * 60, file=sys.stderr)
        sys.exit(1)  # Fail fast - better UX than delayed failure

    # Set cleaned API key back to environment
    os.environ["DC_API_KEY"] = api_key

    if debug_mode:
        print(f"✓ DC_API_KEY configured ({len(api_key)} chars)", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

    # Import and run the server
    from datacommons_mcp.server import mcp

    mcp.run()


if __name__ == "__main__":
    main()
