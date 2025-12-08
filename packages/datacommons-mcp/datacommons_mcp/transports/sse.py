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
"""SSE (Server-Sent Events) transport for streaming progress updates.

This module provides a transport that can stream progress events to
clients in real-time using Server-Sent Events.

Note: This requires the optional 'sse' extras to be installed.
"""

import json
import logging
from typing import Any

from .base import BaseTransport, ProgressEvent, TransportMode

logger = logging.getLogger(__name__)

# Check for optional SSE dependency
try:
    from sse_starlette.sse import EventSourceResponse  # noqa: F401

    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False


class SSETransport(BaseTransport):
    """Server-Sent Events transport for streaming progress.

    This transport allows real-time progress updates to be streamed
    to the client. It's useful for long-running operations like
    large dataset exports.

    Requires: sse-starlette library (install with pip install datacommons-mcp[sse])

    Attributes:
        port: The port to run the SSE server on.
        host: The host to bind to.
    """

    def __init__(
        self,
        port: int = 8080,
        host: str = "127.0.0.1",
    ) -> None:
        """Initialize the SSE transport.

        Args:
            port: Port for the SSE server (default: 8080).
            host: Host to bind to (default: localhost).

        Raises:
            ImportError: If sse-starlette is not installed.
        """
        if not SSE_AVAILABLE:
            raise ImportError(
                "SSE transport requires sse-starlette. "
                "Install with: pip install datacommons-mcp[sse]"
            )

        super().__init__(TransportMode.SSE)
        self.port = port
        self.host = host
        self._event_queue: list[ProgressEvent] = []
        self._is_running = False

    @property
    def supports_streaming_progress(self) -> bool:
        """SSE transport supports real-time streaming progress."""
        return True

    def send_progress(self, event: ProgressEvent) -> None:
        """Send a progress event via SSE.

        This queues the event for transmission to connected clients.

        Args:
            event: The progress event to send.
        """
        self._event_queue.append(event)

        # Log for debugging
        logger.debug(
            "SSE Progress: type=%s page=%d rows=%d bytes=%d",
            event.event_type,
            event.page_number,
            event.rows_written,
            event.total_bytes,
        )

    def send_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Send the final result.

        For SSE, this sends a completion event with the result.

        Args:
            result: The result dictionary.

        Returns:
            The result dictionary (unchanged).
        """
        # Send completion event
        self.send_complete(result)
        return result

    def get_pending_events(self) -> list[dict[str, Any]]:
        """Get all pending events as serializable dicts.

        This drains the event queue and returns the events.

        Returns:
            List of event dictionaries ready for SSE transmission.
        """
        events = [e.to_dict() for e in self._event_queue]
        self._event_queue.clear()
        return events

    async def event_generator(self):
        """Async generator for SSE events.

        This can be used with sse-starlette's EventSourceResponse.

        Yields:
            SSE event data dictionaries.
        """
        import asyncio

        while self._is_running or self._event_queue:
            if self._event_queue:
                event = self._event_queue.pop(0)
                yield {
                    "event": event.event_type,
                    "data": json.dumps(event.to_dict()),
                }

            # Small delay to prevent busy-waiting
            await asyncio.sleep(0.01)

    def start(self) -> None:
        """Mark the transport as running."""
        self._is_running = True

    def stop(self) -> None:
        """Mark the transport as stopped."""
        self._is_running = False

    def get_endpoint_url(self) -> str:
        """Get the SSE endpoint URL.

        Returns:
            The URL clients should connect to for events.
        """
        return f"http://{self.host}:{self.port}/events"
