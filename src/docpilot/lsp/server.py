"""LSP server implementation for docpilot.

This module provides Language Server Protocol support for IDE integration,
enabling features like code actions, hover information, and real-time
docstring generation in supported editors.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import structlog

from docpilot.core.analyzer import CodeAnalyzer
from docpilot.core.generator import DocstringGenerator, MockLLMProvider
from docpilot.core.models import CodeElementType, DocstringStyle
from docpilot.core.parser import PythonParser
from docpilot.formatters.google import GoogleFormatter

logger = structlog.get_logger(__name__)


class DocpilotLSPServer:
    """Language Server Protocol server for docpilot.

    Provides LSP features for IDE integration including:
    - Code actions for generating docstrings
    - Hover information showing what docstring would be generated
    - Completion suggestions for docstring templates

    The server communicates via JSON-RPC over stdin/stdout.
    """

    def __init__(self) -> None:
        """Initialize the LSP server with required components."""
        self.parser = PythonParser()
        self.analyzer = CodeAnalyzer()
        self.formatter = GoogleFormatter()
        # Use MockLLMProvider for instant responses in IDE
        self.generator = DocstringGenerator(
            llm_provider=MockLLMProvider(),
            formatter=self.formatter,
            default_style=DocstringStyle.GOOGLE,
        )
        self._log = logger.bind(component="lsp_server")
        self.running = False
        self.initialized = False

    def start(self) -> None:
        """Start the LSP server and begin listening for requests.

        The server reads JSON-RPC messages from stdin and writes responses to stdout.
        """
        self.running = True
        self._log.info("lsp_server_started")

        try:
            while self.running:
                message = self._read_message()
                if message:
                    response = asyncio.run(self._handle_message(message))
                    if response:
                        self._send_message(response)
        except KeyboardInterrupt:
            self._log.info("lsp_server_interrupted")
        except Exception as e:
            self._log.error("lsp_server_error", error=str(e))
        finally:
            self.running = False
            self._log.info("lsp_server_stopped")

    def stop(self) -> None:
        """Stop the LSP server gracefully."""
        self.running = False
        self._log.info("lsp_server_stopping")

    def _read_message(self) -> dict[str, Any] | None:
        """Read a JSON-RPC message from stdin.

        Returns:
            Parsed JSON message or None if EOF
        """
        try:
            # Read Content-Length header
            header = sys.stdin.buffer.readline().decode("utf-8")
            if not header:
                return None

            if not header.startswith("Content-Length:"):
                self._log.warning("invalid_header", header=header)
                return None

            content_length = int(header.split(":")[1].strip())

            # Read blank line
            sys.stdin.buffer.readline()

            # Read content
            content = sys.stdin.buffer.read(content_length).decode("utf-8")
            message = json.loads(content)

            self._log.debug("message_received", method=message.get("method"))
            return message

        except Exception as e:
            self._log.error("message_read_error", error=str(e))
            return None

    def _send_message(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message to stdout.

        Args:
            message: JSON-RPC message to send
        """
        try:
            content = json.dumps(message)
            content_bytes = content.encode("utf-8")
            content_length = len(content_bytes)

            # Write headers
            sys.stdout.buffer.write(
                f"Content-Length: {content_length}\r\n\r\n".encode("utf-8")
            )
            # Write content
            sys.stdout.buffer.write(content_bytes)
            sys.stdout.buffer.flush()

            self._log.debug("message_sent", method=message.get("method"))

        except Exception as e:
            self._log.error("message_send_error", error=str(e))

    async def _handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle an incoming JSON-RPC message.

        Args:
            message: Incoming JSON-RPC message

        Returns:
            Response message or None if no response needed
        """
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params", {})

        try:
            if method == "initialize":
                return self._handle_initialize(msg_id, params)
            elif method == "initialized":
                self.initialized = True
                return None
            elif method == "shutdown":
                return self._handle_shutdown(msg_id)
            elif method == "exit":
                self.stop()
                return None
            elif method == "textDocument/codeAction":
                return await self._handle_code_action(msg_id, params)
            elif method == "textDocument/hover":
                return await self._handle_hover(msg_id, params)
            elif method == "textDocument/completion":
                return await self._handle_completion(msg_id, params)
            else:
                self._log.warning("unhandled_method", method=method)
                return self._error_response(msg_id, -32601, "Method not found")

        except Exception as e:
            self._log.error("message_handler_error", method=method, error=str(e))
            return self._error_response(msg_id, -32603, f"Internal error: {e}")

    def _handle_initialize(
        self, msg_id: int | str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle initialize request.

        Args:
            msg_id: Message ID
            params: Initialize parameters

        Returns:
            Initialize response
        """
        self._log.info("lsp_initialize", client=params.get("clientInfo"))

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "capabilities": {
                    "textDocumentSync": {
                        "openClose": True,
                        "change": 1,  # Full document sync
                    },
                    "codeActionProvider": True,
                    "hoverProvider": True,
                    "completionProvider": {
                        "triggerCharacters": ['"""', "'''"],
                    },
                },
                "serverInfo": {
                    "name": "docpilot-lsp",
                    "version": "0.2.0",
                },
            },
        }

    def _handle_shutdown(self, msg_id: int | str) -> dict[str, Any]:
        """Handle shutdown request.

        Args:
            msg_id: Message ID

        Returns:
            Shutdown response
        """
        self._log.info("lsp_shutdown")
        return {"jsonrpc": "2.0", "id": msg_id, "result": None}

    async def _handle_code_action(
        self, msg_id: int | str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle code action request to generate docstrings.

        Args:
            msg_id: Message ID
            params: Code action parameters

        Returns:
            Code actions response
        """
        text_document = params.get("textDocument", {})
        uri = text_document.get("uri", "")

        actions = [
            {
                "title": "Generate Docstring for Current Function",
                "kind": "refactor.rewrite",
                "command": {
                    "title": "Generate Docstring",
                    "command": "docpilot.generateDocstring",
                    "arguments": [uri, params.get("range")],
                },
            },
            {
                "title": "Generate Docstrings for Entire File",
                "kind": "refactor.rewrite",
                "command": {
                    "title": "Generate All Docstrings",
                    "command": "docpilot.generateAllDocstrings",
                    "arguments": [uri],
                },
            },
        ]

        return {"jsonrpc": "2.0", "id": msg_id, "result": actions}

    async def _handle_hover(
        self, msg_id: int | str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle hover request to show docstring preview.

        Args:
            msg_id: Message ID
            params: Hover parameters

        Returns:
            Hover response with docstring preview
        """
        # For now, return a simple hover message
        # In a full implementation, we would:
        # 1. Parse the document at the cursor position
        # 2. Find the function/class at that position
        # 3. Generate a docstring preview
        # 4. Return formatted hover content

        hover_content = {
            "kind": "markdown",
            "value": "**docpilot**: Hover over a function or class to see docstring preview\n\n"
            "Use code actions to generate docstrings.",
        }

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"contents": hover_content},
        }

    async def _handle_completion(
        self, msg_id: int | str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle completion request for docstring templates.

        Args:
            msg_id: Message ID
            params: Completion parameters

        Returns:
            Completion items
        """
        completions = [
            {
                "label": '"""Google Style Docstring"""',
                "kind": 15,  # Snippet
                "insertText": '"""\n$1\n\nArgs:\n    $2\n\nReturns:\n    $3\n"""',
                "insertTextFormat": 2,  # Snippet format
            },
            {
                "label": '"""NumPy Style Docstring"""',
                "kind": 15,
                "insertText": '"""\n$1\n\nParameters\n----------\n$2\n\nReturns\n-------\n$3\n"""',
                "insertTextFormat": 2,
            },
        ]

        return {"jsonrpc": "2.0", "id": msg_id, "result": completions}

    def _error_response(
        self, msg_id: int | str | None, code: int, message: str
    ) -> dict[str, Any]:
        """Create an error response.

        Args:
            msg_id: Message ID
            code: Error code
            message: Error message

        Returns:
            Error response
        """
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": code, "message": message},
        }


def start_lsp_server() -> None:
    """Start the docpilot LSP server.

    This function is the entry point for running docpilot as a language server.
    """
    server = DocpilotLSPServer()
    server.start()
