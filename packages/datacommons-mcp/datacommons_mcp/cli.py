import logging
import os
import sys
from typing import Literal

import click

from .transports import TransportFactory, TransportMode, create_transport
from .version import __version__

# Global transport and server instances for the server
_transport = None
_sse_server = None


def get_transport():
    """Get the current transport instance."""
    global _transport
    if _transport is None:
        _transport = create_transport()
    return _transport


def get_sse_server():
    """Get the current SSE server instance (if any)."""
    return _sse_server


def set_transport(
    mode: Literal["stdio", "sse"] = "stdio",
    verbose: bool = False,
    sse_port: int = 8081,
    sse_host: str = "127.0.0.1",
) -> None:
    """Configure the transport for the server."""
    global _transport, _sse_server
    if mode == "sse":
        _transport = TransportFactory.create(
            TransportMode.SSE,
            port=sse_port,
        )
        # Create SSE server
        try:
            from .sse_server import create_sse_server

            _sse_server = create_sse_server(
                _transport,
                host=sse_host,
                port=sse_port,
            )
        except ImportError:
            # SSE server not available
            _sse_server = None
    else:
        _transport = TransportFactory.create(
            TransportMode.STDIO,
            verbose=verbose,
        )
        _sse_server = None


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """DataCommons MCP CLI - Model Context Protocol server for Data Commons."""
    logging.basicConfig(level=logging.INFO)


@cli.group()
def serve() -> None:
    """Serve the MCP server in different modes."""


@serve.command()
@click.option("--host", default="localhost", help="Host to bind.")
@click.option("--port", default=8080, help="Port to bind.", type=int)
@click.option(
    "--progress-transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport for progress updates (stdio logs, sse streams).",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose progress logging (stdio transport only).",
)
@click.option(
    "--sse-port",
    default=8081,
    type=int,
    help="Port for SSE progress endpoint (sse transport only).",
)
@click.option(
    "--storage-dir",
    default=None,
    type=click.Path(),
    help="Directory for storing exported data files (overrides DC_STORAGE_DIR).",
)
def http(
    host: str,
    port: int,
    progress_transport: str,
    verbose: bool,
    sse_port: int,
    storage_dir: str | None,
) -> None:
    """Start the MCP server in Streamable HTTP mode."""
    # Set storage directory environment variable if provided via CLI
    if storage_dir:
        os.environ["DC_STORAGE_DIR"] = storage_dir

    try:
        from datacommons_mcp.server import mcp

        # Configure transport
        set_transport(
            mode=progress_transport,  # type: ignore
            verbose=verbose,
            sse_port=sse_port,
            sse_host=host,
        )

        click.echo("Starting DataCommons MCP server in Streamable HTTP mode")
        click.echo(f"Version: {__version__}")
        click.echo(f"Server URL: http://{host}:{port}")
        click.echo(f"Streamable HTTP endpoint: http://{host}:{port}/mcp")
        click.echo(f"Progress transport: {progress_transport}")

        # Start SSE server if using SSE transport
        sse_server = get_sse_server()
        if progress_transport == "sse" and sse_server is not None:
            sse_server.start()
            click.echo(f"SSE progress endpoint: http://{host}:{sse_port}/events")

        click.echo("Press CTRL+C to stop")

        try:
            mcp.run(host=host, port=port, transport="streamable-http")
        finally:
            # Stop SSE server on shutdown
            if sse_server is not None:
                sse_server.stop()

    except ImportError as e:
        click.echo(f"Error importing server: {e}", err=True)
        sys.exit(1)


@serve.command()
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose progress logging.",
)
@click.option(
    "--storage-dir",
    default=None,
    type=click.Path(),
    help="Directory for storing exported data files (overrides DC_STORAGE_DIR).",
)
def stdio(verbose: bool, storage_dir: str | None) -> None:
    """Start the MCP server in stdio mode."""
    # Set storage directory environment variable if provided via CLI
    if storage_dir:
        os.environ["DC_STORAGE_DIR"] = storage_dir

    try:
        from datacommons_mcp.server import mcp

        # Configure transport (always STDIO for stdio mode)
        set_transport(mode="stdio", verbose=verbose)

        click.echo("Starting DataCommons MCP server in stdio mode", err=True)
        click.echo(f"Version: {__version__}", err=True)
        if verbose:
            click.echo("Verbose progress logging enabled", err=True)
        click.echo("Server is ready to receive requests via stdin/stdout", err=True)

        mcp.run(transport="stdio")

    except ImportError as e:
        click.echo(f"Error importing server: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
