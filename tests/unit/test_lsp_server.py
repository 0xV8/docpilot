"""Unit tests for LSP server implementation.

Tests the Language Server Protocol server for IDE integration including:
- Server initialization and lifecycle
- Message handling (JSON-RPC)
- Code actions
- Hover information
- Completion suggestions
"""

import json
import sys
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from docpilot.lsp.server import DocpilotLSPServer


@pytest.fixture
def lsp_server():
    """Create an LSP server instance."""
    return DocpilotLSPServer()


class TestServerLifecycle:
    """Test LSP server lifecycle management."""

    def test_server_initialization(self, lsp_server):
        """Test server initializes with correct components."""
        assert lsp_server.parser is not None
        assert lsp_server.analyzer is not None
        assert lsp_server.formatter is not None
        assert lsp_server.generator is not None
        assert not lsp_server.running
        assert not lsp_server.initialized

    def test_server_stop(self, lsp_server):
        """Test server can be stopped."""
        lsp_server.running = True
        lsp_server.stop()
        assert not lsp_server.running


class TestMessageHandling:
    """Test JSON-RPC message handling."""

    def test_send_message_format(self, lsp_server):
        """Test that messages are sent in correct JSON-RPC format."""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"test": "data"}
        }

        mock_buffer = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.buffer = mock_buffer

        with patch('sys.stdout', mock_stdout):
            lsp_server._send_message(message)

            # Verify message was written
            assert mock_buffer.write.called
            assert mock_buffer.flush.called

    def test_error_response_format(self, lsp_server):
        """Test error response format."""
        error_response = lsp_server._error_response(1, -32601, "Method not found")

        assert error_response["jsonrpc"] == "2.0"
        assert error_response["id"] == 1
        assert "error" in error_response
        assert error_response["error"]["code"] == -32601
        assert error_response["error"]["message"] == "Method not found"

    @pytest.mark.asyncio
    async def test_handle_unhandled_method(self, lsp_server):
        """Test handling of unknown methods."""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unknown/method",
            "params": {}
        }

        response = await lsp_server._handle_message(message)

        assert response is not None
        assert "error" in response
        assert response["error"]["code"] == -32601


class TestInitialization:
    """Test LSP initialization."""

    def test_initialize_request(self, lsp_server):
        """Test handling of initialize request."""
        msg_id = 1
        params = {
            "processId": 12345,
            "rootUri": "file:///test/project",
            "capabilities": {},
            "clientInfo": {
                "name": "VSCode",
                "version": "1.70.0"
            }
        }

        response = lsp_server._handle_initialize(msg_id, params)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == msg_id
        assert "result" in response
        assert "capabilities" in response["result"]
        assert "serverInfo" in response["result"]

    def test_initialize_capabilities(self, lsp_server):
        """Test that server advertises correct capabilities."""
        response = lsp_server._handle_initialize(1, {})
        capabilities = response["result"]["capabilities"]

        assert "textDocumentSync" in capabilities
        assert "codeActionProvider" in capabilities
        assert "hoverProvider" in capabilities
        assert "completionProvider" in capabilities
        assert capabilities["codeActionProvider"] is True
        assert capabilities["hoverProvider"] is True

    def test_initialize_server_info(self, lsp_server):
        """Test server info in initialize response."""
        response = lsp_server._handle_initialize(1, {})
        server_info = response["result"]["serverInfo"]

        assert server_info["name"] == "docpilot-lsp"
        assert "version" in server_info

    def test_shutdown_request(self, lsp_server):
        """Test handling of shutdown request."""
        response = lsp_server._handle_shutdown(1)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"] is None


class TestCodeActions:
    """Test code action requests."""

    @pytest.mark.asyncio
    async def test_code_action_request(self, lsp_server):
        """Test code action request returns available actions."""
        params = {
            "textDocument": {
                "uri": "file:///test/file.py"
            },
            "range": {
                "start": {"line": 10, "character": 0},
                "end": {"line": 15, "character": 0}
            },
            "context": {
                "diagnostics": []
            }
        }

        response = await lsp_server._handle_code_action(1, params)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert isinstance(response["result"], list)

    @pytest.mark.asyncio
    async def test_code_action_types(self, lsp_server):
        """Test that correct code actions are provided."""
        params = {
            "textDocument": {"uri": "file:///test/file.py"},
            "range": {
                "start": {"line": 10, "character": 0},
                "end": {"line": 15, "character": 0}
            }
        }

        response = await lsp_server._handle_code_action(1, params)
        actions = response["result"]

        # Check for expected actions
        action_titles = [action["title"] for action in actions]
        assert any("Current Function" in title for title in action_titles)
        assert any("Entire File" in title for title in action_titles)

    @pytest.mark.asyncio
    async def test_code_action_commands(self, lsp_server):
        """Test that code actions include commands."""
        params = {
            "textDocument": {"uri": "file:///test/file.py"},
            "range": {
                "start": {"line": 10, "character": 0},
                "end": {"line": 15, "character": 0}
            }
        }

        response = await lsp_server._handle_code_action(1, params)
        actions = response["result"]

        for action in actions:
            assert "command" in action
            assert "title" in action["command"]
            assert "command" in action["command"]
            assert "arguments" in action["command"]


class TestHover:
    """Test hover requests."""

    @pytest.mark.asyncio
    async def test_hover_request(self, lsp_server):
        """Test hover request returns information."""
        params = {
            "textDocument": {
                "uri": "file:///test/file.py"
            },
            "position": {
                "line": 10,
                "character": 5
            }
        }

        response = await lsp_server._handle_hover(1, params)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response

    @pytest.mark.asyncio
    async def test_hover_content_format(self, lsp_server):
        """Test hover content is in markdown format."""
        params = {
            "textDocument": {"uri": "file:///test/file.py"},
            "position": {"line": 10, "character": 5}
        }

        response = await lsp_server._handle_hover(1, params)
        contents = response["result"]["contents"]

        assert "kind" in contents
        assert contents["kind"] == "markdown"
        assert "value" in contents
        assert isinstance(contents["value"], str)


class TestCompletion:
    """Test completion requests."""

    @pytest.mark.asyncio
    async def test_completion_request(self, lsp_server):
        """Test completion request returns suggestions."""
        params = {
            "textDocument": {
                "uri": "file:///test/file.py"
            },
            "position": {
                "line": 10,
                "character": 5
            }
        }

        response = await lsp_server._handle_completion(1, params)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert isinstance(response["result"], list)

    @pytest.mark.asyncio
    async def test_completion_items(self, lsp_server):
        """Test completion items have correct format."""
        params = {
            "textDocument": {"uri": "file:///test/file.py"},
            "position": {"line": 10, "character": 5}
        }

        response = await lsp_server._handle_completion(1, params)
        completions = response["result"]

        for completion in completions:
            assert "label" in completion
            assert "kind" in completion
            assert "insertText" in completion
            assert "insertTextFormat" in completion

    @pytest.mark.asyncio
    async def test_completion_docstring_templates(self, lsp_server):
        """Test that completion includes docstring templates."""
        params = {
            "textDocument": {"uri": "file:///test/file.py"},
            "position": {"line": 10, "character": 5}
        }

        response = await lsp_server._handle_completion(1, params)
        completions = response["result"]

        labels = [c["label"] for c in completions]
        assert any("Google" in label for label in labels)
        assert any("NumPy" in label for label in labels)

    @pytest.mark.asyncio
    async def test_completion_snippet_format(self, lsp_server):
        """Test that completions use snippet format."""
        params = {
            "textDocument": {"uri": "file:///test/file.py"},
            "position": {"line": 10, "character": 5}
        }

        response = await lsp_server._handle_completion(1, params)
        completions = response["result"]

        # Check that snippets have placeholders
        for completion in completions:
            insert_text = completion["insertText"]
            assert "$" in insert_text  # Snippet placeholders use $
            assert completion["insertTextFormat"] == 2  # Snippet format


class TestServerIntegration:
    """Test server integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_initialize_sequence(self, lsp_server):
        """Test full initialization sequence."""
        # Initialize request
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": 12345,
                "rootUri": "file:///test/project"
            }
        }

        init_response = await lsp_server._handle_message(init_msg)
        assert init_response is not None
        assert "result" in init_response

        # Initialized notification
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        }

        initialized_response = await lsp_server._handle_message(initialized_msg)
        assert initialized_response is None  # Notifications don't return responses
        assert lsp_server.initialized

    @pytest.mark.asyncio
    async def test_shutdown_sequence(self, lsp_server):
        """Test shutdown and exit sequence."""
        # Shutdown request
        shutdown_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "shutdown",
            "params": {}
        }

        shutdown_response = await lsp_server._handle_message(shutdown_msg)
        assert shutdown_response is not None
        assert shutdown_response["result"] is None

        # Exit notification
        lsp_server.running = True
        exit_msg = {
            "jsonrpc": "2.0",
            "method": "exit",
            "params": {}
        }

        exit_response = await lsp_server._handle_message(exit_msg)
        assert exit_response is None
        assert not lsp_server.running

    @pytest.mark.asyncio
    async def test_request_error_handling(self, lsp_server):
        """Test that errors are properly handled and returned."""
        # Invalid message format
        invalid_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "textDocument/codeAction",
            "params": {
                # Missing required fields
            }
        }

        # Should not crash, should return valid response
        response = await lsp_server._handle_message(invalid_msg)
        assert response is not None
        assert response["jsonrpc"] == "2.0"


class TestServerComponents:
    """Test server component initialization."""

    def test_parser_initialized(self, lsp_server):
        """Test that parser is correctly initialized."""
        assert lsp_server.parser is not None
        from docpilot.core.parser import PythonParser
        assert isinstance(lsp_server.parser, PythonParser)

    def test_analyzer_initialized(self, lsp_server):
        """Test that analyzer is correctly initialized."""
        assert lsp_server.analyzer is not None
        from docpilot.core.analyzer import CodeAnalyzer
        assert isinstance(lsp_server.analyzer, CodeAnalyzer)

    def test_generator_initialized(self, lsp_server):
        """Test that generator is correctly initialized."""
        assert lsp_server.generator is not None
        from docpilot.core.generator import DocstringGenerator
        assert isinstance(lsp_server.generator, DocstringGenerator)

    def test_formatter_initialized(self, lsp_server):
        """Test that formatter is correctly initialized."""
        assert lsp_server.formatter is not None
        from docpilot.formatters.google import GoogleFormatter
        assert isinstance(lsp_server.formatter, GoogleFormatter)

    def test_mock_provider_used(self, lsp_server):
        """Test that MockLLMProvider is used for instant responses."""
        from docpilot.core.generator import MockLLMProvider
        assert isinstance(lsp_server.generator.llm_provider, MockLLMProvider)
