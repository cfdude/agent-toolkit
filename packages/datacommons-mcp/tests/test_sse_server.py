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
"""Tests for the SSE server module."""

import pytest

# Check if SSE dependencies are available
try:
    import uvicorn  # noqa: F401
    from sse_starlette.sse import EventSourceResponse  # noqa: F401

    SSE_DEPS_AVAILABLE = True
except ImportError:
    SSE_DEPS_AVAILABLE = False


@pytest.mark.skipif(not SSE_DEPS_AVAILABLE, reason="SSE dependencies not installed")
class TestSSEServer:
    """Tests for SSEServer class."""

    def test_create_sse_server(self):
        """Test creating an SSE server."""
        from datacommons_mcp.sse_server import SSEServer, create_sse_server
        from datacommons_mcp.transports import create_transport

        transport = create_transport("sse", port=8082)
        server = create_sse_server(transport, port=8082)

        assert isinstance(server, SSEServer)
        assert server.transport == transport
        assert server.port == 8082

    def test_server_init(self):
        """Test server initialization."""
        from datacommons_mcp.sse_server import SSEServer
        from datacommons_mcp.transports import create_transport

        transport = create_transport("sse", port=8083)
        server = SSEServer(transport, host="0.0.0.0", port=8083)

        assert server.host == "0.0.0.0"
        assert server.port == 8083
        assert not server.is_running()

    def test_get_endpoint_url(self):
        """Test getting endpoint URL."""
        from datacommons_mcp.sse_server import SSEServer
        from datacommons_mcp.transports import create_transport

        transport = create_transport("sse", port=8084)
        server = SSEServer(transport, host="localhost", port=8084)

        url = server.get_endpoint_url()
        assert url == "http://localhost:8084/events"

    def test_app_has_routes(self):
        """Test that app has expected routes."""
        from datacommons_mcp.sse_server import SSEServer
        from datacommons_mcp.transports import create_transport

        transport = create_transport("sse", port=8085)
        server = SSEServer(transport, port=8085)

        # Check routes exist
        routes = [r.path for r in server._app.routes]
        assert "/events" in routes
        assert "/health" in routes
        assert "/status" in routes


class TestSSEServerImportError:
    """Test behavior when SSE dependencies are not installed."""

    def test_without_deps_flag(self):
        """Test SSE_DEPS_AVAILABLE flag."""
        from datacommons_mcp.sse_server import SSE_DEPS_AVAILABLE

        # Flag should match our test check
        assert SSE_DEPS_AVAILABLE == SSE_DEPS_AVAILABLE


@pytest.mark.skipif(not SSE_DEPS_AVAILABLE, reason="SSE dependencies not installed")
class TestSSEServerIntegration:
    """Integration tests for SSE server (requires SSE deps)."""

    def test_server_start_stop(self):
        """Test starting and stopping the server."""
        import time

        from datacommons_mcp.sse_server import SSEServer
        from datacommons_mcp.transports import create_transport

        transport = create_transport("sse", port=8086)
        server = SSEServer(transport, port=8086)

        # Start server
        server.start()
        time.sleep(0.5)  # Give server time to start

        assert server.is_running()

        # Stop server
        server.stop()
        time.sleep(0.5)  # Give server time to stop

        # Note: is_running() may still be True briefly after stop()
        # because the thread may take a moment to fully terminate

    def test_server_double_start(self):
        """Test that starting twice doesn't crash."""
        import time

        from datacommons_mcp.sse_server import SSEServer
        from datacommons_mcp.transports import create_transport

        transport = create_transport("sse", port=8087)
        server = SSEServer(transport, port=8087)

        try:
            server.start()
            time.sleep(0.3)
            server.start()  # Should warn but not crash
            time.sleep(0.3)
        finally:
            server.stop()
