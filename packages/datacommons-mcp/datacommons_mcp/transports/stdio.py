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
"""STDIO transport implementation for standard MCP communication."""

import logging
import sys
from typing import Any

from .base import BaseTransport, ProgressEvent, TransportMode

logger = logging.getLogger(__name__)


class StdioTransport(BaseTransport):
    """Standard input/output transport for MCP.

    This is the default transport mode for MCP servers. Progress updates
    are logged to stderr (since stdout is reserved for MCP protocol),
    and results are returned directly to the caller.

    This transport does NOT support real-time progress streaming to the
    client, as the MCP protocol over STDIO doesn't have a mechanism for
    mid-request updates. Progress is logged for debugging purposes only.

    Attributes:
        verbose: If True, log progress updates to stderr.
    """

    def __init__(self, *, verbose: bool = False) -> None:
        """Initialize the STDIO transport.

        Args:
            verbose: If True, log detailed progress to stderr.
        """
        super().__init__(TransportMode.STDIO)
        self.verbose = verbose
        self._progress_log: list[ProgressEvent] = []

    @property
    def supports_streaming_progress(self) -> bool:
        """STDIO transport doesn't support streaming progress."""
        return False

    def send_progress(self, event: ProgressEvent) -> None:
        """Log progress update to stderr.

        Since STDIO doesn't support streaming progress to the client,
        we log progress for debugging purposes.

        Args:
            event: The progress event to log.
        """
        self._progress_log.append(event)

        if self.verbose:
            if event.event_type == "progress":
                print(
                    f"[Progress] Page {event.page_number}: "
                    f"{event.rows_written} rows, {event.total_bytes} bytes",
                    file=sys.stderr,
                )
            elif event.event_type == "start":
                print("[Start] Processing...", file=sys.stderr)
            elif event.event_type == "complete":
                print(f"[Complete] {event.message}", file=sys.stderr)
            elif event.event_type == "error":
                print(f"[Error] {event.message}", file=sys.stderr)
            else:
                print(f"[{event.event_type}] {event.message}", file=sys.stderr)

        # Also log at debug level for logger
        logger.debug(
            "Progress: type=%s page=%d rows=%d bytes=%d",
            event.event_type,
            event.page_number,
            event.rows_written,
            event.total_bytes,
        )

    def send_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Return result directly (STDIO passthrough).

        For STDIO transport, results are returned as-is to be handled
        by the MCP protocol layer.

        Args:
            result: The result dictionary.

        Returns:
            The unchanged result dictionary.
        """
        return result

    def get_progress_log(self) -> list[ProgressEvent]:
        """Get the log of all progress events.

        This can be useful for debugging or testing.

        Returns:
            List of all progress events received.
        """
        return self._progress_log.copy()

    def clear_progress_log(self) -> None:
        """Clear the progress log."""
        self._progress_log.clear()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the progress.

        Returns:
            Dictionary with summary statistics.
        """
        if not self._progress_log:
            return {"pages": 0, "rows": 0, "bytes": 0}

        # Find the last progress or complete event
        last_progress = None
        for event in reversed(self._progress_log):
            if event.event_type in ("progress", "complete"):
                last_progress = event
                break

        if last_progress:
            return {
                "pages": last_progress.page_number,
                "rows": last_progress.rows_written,
                "bytes": last_progress.total_bytes,
            }

        return {"pages": 0, "rows": 0, "bytes": 0}
