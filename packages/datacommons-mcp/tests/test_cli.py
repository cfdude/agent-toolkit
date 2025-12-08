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
"""Tests for the CLI module."""

from unittest.mock import patch

from click.testing import CliRunner
from datacommons_mcp.cli import cli, get_transport, set_transport
from datacommons_mcp.transports import StdioTransport, TransportMode


class TestSetTransport:
    """Tests for set_transport function."""

    def test_default_stdio_transport(self):
        """Test setting default STDIO transport."""
        set_transport()

        transport = get_transport()
        assert isinstance(transport, StdioTransport)
        assert transport.mode == TransportMode.STDIO
        assert transport.verbose is False

    def test_stdio_transport_verbose(self):
        """Test STDIO transport with verbose mode."""
        set_transport(mode="stdio", verbose=True)

        transport = get_transport()
        assert isinstance(transport, StdioTransport)
        assert transport.verbose is True

    def test_sse_transport_requires_dependency(self):
        """Test SSE transport requires sse-starlette dependency."""
        # SSE transport may not be available without optional deps
        # This test documents that behavior
        try:
            set_transport(mode="sse", sse_port=8081)
            transport = get_transport()
            assert transport.mode == TransportMode.SSE
        except ImportError:
            # Expected if sse-starlette is not installed
            pass


class TestCliGroup:
    """Tests for CLI group commands."""

    def test_cli_version(self):
        """Test CLI version option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_cli_help(self):
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "DataCommons MCP CLI" in result.output


class TestServeGroup:
    """Tests for serve command group."""

    def test_serve_help(self):
        """Test serve group help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])

        assert result.exit_code == 0
        assert "stdio" in result.output
        assert "http" in result.output


class TestStdioCommand:
    """Tests for stdio serve command."""

    def test_stdio_help(self):
        """Test stdio command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "stdio", "--help"])

        assert result.exit_code == 0
        assert "--verbose" in result.output
        assert "--storage-dir" in result.output

    @patch("datacommons_mcp.server.mcp")
    def test_stdio_default(self, mock_mcp):
        """Test stdio command with defaults."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "stdio"])

        # Check transport was configured
        transport = get_transport()
        assert isinstance(transport, StdioTransport)
        assert transport.verbose is False

    @patch("datacommons_mcp.server.mcp")
    def test_stdio_verbose(self, mock_mcp):
        """Test stdio command with verbose flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "stdio", "--verbose"])

        transport = get_transport()
        assert isinstance(transport, StdioTransport)
        assert transport.verbose is True

    @patch("datacommons_mcp.server.mcp")
    def test_stdio_storage_dir(self, mock_mcp):
        """Test stdio command with --storage-dir sets environment variable."""
        import os

        # Save and clear any existing value
        original_value = os.environ.pop("DC_STORAGE_DIR", None)

        try:
            runner = CliRunner()
            result = runner.invoke(
                cli, ["serve", "stdio", "--storage-dir", "/tmp/test-data"]
            )

            # Verify environment variable was set
            assert os.environ.get("DC_STORAGE_DIR") == "/tmp/test-data"
        finally:
            # Clean up: restore original value or remove
            if original_value is not None:
                os.environ["DC_STORAGE_DIR"] = original_value
            else:
                os.environ.pop("DC_STORAGE_DIR", None)


class TestHttpCommand:
    """Tests for http serve command."""

    def test_http_help(self):
        """Test http command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "http", "--help"])

        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--progress-transport" in result.output
        assert "--verbose" in result.output
        assert "--sse-port" in result.output
        assert "--storage-dir" in result.output

    @patch("datacommons_mcp.server.mcp")
    def test_http_default(self, mock_mcp):
        """Test http command with defaults."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "http"])

        # Check transport was configured
        transport = get_transport()
        assert isinstance(transport, StdioTransport)

    @patch("datacommons_mcp.server.mcp")
    def test_http_custom_ports(self, mock_mcp):
        """Test http command with custom ports."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["serve", "http", "--host", "0.0.0.0", "--port", "9000"]
        )

        assert "9000" in result.output

    @patch("datacommons_mcp.server.mcp")
    def test_http_verbose(self, mock_mcp):
        """Test http command with verbose progress."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "http", "--verbose"])

        transport = get_transport()
        assert transport.verbose is True

    @patch("datacommons_mcp.server.mcp")
    def test_http_sse_transport(self, mock_mcp):
        """Test http command with SSE transport."""
        runner = CliRunner()
        try:
            result = runner.invoke(
                cli,
                [
                    "serve",
                    "http",
                    "--progress-transport",
                    "sse",
                    "--sse-port",
                    "8082",
                ],
            )
            # If SSE is available, check output mentions SSE
            if result.exit_code == 0:
                assert "sse" in result.output.lower() or "8082" in result.output
        except ImportError:
            # SSE may not be available without optional deps
            pass

    @patch("datacommons_mcp.server.mcp")
    def test_http_storage_dir(self, mock_mcp):
        """Test http command with --storage-dir sets environment variable."""
        import os

        # Save and clear any existing value
        original_value = os.environ.pop("DC_STORAGE_DIR", None)

        try:
            runner = CliRunner()
            result = runner.invoke(
                cli, ["serve", "http", "--storage-dir", "/tmp/test-http-data"]
            )

            # Verify environment variable was set
            assert os.environ.get("DC_STORAGE_DIR") == "/tmp/test-http-data"
        finally:
            # Clean up: restore original value or remove
            if original_value is not None:
                os.environ["DC_STORAGE_DIR"] = original_value
            else:
                os.environ.pop("DC_STORAGE_DIR", None)


class TestGetTransport:
    """Tests for get_transport function."""

    def test_get_transport_returns_default(self):
        """Test get_transport returns default if not set."""
        # Reset transport
        import datacommons_mcp.cli as cli_module

        cli_module._transport = None

        transport = get_transport()
        assert transport is not None
        assert isinstance(transport, StdioTransport)

    def test_get_transport_returns_configured(self):
        """Test get_transport returns configured transport."""
        set_transport(mode="stdio", verbose=True)

        transport = get_transport()
        assert transport.verbose is True
