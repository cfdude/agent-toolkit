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
"""Factory for creating transport instances."""

from typing import Any

from .base import BaseTransport, TransportMode
from .stdio import StdioTransport


class TransportFactory:
    """Factory for creating transport instances.

    This factory creates the appropriate transport implementation based
    on the requested mode. It centralizes transport creation and makes
    it easy to add new transport types.

    Example:
        >>> factory = TransportFactory()
        >>> transport = factory.create("stdio", verbose=True)
        >>> # or
        >>> transport = factory.create(TransportMode.SSE, port=8080)
    """

    @staticmethod
    def create(
        mode: TransportMode | str,
        **kwargs: Any,  # noqa: ANN401
    ) -> BaseTransport:
        """Create a transport instance.

        Args:
            mode: The transport mode (as enum or string).
            **kwargs: Additional arguments passed to the transport constructor.

        Returns:
            A configured transport instance.

        Raises:
            ValueError: If the mode is not supported.
            ImportError: If SSE dependencies are not installed.
        """
        # Normalize mode to enum
        if isinstance(mode, str):
            mode = TransportMode(mode.lower())

        if mode == TransportMode.STDIO:
            return StdioTransport(**kwargs)

        if mode == TransportMode.SSE:
            # SSE transport requires optional dependencies
            try:
                from .sse import SSETransport

                return SSETransport(**kwargs)
            except ImportError as e:
                raise ImportError(
                    "SSE transport requires the 'sse' extras. "
                    "Install with: pip install datacommons-mcp[sse]"
                ) from e

        else:
            raise ValueError(f"Unsupported transport mode: {mode}")

    @staticmethod
    def get_available_modes() -> list[TransportMode]:
        """Get list of available transport modes.

        Returns:
            List of TransportMode enum values.
        """
        return list(TransportMode)

    @staticmethod
    def is_mode_available(mode: TransportMode | str) -> bool:
        """Check if a transport mode is available.

        This checks both if the mode is valid and if any required
        dependencies are installed.

        Args:
            mode: The transport mode to check.

        Returns:
            True if the mode can be used.
        """
        if isinstance(mode, str):
            try:
                mode = TransportMode(mode.lower())
            except ValueError:
                return False

        if mode == TransportMode.STDIO:
            return True

        if mode == TransportMode.SSE:
            try:
                import sse_starlette  # noqa: F401

                return True
            except ImportError:
                return False

        return False


def create_transport(
    mode: TransportMode | str = TransportMode.STDIO,
    **kwargs: Any,  # noqa: ANN401
) -> BaseTransport:
    """Convenience function to create a transport.

    This is a shorthand for TransportFactory.create().

    Args:
        mode: The transport mode (default: STDIO).
        **kwargs: Additional arguments for the transport.

    Returns:
        A configured transport instance.

    Example:
        >>> transport = create_transport("stdio", verbose=True)
        >>> transport = create_transport(TransportMode.SSE, port=8080)
    """
    return TransportFactory.create(mode, **kwargs)
