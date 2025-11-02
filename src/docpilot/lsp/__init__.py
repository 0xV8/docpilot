"""Language Server Protocol (LSP) support for docpilot.

This module provides LSP server implementation for IDE integration,
enabling real-time docstring generation and code actions in editors.
"""

from docpilot.lsp.server import DocpilotLSPServer

__all__ = ["DocpilotLSPServer"]
