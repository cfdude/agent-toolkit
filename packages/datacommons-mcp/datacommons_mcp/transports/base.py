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
"""Base transport abstraction for MCP server communication."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TransportMode(str, Enum):
    """Transport modes supported by the MCP server."""

    STDIO = "stdio"  # Standard input/output (default MCP transport)
    SSE = "sse"  # Server-Sent Events for streaming progress


@dataclass
class ProgressEvent:
    """Represents a progress update during data streaming.

    Attributes:
        event_type: Type of event (e.g., "page", "rows", "complete", "error").
        page_number: Current page number being processed.
        rows_written: Total rows written so far.
        total_bytes: Total bytes written so far.
        message: Optional human-readable message.
        data: Optional additional data for the event.
    """

    event_type: str
    page_number: int = 0
    rows_written: int = 0
    total_bytes: int = 0
    message: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "event": self.event_type,
            "page": self.page_number,
            "rows": self.rows_written,
            "bytes": self.total_bytes,
        }
        if self.message:
            result["message"] = self.message
        if self.data:
            result["data"] = self.data
        return result


# Type alias for progress callback
ProgressCallback = Callable[[ProgressEvent], None]


class BaseTransport(ABC):
    """Abstract base class for MCP transport implementations.

    This class defines the interface for different transport mechanisms
    used by the MCP server. Implementations handle the specifics of
    how to communicate progress and results to the client.

    The transport abstraction allows the same server logic to work with
    both STDIO (standard MCP) and SSE (streaming progress) transports.

    Attributes:
        mode: The transport mode (STDIO or SSE).
    """

    def __init__(self, mode: TransportMode) -> None:
        """Initialize the transport.

        Args:
            mode: The transport mode to use.
        """
        self.mode = mode

    @property
    def supports_streaming_progress(self) -> bool:
        """Whether this transport supports real-time progress updates.

        STDIO transport doesn't support mid-request progress updates,
        while SSE can stream progress events to the client.

        Returns:
            True if the transport supports streaming progress.
        """
        return False

    @abstractmethod
    def send_progress(self, event: ProgressEvent) -> None:
        """Send a progress update to the client.

        For transports that don't support streaming progress, this
        method may be a no-op or log the progress internally.

        Args:
            event: The progress event to send.
        """

    @abstractmethod
    def send_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Send the final result to the client.

        This method prepares the result for transmission through
        the specific transport mechanism.

        Args:
            result: The result dictionary to send.

        Returns:
            The formatted result (may be transformed for transport).
        """

    def create_progress_callback(self) -> ProgressCallback:
        """Create a progress callback function for streaming.

        This callback can be passed to the pagination handler to
        receive progress updates during data fetching.

        Returns:
            A callback function that accepts page, rows, and bytes.
        """

        def callback(page: int, rows: int, total_bytes: int) -> None:
            event = ProgressEvent(
                event_type="progress",
                page_number=page,
                rows_written=rows,
                total_bytes=total_bytes,
            )
            self.send_progress(event)

        return callback

    def send_start(self, request_info: dict[str, Any] | None = None) -> None:
        """Send a start event indicating the beginning of processing.

        Args:
            request_info: Optional information about the request being processed.
        """
        event = ProgressEvent(
            event_type="start",
            message="Processing started",
            data=request_info or {},
        )
        self.send_progress(event)

    def send_complete(
        self,
        result: dict[str, Any],
        *,
        success: bool = True,
        message: str | None = None,
    ) -> None:
        """Send a completion event.

        Args:
            result: The final result data.
            success: Whether the operation completed successfully.
            message: Optional completion message.
        """
        event = ProgressEvent(
            event_type="complete" if success else "error",
            message=message or ("Completed successfully" if success else "Failed"),
            data=result,
        )
        self.send_progress(event)

    def send_error(self, error: Exception, message: str | None = None) -> None:
        """Send an error event.

        Args:
            error: The exception that occurred.
            message: Optional error message (uses exception message if not provided).
        """
        event = ProgressEvent(
            event_type="error",
            message=message or str(error),
            data={"error_type": type(error).__name__},
        )
        self.send_progress(event)
