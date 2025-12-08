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
"""Transport abstraction layer for MCP server communication.

This module provides a unified interface for different transport mechanisms
used by the MCP server, primarily STDIO (standard) and SSE (Server-Sent Events).
"""

from .base import BaseTransport, TransportMode
from .factory import TransportFactory, create_transport
from .stdio import StdioTransport

__all__ = [
    "BaseTransport",
    "TransportFactory",
    "TransportMode",
    "StdioTransport",
    "create_transport",
]
