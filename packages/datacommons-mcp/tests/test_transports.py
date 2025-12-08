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
"""Tests for the transport abstraction layer."""

from datacommons_mcp.transports import (
    StdioTransport,
    TransportFactory,
    TransportMode,
    create_transport,
)
from datacommons_mcp.transports.base import ProgressEvent


class TestTransportMode:
    """Tests for TransportMode enum."""

    def test_enum_values(self):
        """Test that TransportMode has expected values."""
        assert TransportMode.STDIO.value == "stdio"
        assert TransportMode.SSE.value == "sse"

    def test_enum_from_string(self):
        """Test creating enum from string."""
        assert TransportMode("stdio") == TransportMode.STDIO
        assert TransportMode("sse") == TransportMode.SSE


class TestProgressEvent:
    """Tests for ProgressEvent dataclass."""

    def test_create_progress_event(self):
        """Test creating a progress event."""
        event = ProgressEvent(
            event_type="progress",
            page_number=1,
            rows_written=100,
            total_bytes=1024,
        )

        assert event.event_type == "progress"
        assert event.page_number == 1
        assert event.rows_written == 100
        assert event.total_bytes == 1024

    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = ProgressEvent(
            event_type="progress",
            page_number=2,
            rows_written=200,
            total_bytes=2048,
            message="Processing...",
        )

        result = event.to_dict()

        assert result["event"] == "progress"
        assert result["page"] == 2
        assert result["rows"] == 200
        assert result["bytes"] == 2048
        assert result["message"] == "Processing..."

    def test_to_dict_with_data(self):
        """Test converting event with data to dictionary."""
        event = ProgressEvent(
            event_type="complete",
            data={"file_path": "/tmp/test.csv"},
        )

        result = event.to_dict()

        assert result["data"]["file_path"] == "/tmp/test.csv"

    def test_default_values(self):
        """Test default values for optional fields."""
        event = ProgressEvent(event_type="test")

        assert event.page_number == 0
        assert event.rows_written == 0
        assert event.total_bytes == 0
        assert event.message is None
        assert event.data == {}


class TestStdioTransport:
    """Tests for StdioTransport."""

    def test_init(self):
        """Test transport initialization."""
        transport = StdioTransport()

        assert transport.mode == TransportMode.STDIO
        assert transport.verbose is False

    def test_init_verbose(self):
        """Test transport initialization with verbose mode."""
        transport = StdioTransport(verbose=True)

        assert transport.verbose is True

    def test_supports_streaming_progress(self):
        """Test that STDIO doesn't support streaming progress."""
        transport = StdioTransport()

        assert transport.supports_streaming_progress is False

    def test_send_progress(self):
        """Test sending progress (logs internally)."""
        transport = StdioTransport()

        event = ProgressEvent(event_type="progress", page_number=1)
        transport.send_progress(event)

        log = transport.get_progress_log()
        assert len(log) == 1
        assert log[0].event_type == "progress"

    def test_send_result_passthrough(self):
        """Test that send_result returns result unchanged."""
        transport = StdioTransport()

        result = {"output_mode": "screen", "data": {"test": 123}}
        output = transport.send_result(result)

        assert output == result

    def test_progress_log(self):
        """Test progress log accumulation."""
        transport = StdioTransport()

        transport.send_progress(ProgressEvent(event_type="start"))
        transport.send_progress(ProgressEvent(event_type="progress", page_number=1))
        transport.send_progress(ProgressEvent(event_type="complete"))

        log = transport.get_progress_log()
        assert len(log) == 3
        assert log[0].event_type == "start"
        assert log[1].event_type == "progress"
        assert log[2].event_type == "complete"

    def test_clear_progress_log(self):
        """Test clearing the progress log."""
        transport = StdioTransport()

        transport.send_progress(ProgressEvent(event_type="test"))
        transport.clear_progress_log()

        assert transport.get_progress_log() == []

    def test_get_summary(self):
        """Test getting progress summary."""
        transport = StdioTransport()

        transport.send_progress(
            ProgressEvent(
                event_type="progress",
                page_number=5,
                rows_written=500,
                total_bytes=5000,
            )
        )

        summary = transport.get_summary()

        assert summary["pages"] == 5
        assert summary["rows"] == 500
        assert summary["bytes"] == 5000

    def test_get_summary_empty(self):
        """Test summary with no progress events."""
        transport = StdioTransport()

        summary = transport.get_summary()

        assert summary["pages"] == 0
        assert summary["rows"] == 0
        assert summary["bytes"] == 0

    def test_create_progress_callback(self):
        """Test creating a progress callback."""
        transport = StdioTransport()
        callback = transport.create_progress_callback()

        callback(1, 100, 1024)

        log = transport.get_progress_log()
        assert len(log) == 1
        assert log[0].page_number == 1
        assert log[0].rows_written == 100
        assert log[0].total_bytes == 1024


class TestBaseTransportMethods:
    """Tests for BaseTransport convenience methods."""

    def test_send_start(self):
        """Test send_start method."""
        transport = StdioTransport()

        transport.send_start({"variable": "Count_Person"})

        log = transport.get_progress_log()
        assert log[0].event_type == "start"
        assert log[0].data["variable"] == "Count_Person"

    def test_send_complete(self):
        """Test send_complete method."""
        transport = StdioTransport()

        transport.send_complete({"rows": 100}, success=True)

        log = transport.get_progress_log()
        assert log[0].event_type == "complete"
        assert log[0].data["rows"] == 100

    def test_send_complete_failure(self):
        """Test send_complete for failure."""
        transport = StdioTransport()

        transport.send_complete({}, success=False, message="Failed!")

        log = transport.get_progress_log()
        assert log[0].event_type == "error"
        assert log[0].message == "Failed!"

    def test_send_error(self):
        """Test send_error method."""
        transport = StdioTransport()

        transport.send_error(ValueError("Test error"))

        log = transport.get_progress_log()
        assert log[0].event_type == "error"
        assert "Test error" in log[0].message
        assert log[0].data["error_type"] == "ValueError"


class TestTransportFactory:
    """Tests for TransportFactory."""

    def test_create_stdio_transport(self):
        """Test creating STDIO transport."""
        transport = TransportFactory.create(TransportMode.STDIO)

        assert isinstance(transport, StdioTransport)
        assert transport.mode == TransportMode.STDIO

    def test_create_stdio_from_string(self):
        """Test creating transport from string mode."""
        transport = TransportFactory.create("stdio")

        assert isinstance(transport, StdioTransport)

    def test_create_with_kwargs(self):
        """Test creating transport with kwargs."""
        transport = TransportFactory.create("stdio", verbose=True)

        assert transport.verbose is True

    def test_get_available_modes(self):
        """Test getting available modes."""
        modes = TransportFactory.get_available_modes()

        assert TransportMode.STDIO in modes
        assert TransportMode.SSE in modes

    def test_is_mode_available_stdio(self):
        """Test STDIO mode is always available."""
        assert TransportFactory.is_mode_available(TransportMode.STDIO)
        assert TransportFactory.is_mode_available("stdio")

    def test_is_mode_available_invalid(self):
        """Test invalid mode returns False."""
        assert not TransportFactory.is_mode_available("invalid")


class TestCreateTransport:
    """Tests for create_transport convenience function."""

    def test_default_is_stdio(self):
        """Test default transport is STDIO."""
        transport = create_transport()

        assert isinstance(transport, StdioTransport)

    def test_with_mode(self):
        """Test creating with explicit mode."""
        transport = create_transport(TransportMode.STDIO)

        assert isinstance(transport, StdioTransport)

    def test_with_string_mode(self):
        """Test creating with string mode."""
        transport = create_transport("stdio")

        assert isinstance(transport, StdioTransport)

    def test_with_kwargs(self):
        """Test creating with kwargs."""
        transport = create_transport("stdio", verbose=True)

        assert transport.verbose is True
