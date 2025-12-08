# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""SSE server for streaming progress events.

This module provides an HTTP server that streams progress events
to connected clients using Server-Sent Events (SSE).

Requires: pip install datacommons-mcp[sse]
"""

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# Check for optional dependencies
try:
    import uvicorn
    from sse_starlette.sse import EventSourceResponse
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    SSE_DEPS_AVAILABLE = True
except ImportError:
    SSE_DEPS_AVAILABLE = False
    uvicorn = None  # type: ignore
    Starlette = None  # type: ignore
    JSONResponse = None  # type: ignore
    Route = None  # type: ignore
    EventSourceResponse = None  # type: ignore

if TYPE_CHECKING:
    from .transports.sse import SSETransport


class SSEServer:
    """SSE server for streaming progress events.

    This server runs in a background thread and provides an HTTP endpoint
    for clients to subscribe to progress events via Server-Sent Events.

    Example:
        >>> from datacommons_mcp.transports import create_transport
        >>> from datacommons_mcp.sse_server import SSEServer
        >>>
        >>> transport = create_transport("sse", port=8081)
        >>> server = SSEServer(transport)
        >>> server.start()  # Starts in background thread
        >>> # ... use transport.send_progress() ...
        >>> server.stop()

    Attributes:
        transport: The SSE transport instance.
        host: Host to bind to.
        port: Port to bind to.
    """

    def __init__(
        self,
        transport: "SSETransport",
        host: str = "127.0.0.1",
        port: int = 8081,
    ) -> None:
        """Initialize the SSE server.

        Args:
            transport: The SSE transport to serve events from.
            host: Host to bind to (default: localhost).
            port: Port to bind to (default: 8081).

        Raises:
            ImportError: If required dependencies are not installed.
        """
        if not SSE_DEPS_AVAILABLE:
            raise ImportError(
                "SSE server requires additional dependencies. "
                "Install with: pip install datacommons-mcp[sse]"
            )

        self.transport = transport
        self.host = host
        self.port = port
        self._server_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._app = self._create_app()

    def _create_app(self) -> "Starlette":
        """Create the Starlette application.

        Returns:
            Configured Starlette app with SSE endpoint.
        """

        async def sse_endpoint(request):
            """SSE endpoint for streaming events."""
            self.transport.start()
            return EventSourceResponse(self.transport.event_generator())

        async def health_endpoint(request):
            """Health check endpoint."""
            return JSONResponse({"status": "healthy", "server": "sse-progress"})

        async def status_endpoint(request):
            """Status endpoint with server info."""
            return JSONResponse(
                {
                    "host": self.host,
                    "port": self.port,
                    "running": self.transport._is_running,
                    "pending_events": len(self.transport._event_queue),
                    "endpoint": f"http://{self.host}:{self.port}/events",
                }
            )

        routes = [
            Route("/events", sse_endpoint),
            Route("/health", health_endpoint),
            Route("/status", status_endpoint),
        ]

        return Starlette(routes=routes)

    def start(self) -> None:
        """Start the SSE server in a background thread."""
        if self._server_thread is not None and self._server_thread.is_alive():
            logger.warning("SSE server is already running")
            return

        self._shutdown_event.clear()

        def run_server():
            """Run the uvicorn server."""
            config = uvicorn.Config(
                self._app,
                host=self.host,
                port=self.port,
                log_level="warning",
                access_log=False,
            )
            server = uvicorn.Server(config)

            # Override the shutdown method to check our event
            original_shutdown = server.shutdown

            async def patched_shutdown(*args, **kwargs):
                self.transport.stop()
                await original_shutdown(*args, **kwargs)

            server.shutdown = patched_shutdown

            # Run the server
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(server.serve())
            finally:
                loop.close()

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

        logger.info("SSE server started at http://%s:%d/events", self.host, self.port)

    def stop(self) -> None:
        """Stop the SSE server."""
        self._shutdown_event.set()
        self.transport.stop()

        if self._server_thread is not None:
            self._server_thread.join(timeout=5.0)
            self._server_thread = None

        logger.info("SSE server stopped")

    def is_running(self) -> bool:
        """Check if the server is running.

        Returns:
            True if the server is running.
        """
        return self._server_thread is not None and self._server_thread.is_alive()

    def get_endpoint_url(self) -> str:
        """Get the SSE endpoint URL.

        Returns:
            The URL to connect to for SSE events.
        """
        return f"http://{self.host}:{self.port}/events"


def create_sse_server(
    transport: "SSETransport",
    host: str = "127.0.0.1",
    port: int = 8081,
) -> SSEServer:
    """Create an SSE server instance.

    This is a convenience function for creating an SSE server.

    Args:
        transport: The SSE transport to serve events from.
        host: Host to bind to (default: localhost).
        port: Port to bind to (default: 8081).

    Returns:
        Configured SSEServer instance.

    Example:
        >>> from datacommons_mcp.transports import create_transport
        >>> from datacommons_mcp.sse_server import create_sse_server
        >>>
        >>> transport = create_transport("sse", port=8081)
        >>> server = create_sse_server(transport, port=8081)
        >>> server.start()
    """
    return SSEServer(transport, host=host, port=port)
