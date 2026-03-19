import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from claude_agent import ClaudeAgent, TOOLS, SYSTEM_PROMPT


class MockContentBlock:
    def __init__(self, text=None, tool_name=None, tool_input=None, tool_id=None):
        if text is not None:
            self.type = "text"
            self.text = text
        else:
            self.type = "tool_use"
            self.name = tool_name
            self.input = tool_input
            self.id = tool_id


class MockUsage:
    def __init__(self, input_tokens=100):
        self.input_tokens = input_tokens


class MockResponse:
    def __init__(self, content, stop_reason="end_turn", input_tokens=100):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = MockUsage(input_tokens)


@pytest.fixture
def mock_executor():
    executor = MagicMock()
    executor.run_command.return_value = {"exit_code": 0, "output": "hello"}
    executor.read_file.return_value = "file content"
    executor.write_file.return_value = None
    executor.list_files.return_value = "file1.txt\nfile2.txt"
    return executor


@pytest.fixture
def mock_conversation():
    from conversation import ConversationManager
    return ConversationManager(compression_threshold=100000, keep_tokens=20000)


@pytest.fixture
def agent(mock_executor, mock_conversation):
    with patch("claude_agent.Anthropic") as mock_anthropic:
        a = ClaudeAgent(
            api_key="test-key",
            model="claude-sonnet-4-20250514",
            docker_executor=mock_executor,
            conversation=mock_conversation,
        )
        yield a, mock_anthropic.return_value


class TestToolExecution:
    def test_run_command(self, agent):
        a, _ = agent
        result = a._execute_tool("run_command", {"command": "echo hello"})
        assert "hello" in result
        a._executor.run_command.assert_called_once_with("echo hello")

    def test_read_file_absolute(self, agent):
        a, _ = agent
        result = a._execute_tool("read_file", {"path": "/workspace/test.txt"})
        assert result == "file content"

    def test_read_file_relative(self, agent):
        a, _ = agent
        result = a._execute_tool("read_file", {"path": "test.txt"})
        a._executor.read_file.assert_called_with("/workspace/test.txt")

    def test_write_file(self, agent):
        a, _ = agent
        result = a._execute_tool("write_file", {"path": "test.txt", "content": "hello"})
        assert "written" in result.lower()
        a._executor.write_file.assert_called_with("/workspace/test.txt", "hello")

    def test_list_files(self, agent):
        a, _ = agent
        result = a._execute_tool("list_files", {"path": "/workspace"})
        assert "file1.txt" in result

    def test_unknown_tool(self, agent):
        a, _ = agent
        result = a._execute_tool("unknown", {})
        assert "unknown" in result.lower()

    def test_file_not_found(self, agent):
        a, _ = agent
        a._executor.read_file.side_effect = FileNotFoundError("not found")
        result = a._execute_tool("read_file", {"path": "nope.txt"})
        assert "not found" in result.lower()

    def test_path_traversal_blocked(self, agent):
        a, _ = agent
        a._executor.read_file.side_effect = ValueError("path traversal blocked")
        result = a._execute_tool("read_file", {"path": "/etc/passwd"})
        assert "blocked" in result.lower()


class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_simple_text_response(self, agent):
        a, mock_client = agent
        mock_client.messages.create.return_value = MockResponse(
            content=[MockContentBlock(text="Hello!")],
            stop_reason="end_turn",
        )
        result = await a.process_message("hi")
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_tool_use_then_text(self, agent):
        a, mock_client = agent
        # First call: tool use
        tool_response = MockResponse(
            content=[
                MockContentBlock(text="Let me run that."),
                MockContentBlock(tool_name="run_command", tool_input={"command": "echo hi"}, tool_id="tool_1"),
            ],
            stop_reason="tool_use",
        )
        # Second call: final text
        text_response = MockResponse(
            content=[MockContentBlock(text="Done! Output was: hello")],
            stop_reason="end_turn",
        )
        mock_client.messages.create.side_effect = [tool_response, text_response]
        result = await a.process_message("run echo hi")
        assert "Done" in result
        assert mock_client.messages.create.call_count == 2


class TestTools:
    def test_tools_defined(self):
        assert len(TOOLS) == 4
        names = [t["name"] for t in TOOLS]
        assert "run_command" in names
        assert "read_file" in names
        assert "write_file" in names
        assert "list_files" in names

    def test_system_prompt_exists(self):
        assert "sandbox" in SYSTEM_PROMPT.lower() or "docker" in SYSTEM_PROMPT.lower()
