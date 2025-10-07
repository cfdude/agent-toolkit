#!/usr/bin/env python3
"""
Entry point for Claude Desktop extension mode.

This module handles API key configuration from Claude Desktop UI and starts the MCP server.
Separate from cli.py to maintain backward compatibility with CLI usage modes.
"""

import os
import sys


def main() -> None:
    """
    Initialize and run the DataCommons MCP server in extension mode.

    Validates API key configuration from environment and starts the FastMCP server.
    Exits with code 1 if API key is not configured.
    """
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
        print(f"Stripped whitespace from API key ({len(api_key_raw)} → {len(api_key)} chars)", file=sys.stderr)

    # Check for unsubstituted variable placeholders
    if api_key and api_key.startswith("$"):
        if debug_mode:
            print(f"Warning: DC_API_KEY looks like unsubstituted variable: {api_key}", file=sys.stderr)
        api_key = ""  # Treat as not set

    # Validate API key is present
    if not api_key:
        print("\n" + "=" * 60, file=sys.stderr)
        print("ERROR: DC_API_KEY not configured", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nPlease configure your DataCommons API key in Claude Desktop:", file=sys.stderr)
        print("  1. Go to Settings → Developer → Extensions", file=sys.stderr)
        print("  2. Find the 'datacommons-mcp' extension", file=sys.stderr)
        print("  3. Click 'Configure' and enter your API key", file=sys.stderr)
        print("  4. Get your API key at: https://apikeys.datacommons.org", file=sys.stderr)
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
