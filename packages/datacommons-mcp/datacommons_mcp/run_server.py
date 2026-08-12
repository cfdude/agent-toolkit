#!/usr/bin/env python3
"""
Entry point for Claude Desktop extension mode.

This module handles API key configuration from Claude Desktop UI and starts the MCP server.
Separate from cli.py to maintain backward compatibility with CLI usage modes.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Minimum Python version required by fastmcp
MIN_PYTHON = (3, 10)

# Platform detection
IS_WINDOWS = platform.system() == "Windows"


def _get_python_search_paths() -> list[str]:
    """Get platform-specific Python search paths."""
    if IS_WINDOWS:
        # Windows Python locations
        paths = [
            # Python Launcher (py.exe) - preferred on Windows
            "py",
            # Common Windows install locations
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "python.exe"),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python311" / "python.exe"),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python310" / "python.exe"),
            # Program Files locations
            r"C:\Python312\python.exe",
            r"C:\Python311\python.exe",
            r"C:\Python310\python.exe",
            str(Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Python312" / "python.exe"),
            str(Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Python311" / "python.exe"),
            str(Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Python310" / "python.exe"),
            # pyenv-win
            str(Path.home() / ".pyenv" / "pyenv-win" / "shims" / "python.bat"),
        ]
    else:
        # Unix/macOS Python locations
        paths = [
            "/opt/homebrew/bin/python3",
            "/opt/homebrew/bin/python3.12",
            "/opt/homebrew/bin/python3.11",
            "/opt/homebrew/bin/python3.10",
            "/usr/local/bin/python3",
            "/usr/local/bin/python3.12",
            "/usr/local/bin/python3.11",
            "/usr/local/bin/python3.10",
            str(Path.home() / ".pyenv" / "shims" / "python3"),
        ]
    return paths


def _verify_python_version(python_path: str) -> bool:
    """Verify a Python interpreter is 3.10+."""
    try:
        result = subprocess.run(  # noqa: S603
            [python_path, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            major, minor = map(int, version.split("."))
            return (major, minor) >= MIN_PYTHON
    except Exception:
        pass
    return False


def _find_suitable_python() -> Optional[str]:
    """Find a Python >= 3.10 interpreter."""
    # On Windows, try py launcher first with version flag
    if IS_WINDOWS:
        for version in ["3.12", "3.11", "3.10"]:
            try:
                result = subprocess.run(  # noqa: S603, S607
                    ["py", f"-{version}", "-c", "import sys; print(sys.executable)"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    python_path = result.stdout.strip()
                    if _verify_python_version(python_path):
                        return python_path
            except Exception:
                continue

    # Check common paths
    for python_path in _get_python_search_paths():
        if python_path == "py":
            continue  # Already tried py launcher above
        if Path(python_path).exists() and _verify_python_version(python_path):
            return python_path

    return None


def _ensure_python_version() -> None:
    """Ensure we're running on Python 3.10+. Re-exec with suitable Python if needed."""
    if sys.version_info >= MIN_PYTHON:
        return  # Already running on suitable Python

    print(
        f"Python {sys.version_info.major}.{sys.version_info.minor} detected, but 3.10+ required.",
        file=sys.stderr,
    )

    suitable_python = _find_suitable_python()
    if suitable_python:
        print(f"Re-executing with: {suitable_python}", file=sys.stderr)
        # Re-exec with the suitable Python
        if IS_WINDOWS:
            # On Windows, use subprocess since execv behaves differently
            result = subprocess.run(  # noqa: S603
                [suitable_python] + sys.argv,
                check=False,
            )
            sys.exit(result.returncode)
        else:
            # On Unix, execv replaces the current process
            os.execv(suitable_python, [suitable_python] + sys.argv)  # noqa: S606
            # execv replaces the current process, so we never reach here

    # No suitable Python found
    print(
        "\n" + "=" * 60,
        file=sys.stderr,
    )
    print("ERROR: Python 3.10+ required but not found", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("\nPlease install Python 3.10+ using one of:", file=sys.stderr)
    if IS_WINDOWS:
        print("  Download from: https://www.python.org/downloads/", file=sys.stderr)
        print("  Or use: winget install Python.Python.3.12", file=sys.stderr)
        print("  Or use: choco install python312", file=sys.stderr)
    else:
        print("  brew install python@3.12", file=sys.stderr)
        print("  brew install python@3.11", file=sys.stderr)
        print("  brew install python@3.10", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    sys.exit(1)


def _find_uv() -> Optional[str]:
    """Find uv executable in common locations."""
    # Platform-specific paths
    if IS_WINDOWS:
        uv_paths = [
            str(Path.home() / ".cargo" / "bin" / "uv.exe"),
            str(Path.home() / ".local" / "bin" / "uv.exe"),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "uv" / "uv.exe"),
            r"C:\uv\uv.exe",
        ]
    else:
        uv_paths = [
            "/opt/homebrew/bin/uv",
            "/usr/local/bin/uv",
            str(Path.home() / ".cargo" / "bin" / "uv"),
            str(Path.home() / ".local" / "bin" / "uv"),
        ]

    for uv_path in uv_paths:
        if Path(uv_path).exists():
            return uv_path

    # Try PATH as fallback using platform-appropriate command
    try:
        which_cmd = "where" if IS_WINDOWS else "which"
        result = subprocess.run(  # noqa: S603, S607
            [which_cmd, "uv"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            # 'where' on Windows may return multiple lines, take first
            return result.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    return None


def _install_with_uv(uv_path: str, cache_dir: Path, packages: list[str]) -> bool:
    """Try installing with uv. Returns True on success."""
    try:
        print(f"Using uv for installation: {uv_path}", file=sys.stderr)
        result = subprocess.run(  # noqa: S603
            [
                uv_path,
                "pip",
                "install",
                "--python",
                sys.executable,  # Use current Python interpreter
                "--target",
                str(cache_dir),
            ]
            + packages,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True
        print(f"uv error: {result.stderr}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"uv exception: {e}", file=sys.stderr)
        return False


def _install_with_pip(cache_dir: Path, packages: list[str]) -> bool:
    """Try installing with pip. Returns True on success."""
    try:
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                str(cache_dir),
                "--upgrade",
            ]
            + packages,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True
        print(f"pip error: {result.stderr}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"pip exception: {e}", file=sys.stderr)
        return False


def _bootstrap_pip_and_install(cache_dir: Path, packages: list[str]) -> bool:
    """Try to bootstrap pip using ensurepip, then install. Returns True on success."""
    try:
        print("Attempting to bootstrap pip with ensurepip...", file=sys.stderr)
        subprocess.check_call(  # noqa: S603
            [sys.executable, "-m", "ensurepip", "--user"],
            stderr=subprocess.PIPE,
        )
        # Now try pip again
        return _install_with_pip(cache_dir, packages)
    except subprocess.CalledProcessError:
        return False


def ensure_dependencies() -> None:
    """
    Ensure required dependencies are installed and compatible with current Python version.

    If bundled dependencies are incompatible (wrong Python version), install them
    to a user-specific cache directory. Uses uv if available, falls back to pip.
    """
    # Try importing fastmcp to check if dependencies are available
    # We use fastmcp as the canary since it's the key MCP dependency
    try:
        import fastmcp  # noqa: F401

        # If import succeeds, dependencies are available
        return
    except (ImportError, ModuleNotFoundError) as e:
        # Bundled dependencies are missing or incompatible with this Python version
        print(
            f"Dependencies not available for Python {sys.version_info.major}.{sys.version_info.minor}: {e}",
            file=sys.stderr,
        )
        print("Installing compatible dependencies...", file=sys.stderr)

        # Create user-specific cache directory for this Python version
        cache_dir = (
            Path.home()
            / ".cache"
            / "datacommons-mcp"
            / f"py{sys.version_info.major}{sys.version_info.minor}"
        )
        cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"Cache directory: {cache_dir}", file=sys.stderr)

        # Check if already installed in cache
        fastmcp_path = cache_dir / "fastmcp"
        print(f"Checking for fastmcp at: {fastmcp_path} (exists: {fastmcp_path.exists()})", file=sys.stderr)
        if fastmcp_path.exists():
            # Add cache to path and try again
            sys.path.insert(0, str(cache_dir))
            try:
                import fastmcp  # noqa: F401

                print(f"[OK] Using cached dependencies from {cache_dir}", file=sys.stderr)
                return
            except (ImportError, ModuleNotFoundError):
                # Cache is corrupted, reinstall
                print("Cache corrupted, reinstalling...", file=sys.stderr)

        # Package list
        packages = [
            "fastmcp>=2.12.4",
            "requests>=2.32.0",
            "datacommons-client>=2.1.0",
            "pydantic>=2.11.0",
            "pydantic-settings>=2.11.0",
            "python-dateutil>=2.9.0",
        ]

        # Try installation methods in order of preference
        installed = False

        # 1. Try uv first (fastest and most reliable)
        uv_path = _find_uv()
        if uv_path:
            installed = _install_with_uv(uv_path, cache_dir, packages)

        # 2. Try pip
        if not installed:
            print("Trying pip...", file=sys.stderr)
            installed = _install_with_pip(cache_dir, packages)

        # 3. Try ensurepip + pip (for minimal Python installs like Xcode's)
        if not installed:
            installed = _bootstrap_pip_and_install(cache_dir, packages)

        if installed:
            # Add cache to path
            sys.path.insert(0, str(cache_dir))

            # Verify installation
            try:
                import fastmcp  # noqa: F401

                print(
                    f"[OK] Dependencies installed successfully to {cache_dir}",
                    file=sys.stderr,
                )
                return
            except (ImportError, ModuleNotFoundError):
                pass  # Fall through to error

        # All methods failed
        print(
            "\n" + "=" * 60,
            file=sys.stderr,
        )
        print("ERROR: Failed to install dependencies", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            "\nThe system Python lacks pip. Please install dependencies manually:",
            file=sys.stderr,
        )
        if IS_WINDOWS:
            print("\n  1. Install uv: powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"", file=sys.stderr)
            print(f"  2. Run: uv pip install --target {cache_dir} " + " ".join(packages), file=sys.stderr)
            print("\nOr install Python from: https://www.python.org/downloads/", file=sys.stderr)
        else:
            print("\n  1. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh", file=sys.stderr)
            print(f"  2. Run: uv pip install --target {cache_dir} " + " ".join(packages), file=sys.stderr)
            print("\nOr install Homebrew Python: brew install python@3.12", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        sys.exit(1)


def _ensure_package_path() -> None:
    """Ensure the datacommons_mcp package directory is in sys.path.

    When run_server.py is executed directly, Python adds its directory to sys.path,
    but not the parent directory containing the datacommons_mcp package.
    This function adds the correct parent directory.
    """
    # Get the directory containing this file (datacommons_mcp/)
    this_dir = Path(__file__).resolve().parent
    # Get the parent directory (which should contain datacommons_mcp/)
    package_parent = this_dir.parent

    # Add to sys.path if not already there
    package_parent_str = str(package_parent)
    if package_parent_str not in sys.path:
        sys.path.insert(0, package_parent_str)


def main() -> None:
    """
    Initialize and run the DataCommons MCP server in extension mode.

    Validates API key configuration from environment and starts the FastMCP server.
    Exits with code 1 if API key is not configured.
    """
    # Ensure package is importable (fix for Claude Desktop extension mode)
    _ensure_package_path()

    # Ensure we're running on Python 3.10+ (required by fastmcp)
    _ensure_python_version()

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
        print(f"[OK] DC_API_KEY configured ({len(api_key)} chars)", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

    # Import and run the server
    from datacommons_mcp.server import mcp

    mcp.run()


if __name__ == "__main__":
    main()
