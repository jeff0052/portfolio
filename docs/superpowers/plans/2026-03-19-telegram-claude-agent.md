# Telegram Claude Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal Telegram bot that acts as a remote Claude AI agent with Docker-sandboxed command execution.

**Architecture:** Single-process Python app with four modules: TelegramHandler (auth + messaging), ConversationManager (history + compression), ClaudeAgent (Claude API tool use), DockerExecutor (sandboxed execution). All tool operations run inside Docker containers, never on the host.

**Tech Stack:** Python 3.12, python-telegram-bot, anthropic SDK, docker SDK, python-dotenv

**Spec:** `docs/superpowers/specs/2026-03-19-telegram-claude-agent-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `config.py` | All configuration constants, loaded from `.env` |
| `docker_executor.py` | Session container lifecycle, command execution, file operations |
| `conversation.py` | Conversation history storage, token tracking, compression |
| `claude_agent.py` | Claude API calls, tool definitions, tool dispatch loop |
| `telegram_handler.py` | Telegram bot setup, auth, message routing, response splitting |
| `main.py` | Entry point, wiring, graceful shutdown |
| `Dockerfile` | Base image for execution containers |
| `tests/test_config.py` | Config tests |
| `tests/test_docker_executor.py` | DockerExecutor tests |
| `tests/test_conversation.py` | ConversationManager tests |
| `tests/test_claude_agent.py` | ClaudeAgent tests |
| `tests/test_telegram_handler.py` | TelegramHandler tests |
| `tests/test_integration.py` | End-to-end integration tests |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `Dockerfile`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create `requirements.txt`**

```
python-telegram-bot==21.6
anthropic==0.42.0
docker==7.1.0
python-dotenv==1.0.1
pytest==8.3.4
pytest-asyncio==0.24.0
```

- [ ] **Step 2: Create `.env.example`**

```
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
ANTHROPIC_API_KEY=your-anthropic-api-key
OWNER_USER_ID=your-telegram-user-id
```

- [ ] **Step 3: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

RUN useradd -u 1000 -m agent

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

USER agent

CMD ["sleep", "infinity"]
```

- [ ] **Step 5: Create `config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
OWNER_USER_ID = int(os.environ["OWNER_USER_ID"])

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
COMPRESSION_TOKEN_THRESHOLD = int(os.getenv("COMPRESSION_TOKEN_THRESHOLD", "100000"))
COMPRESSION_KEEP_TOKENS = int(os.getenv("COMPRESSION_KEEP_TOKENS", "20000"))
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "claude-agent-sandbox")
DOCKER_MEM_LIMIT = os.getenv("DOCKER_MEM_LIMIT", "512m")
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "30"))
WORKSPACE_DIR = os.path.expanduser(os.getenv("WORKSPACE_DIR", "~/agent-workspace"))
CONTAINER_IDLE_TIMEOUT = int(os.getenv("CONTAINER_IDLE_TIMEOUT", "300"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

- [ ] **Step 6: Write test for config**

```python
# tests/test_config.py
import os
import pytest


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OWNER_USER_ID", "12345")

    # Reload module to pick up new env
    import importlib
    import config
    importlib.reload(config)

    assert config.TELEGRAM_BOT_TOKEN == "test-token"
    assert config.ANTHROPIC_API_KEY == "test-key"
    assert config.OWNER_USER_ID == 12345


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("OWNER_USER_ID", "1")

    import importlib
    import config
    importlib.reload(config)

    assert config.COMPRESSION_TOKEN_THRESHOLD == 100000
    assert config.DOCKER_TIMEOUT == 30
    assert config.CONTAINER_IDLE_TIMEOUT == 300
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 8: Install dependencies and build Docker image**

```bash
pip install -r requirements.txt
docker build -t claude-agent-sandbox .
```

- [ ] **Step 9: Commit**

```bash
git add requirements.txt config.py .env.example .gitignore Dockerfile tests/
git commit -m "feat: project scaffolding with config, Dockerfile, and dependencies"
```

---

### Task 2: DockerExecutor

**Files:**
- Create: `docker_executor.py`
- Create: `tests/test_docker_executor.py`

- [ ] **Step 1: Write failing tests for DockerExecutor**

```python
# tests/test_docker_executor.py
import pytest
from docker_executor import DockerExecutor


@pytest.fixture
def executor(tmp_path):
    """Create executor with a temporary workspace."""
    return DockerExecutor(
        image="python:3.12-slim",
        workspace_dir=str(tmp_path),
        mem_limit="128m",
        timeout=10,
        idle_timeout=30,
    )


class TestRunCommand:
    def test_echo(self, executor):
        result = executor.run_command("echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["output"]

    def test_timeout(self, executor):
        result = executor.run_command("sleep 60")
        assert result["exit_code"] != 0
        assert "timeout" in result["output"].lower()

    def test_nonexistent_command(self, executor):
        result = executor.run_command("nonexistent_cmd_xyz")
        assert result["exit_code"] != 0


class TestFileOperations:
    def test_write_and_read_file(self, executor):
        executor.write_file("/workspace/test.txt", "hello world")
        content = executor.read_file("/workspace/test.txt")
        assert content == "hello world"

    def test_read_nonexistent_file(self, executor):
        with pytest.raises(FileNotFoundError):
            executor.read_file("/workspace/nonexistent.txt")

    def test_list_files(self, executor):
        executor.write_file("/workspace/a.txt", "a")
        executor.write_file("/workspace/b.txt", "b")
        files = executor.list_files("/workspace")
        assert "a.txt" in files
        assert "b.txt" in files

    def test_path_traversal_blocked(self, executor):
        with pytest.raises(ValueError, match="path traversal"):
            executor.read_file("/etc/passwd")

    def test_path_traversal_with_dotdot(self, executor):
        with pytest.raises(ValueError, match="path traversal"):
            executor.read_file("/workspace/../../etc/passwd")


class TestContainerLifecycle:
    def test_container_reuse(self, executor):
        executor.run_command("echo first")
        container_id_1 = executor._container.id
        executor.run_command("echo second")
        container_id_2 = executor._container.id
        assert container_id_1 == container_id_2

    def test_cleanup(self, executor):
        executor.run_command("echo test")
        assert executor._container is not None
        executor.cleanup()
        assert executor._container is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_docker_executor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docker_executor'`

- [ ] **Step 3: Implement DockerExecutor**

```python
# docker_executor.py
import os
import logging
import docker
from docker.errors import ContainerError, NotFound, APIError

logger = logging.getLogger(__name__)


class DockerExecutor:
    def __init__(
        self,
        image: str,
        workspace_dir: str,
        mem_limit: str = "512m",
        timeout: int = 30,
        idle_timeout: int = 300,
    ):
        self._client = docker.from_env()
        self._image = image
        self._workspace_dir = os.path.abspath(workspace_dir)
        self._mem_limit = mem_limit
        self._timeout = timeout
        self._idle_timeout = idle_timeout
        self._container = None

        os.makedirs(self._workspace_dir, exist_ok=True)

    def _ensure_container(self):
        """Start or reuse the session container."""
        if self._container is not None:
            try:
                self._container.reload()
                if self._container.status == "running":
                    return
            except (NotFound, APIError):
                self._container = None

        logger.info("Starting new session container")
        self._container = self._client.containers.run(
            self._image,
            command="sleep infinity",
            detach=True,
            user="1000:1000",
            read_only=True,
            network_disabled=True,
            mem_limit=self._mem_limit,
            cpu_period=100000,
            cpu_quota=50000,
            security_opt=["no-new-privileges"],
            cap_drop=["ALL"],
            volumes={
                self._workspace_dir: {
                    "bind": "/workspace",
                    "mode": "rw,nosuid,nodev",
                }
            },
            tmpfs={"/tmp": "size=100M"},
            working_dir="/workspace",
        )

    def _validate_path(self, path: str) -> str:
        """Validate path is within /workspace. Returns the path."""
        resolved = os.path.realpath(os.path.normpath(path))
        if not resolved.startswith("/workspace"):
            raise ValueError(f"path traversal blocked: {path}")
        return resolved

    def run_command(self, command: str) -> dict:
        """Execute a command in the session container."""
        self._ensure_container()
        try:
            exec_result = self._container.exec_run(
                ["bash", "-c", command],
                workdir="/workspace",
                user="1000:1000",
                demux=True,
                timeout=self._timeout,
            )
            stdout = exec_result.output[0] or b""
            stderr = exec_result.output[1] or b""
            output = (stdout + stderr).decode("utf-8", errors="replace")
            return {
                "exit_code": exec_result.exit_code,
                "output": output,
            }
        except Exception as e:
            if "timeout" in str(e).lower() or "read timed out" in str(e).lower():
                return {
                    "exit_code": -1,
                    "output": f"Timeout: command exceeded {self._timeout}s limit",
                }
            return {
                "exit_code": -1,
                "output": f"Error: {str(e)}",
            }

    def read_file(self, path: str) -> str:
        """Read a file from the workspace via container."""
        self._validate_path(path)
        self._ensure_container()
        result = self.run_command(f"cat '{path}'")
        if result["exit_code"] != 0:
            if "No such file" in result["output"]:
                raise FileNotFoundError(f"File not found: {path}")
            raise RuntimeError(result["output"])
        return result["output"]

    def write_file(self, path: str, content: str) -> None:
        """Write a file to the workspace via container."""
        self._validate_path(path)
        self._ensure_container()
        import base64
        b64 = base64.b64encode(content.encode()).decode()
        result = self.run_command(
            f"mkdir -p $(dirname '{path}') && echo '{b64}' | base64 -d > '{path}'"
        )
        if result["exit_code"] != 0:
            raise RuntimeError(f"Failed to write file: {result['output']}")

    def list_files(self, path: str) -> str:
        """List directory contents via container."""
        self._validate_path(path)
        self._ensure_container()
        result = self.run_command(f"ls -la '{path}'")
        if result["exit_code"] != 0:
            raise RuntimeError(result["output"])
        return result["output"]

    def cleanup(self):
        """Stop and remove the session container."""
        if self._container is not None:
            try:
                self._container.stop(timeout=5)
                self._container.remove(force=True)
            except (NotFound, APIError):
                pass
            self._container = None
            logger.info("Session container cleaned up")

    def is_available(self) -> bool:
        """Check if Docker daemon is reachable."""
        try:
            self._client.ping()
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_docker_executor.py -v`
Expected: PASS (requires Docker Desktop running)

- [ ] **Step 5: Commit**

```bash
git add docker_executor.py tests/test_docker_executor.py
git commit -m "feat: DockerExecutor with session containers and sandboxed file ops"
```

---

### Task 3: ConversationManager

**Files:**
- Create: `conversation.py`
- Create: `tests/test_conversation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_conversation.py
import pytest
from conversation import ConversationManager


@pytest.fixture
def manager():
    return ConversationManager(
        compression_threshold=1000,  # low threshold for testing
        keep_tokens=200,
    )


class TestHistory:
    def test_add_and_get_messages(self, manager):
        manager.add_user_message("hello")
        manager.add_assistant_message("hi there")
        messages = manager.get_messages()
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "hello"}
        assert messages[1] == {"role": "assistant", "content": "hi there"}

    def test_clear(self, manager):
        manager.add_user_message("hello")
        manager.clear()
        assert len(manager.get_messages()) == 0
        assert manager.get_summary() is None

    def test_update_token_count(self, manager):
        manager.add_user_message("hello")
        manager.update_token_count(500)
        assert manager.total_tokens == 500


class TestCompression:
    def test_needs_compression(self, manager):
        manager.update_token_count(1500)
        assert manager.needs_compression() is True

    def test_no_compression_needed(self, manager):
        manager.update_token_count(500)
        assert manager.needs_compression() is False

    def test_get_system_prompt_with_summary(self, manager):
        manager._summary = "User discussed Python projects"
        prompt = manager.get_system_prompt_addition()
        assert "User discussed Python projects" in prompt

    def test_get_system_prompt_without_summary(self, manager):
        prompt = manager.get_system_prompt_addition()
        assert prompt is None

    def test_apply_compression(self, manager):
        # Add many messages
        for i in range(20):
            manager.add_user_message(f"message {i}")
            manager.add_assistant_message(f"response {i}")
        manager.update_token_count(1500)

        summary = "Summary of earlier conversation"
        manager.apply_compression(summary, keep_last_n=4)

        assert manager.get_summary() == summary
        assert len(manager.get_messages()) == 4
        assert manager.total_tokens == 0  # reset after compression
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversation.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ConversationManager**

```python
# conversation.py
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ConversationManager:
    def __init__(
        self,
        compression_threshold: int = 100000,
        keep_tokens: int = 20000,
    ):
        self._messages: list[dict] = []
        self._summary: Optional[str] = None
        self._compression_threshold = compression_threshold
        self._keep_tokens = keep_tokens
        self.total_tokens = 0

    def add_user_message(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    def add_assistant_message(self, text: str) -> None:
        self._messages.append({"role": "assistant", "content": text})

    def add_tool_result(self, tool_use_id: str, content: str) -> None:
        self._messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content,
                }
            ],
        })

    def add_raw_message(self, message: dict) -> None:
        """Add a raw message dict (used for assistant messages with tool_use blocks)."""
        self._messages.append(message)

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def get_summary(self) -> Optional[str]:
        return self._summary

    def get_system_prompt_addition(self) -> Optional[str]:
        if self._summary is None:
            return None
        return f"Summary of earlier conversation:\n{self._summary}"

    def update_token_count(self, input_tokens: int) -> None:
        self.total_tokens = input_tokens

    def needs_compression(self) -> bool:
        return self.total_tokens >= self._compression_threshold

    def get_messages_for_compression(self, keep_last_n: int = 10) -> list[dict]:
        """Return older messages that should be compressed."""
        if len(self._messages) <= keep_last_n:
            return []
        return self._messages[:-keep_last_n]

    def apply_compression(self, summary: str, keep_last_n: int = 10) -> None:
        """Replace older messages with a summary."""
        logger.info(
            "Compressing conversation: %d messages -> summary + %d recent",
            len(self._messages),
            keep_last_n,
        )
        self._summary = summary
        if len(self._messages) > keep_last_n:
            self._messages = self._messages[-keep_last_n:]
        self.total_tokens = 0  # reset, will be recalculated on next API call

    def clear(self) -> None:
        self._messages.clear()
        self._summary = None
        self.total_tokens = 0
        logger.info("Conversation cleared")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_conversation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add conversation.py tests/test_conversation.py
git commit -m "feat: ConversationManager with token-based compression"
```

---

### Task 4: ClaudeAgent

**Files:**
- Create: `claude_agent.py`
- Create: `tests/test_claude_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_claude_agent.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from claude_agent import ClaudeAgent, TOOLS


class TestToolDefinitions:
    def test_tools_defined(self):
        tool_names = [t["name"] for t in TOOLS]
        assert "run_command" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "list_files" in tool_names

    def test_run_command_schema(self):
        tool = next(t for t in TOOLS if t["name"] == "run_command")
        props = tool["input_schema"]["properties"]
        assert "command" in props


class TestToolDispatch:
    def test_dispatch_run_command(self):
        executor = MagicMock()
        executor.run_command.return_value = {"exit_code": 0, "output": "hello"}
        agent = ClaudeAgent.__new__(ClaudeAgent)
        agent._executor = executor
        result = agent._dispatch_tool("run_command", {"command": "echo hello"})
        assert "hello" in result

    def test_dispatch_read_file(self):
        executor = MagicMock()
        executor.read_file.return_value = "file content"
        agent = ClaudeAgent.__new__(ClaudeAgent)
        agent._executor = executor
        result = agent._dispatch_tool("read_file", {"path": "/workspace/test.txt"})
        assert result == "file content"

    def test_dispatch_unknown_tool(self):
        agent = ClaudeAgent.__new__(ClaudeAgent)
        agent._executor = MagicMock()
        result = agent._dispatch_tool("unknown_tool", {})
        assert "unknown tool" in result.lower()


class TestSystemPrompt:
    def test_system_prompt_without_summary(self):
        agent = ClaudeAgent.__new__(ClaudeAgent)
        prompt = agent._build_system_prompt(summary=None)
        assert "assistant" in prompt.lower() or "agent" in prompt.lower()

    def test_system_prompt_with_summary(self):
        agent = ClaudeAgent.__new__(ClaudeAgent)
        prompt = agent._build_system_prompt(summary="User discussed Docker")
        assert "User discussed Docker" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_claude_agent.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ClaudeAgent**

```python
# claude_agent.py
import asyncio
import logging
import anthropic
from typing import Optional
from docker_executor import DockerExecutor
from conversation import ConversationManager

logger = logging.getLogger(__name__)

MAX_API_RETRIES = 2

TOOLS = [
    {
        "name": "run_command",
        "description": "Execute a shell command in the Docker sandbox. Returns exit code and output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file from the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file (must be under /workspace)",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path for the file (must be under /workspace)",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List contents of a directory in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the directory (must be under /workspace)",
                }
            },
            "required": ["path"],
        },
    },
]

SYSTEM_PROMPT_BASE = """You are a helpful AI agent running inside a Telegram bot. You can execute commands and manage files in a sandboxed Docker environment.

Your workspace is at /workspace. All file operations must use absolute paths under /workspace.

When the user asks you to do something that requires running code or commands, use the available tools. You can chain multiple tool calls to accomplish complex tasks.

Be concise in your responses. Report results clearly."""


class ClaudeAgent:
    def __init__(
        self,
        api_key: str,
        model: str,
        executor: DockerExecutor,
        conversation: ConversationManager,
        docker_available: bool = True,
    ):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._executor = executor
        self._conversation = conversation
        self._docker_available = docker_available

    def _build_system_prompt(self, summary: Optional[str] = None) -> str:
        if summary:
            return f"{SYSTEM_PROMPT_BASE}\n\n{summary}"
        return SYSTEM_PROMPT_BASE

    def _dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return the result as a string."""
        try:
            if tool_name == "run_command":
                result = self._executor.run_command(tool_input["command"])
                return f"Exit code: {result['exit_code']}\n{result['output']}"
            elif tool_name == "read_file":
                return self._executor.read_file(tool_input["path"])
            elif tool_name == "write_file":
                self._executor.write_file(tool_input["path"], tool_input["content"])
                return f"File written: {tool_input['path']}"
            elif tool_name == "list_files":
                return self._executor.list_files(tool_input["path"])
            else:
                return f"Unknown tool: {tool_name}"
        except FileNotFoundError as e:
            return f"Error: {e}"
        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            logger.exception("Tool dispatch error")
            return f"Error executing {tool_name}: {e}"

    async def process_message(
        self, user_text: str, on_status: callable = None
    ) -> str:
        """Process a user message through Claude with tool use loop.

        Args:
            user_text: The user's message text
            on_status: Optional callback(status_text) for progress updates

        Returns:
            The final text response from Claude
        """
        self._conversation.add_user_message(user_text)

        tools = TOOLS if self._docker_available else []

        max_iterations = 20
        for iteration in range(max_iterations):
            system = self._build_system_prompt(
                self._conversation.get_system_prompt_addition()
            )
            messages = self._conversation.get_messages()

            response = await self._api_call_with_retry(
                system=system, tools=tools, messages=messages
            )
            if response is None:
                return "Claude API temporarily unavailable, please retry."

            # Track tokens
            self._conversation.update_token_count(response.usage.input_tokens)

            # Check if compression needed
            if self._conversation.needs_compression():
                await self._compress_conversation()

            # Process response
            if response.stop_reason == "end_turn":
                # Extract text from response
                text_parts = [
                    block.text
                    for block in response.content
                    if block.type == "text"
                ]
                assistant_text = "\n".join(text_parts)
                self._conversation.add_assistant_message(assistant_text)
                return assistant_text

            elif response.stop_reason == "tool_use":
                # Store full assistant message (includes tool_use blocks)
                self._conversation.add_raw_message({
                    "role": "assistant",
                    "content": [
                        block.model_dump() for block in response.content
                    ],
                })

                # Execute each tool call
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        if on_status:
                            await on_status(f"Running: {block.name}")
                        logger.info("Tool call: %s(%s)", block.name, block.input)
                        result = self._dispatch_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add tool results as user message
                self._conversation.add_raw_message({
                    "role": "user",
                    "content": tool_results,
                })
            else:
                # Unexpected stop reason
                text_parts = [
                    block.text
                    for block in response.content
                    if block.type == "text"
                ]
                assistant_text = "\n".join(text_parts) if text_parts else "Unexpected response."
                self._conversation.add_assistant_message(assistant_text)
                return assistant_text

        return "Reached maximum tool call iterations. Please try a simpler request."

    async def _api_call_with_retry(self, system, tools, messages):
        """Call Claude API with retry and exponential backoff."""
        for attempt in range(MAX_API_RETRIES + 1):
            try:
                return self._client.messages.create(
                    model=self._model,
                    max_tokens=8192,
                    system=system,
                    tools=tools if tools else anthropic.NOT_GIVEN,
                    messages=messages,
                )
            except (anthropic.APIError, anthropic.APIConnectionError) as e:
                if attempt < MAX_API_RETRIES:
                    wait = 2 ** attempt
                    logger.warning("API call failed (attempt %d), retrying in %ds: %s", attempt + 1, wait, e)
                    await asyncio.sleep(wait)
                else:
                    logger.error("API call failed after %d retries: %s", MAX_API_RETRIES + 1, e)
                    return None

    async def _compress_conversation(self) -> None:
        """Compress older conversation history into a summary."""
        old_messages = self._conversation.get_messages_for_compression(keep_last_n=10)
        if not old_messages:
            return

        logger.info("Compressing %d messages", len(old_messages))
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system="Summarize the following conversation concisely. Preserve key facts, decisions, and context that would be important for continuing the conversation.",
            messages=old_messages,
        )
        summary_text = response.content[0].text
        self._conversation.apply_compression(summary_text, keep_last_n=10)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_claude_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add claude_agent.py tests/test_claude_agent.py
git commit -m "feat: ClaudeAgent with tool use loop and conversation compression"
```

---

### Task 5: TelegramHandler

**Files:**
- Create: `telegram_handler.py`
- Create: `tests/test_telegram_handler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_telegram_handler.py
import pytest
from telegram_handler import split_message, is_authorized


class TestSplitMessage:
    def test_short_message(self):
        result = split_message("hello", max_length=4096)
        assert result == ["hello"]

    def test_long_message(self):
        msg = "a" * 5000
        result = split_message(msg, max_length=4096)
        assert len(result) == 2
        assert len(result[0]) <= 4096
        assert "".join(result) == msg

    def test_split_on_newline(self):
        msg = "line1\n" * 1000
        result = split_message(msg, max_length=4096)
        for part in result:
            assert len(part) <= 4096
        assert len(result) > 1  # should be split into multiple parts


class TestAuthorization:
    def test_authorized_user(self):
        assert is_authorized(12345, owner_id=12345) is True

    def test_unauthorized_user(self):
        assert is_authorized(99999, owner_id=12345) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telegram_handler.py -v`
Expected: FAIL

- [ ] **Step 3: Implement TelegramHandler**

```python
# telegram_handler.py
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from claude_agent import ClaudeAgent
from conversation import ConversationManager

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LENGTH = 4096


def split_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """Split a message into chunks that fit Telegram's limit."""
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        # Try to split at last newline within limit
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1 or split_at == 0:
            split_at = max_length

        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return parts


def is_authorized(user_id: int, owner_id: int) -> bool:
    """Check if a user is the authorized owner."""
    return user_id == owner_id


class TelegramHandler:
    def __init__(
        self,
        bot_token: str,
        owner_id: int,
        agent: ClaudeAgent,
        conversation: ConversationManager,
    ):
        self._owner_id = owner_id
        self._agent = agent
        self._conversation = conversation
        self._app = Application.builder().token(bot_token).build()

        # Register handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("clear", self._cmd_clear))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
        )

    async def _check_auth(self, update: Update) -> bool:
        if not is_authorized(update.effective_user.id, self._owner_id):
            logger.warning("Unauthorized access from user %s", update.effective_user.id)
            return False
        return True

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text(
            "Claude Agent ready. Send me a message and I'll help you."
        )

    async def _cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        self._conversation.clear()
        await update.message.reply_text("Conversation cleared.")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text(
            "Commands:\n"
            "/start - Welcome message\n"
            "/clear - Clear conversation history\n"
            "/help - Show this help\n\n"
            "Send any message to chat with Claude. "
            "I can execute commands and manage files in a sandboxed environment."
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return

        user_text = update.message.text
        logger.info("Message from owner: %s", user_text[:100])

        # Send typing indicator
        await update.message.chat.send_action("typing")

        async def on_status(status: str):
            await update.message.reply_text(f"⏳ {status}")
            await update.message.chat.send_action("typing")

        try:
            response = await self._agent.process_message(user_text, on_status=on_status)
        except Exception as e:
            logger.exception("Error processing message")
            response = f"Error: {e}"

        # Split and send response
        parts = split_message(response)
        for part in parts:
            await update.message.reply_text(part)

    def run(self):
        """Start the bot polling loop."""
        logger.info("Starting Telegram bot")
        self._app.run_polling(drop_pending_updates=True)

    async def stop(self):
        """Stop the bot gracefully."""
        await self._app.stop()
        await self._app.shutdown()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_telegram_handler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add telegram_handler.py tests/test_telegram_handler.py
git commit -m "feat: TelegramHandler with auth, commands, and message splitting"
```

---

### Task 6: Main Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement main.py**

```python
# main.py
import logging
import signal
import sys
import config
from docker_executor import DockerExecutor
from conversation import ConversationManager
from claude_agent import ClaudeAgent
from telegram_handler import TelegramHandler

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    # Initialize DockerExecutor
    executor = DockerExecutor(
        image=config.DOCKER_IMAGE,
        workspace_dir=config.WORKSPACE_DIR,
        mem_limit=config.DOCKER_MEM_LIMIT,
        timeout=config.DOCKER_TIMEOUT,
        idle_timeout=config.CONTAINER_IDLE_TIMEOUT,
    )

    docker_available = executor.is_available()
    if not docker_available:
        logger.warning("Docker not available — running in chat-only mode (no tool execution)")

    # Initialize ConversationManager
    conversation = ConversationManager(
        compression_threshold=config.COMPRESSION_TOKEN_THRESHOLD,
        keep_tokens=config.COMPRESSION_KEEP_TOKENS,
    )

    # Initialize ClaudeAgent
    agent = ClaudeAgent(
        api_key=config.ANTHROPIC_API_KEY,
        model=config.CLAUDE_MODEL,
        executor=executor,
        conversation=conversation,
        docker_available=docker_available,
    )

    # Initialize and run TelegramHandler
    handler = TelegramHandler(
        bot_token=config.TELEGRAM_BOT_TOKEN,
        owner_id=config.OWNER_USER_ID,
        agent=agent,
        conversation=conversation,
    )

    def shutdown(signum, frame):
        logger.info("Shutting down...")
        executor.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Bot starting — workspace: %s", config.WORKSPACE_DIR)
    handler.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('main.py').read()); print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: main entry point with graceful shutdown"
```

---

### Task 7: Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from docker_executor import DockerExecutor
from conversation import ConversationManager
from claude_agent import ClaudeAgent


@pytest.fixture
def workspace(tmp_path):
    return str(tmp_path)


@pytest.fixture
def executor(workspace):
    e = DockerExecutor(
        image="python:3.12-slim",
        workspace_dir=workspace,
        mem_limit="128m",
        timeout=10,
        idle_timeout=30,
    )
    yield e
    e.cleanup()


@pytest.fixture
def conversation():
    return ConversationManager(compression_threshold=100000, keep_tokens=20000)


class TestEndToEnd:
    def test_executor_and_conversation_together(self, executor, conversation):
        """Verify DockerExecutor and ConversationManager work together."""
        # Write a file via executor
        executor.write_file("/workspace/hello.py", 'print("hello world")')

        # Run the file
        result = executor.run_command("python /workspace/hello.py")
        assert result["exit_code"] == 0
        assert "hello world" in result["output"]

        # Track in conversation
        conversation.add_user_message("run hello.py")
        conversation.add_assistant_message(result["output"])
        assert len(conversation.get_messages()) == 2

    def test_file_persistence_in_session(self, executor):
        """Files persist within a session container."""
        executor.write_file("/workspace/data.txt", "persistent data")
        content = executor.read_file("/workspace/data.txt")
        assert content == "persistent data"

        # Run a command that reads the file
        result = executor.run_command("cat /workspace/data.txt")
        assert "persistent data" in result["output"]
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: PASS (requires Docker)

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for executor + conversation"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 2: Verify bot starts (requires real `.env`)**

```bash
cp .env.example .env
# Fill in real values, then:
python main.py
```
Expected: Bot starts, logs "Bot starting", connects to Telegram

- [ ] **Step 3: Test via Telegram**

Send `/start` to the bot — should respond with welcome message.
Send "what files are in the workspace?" — should use `list_files` tool and respond.
Send `/clear` — should confirm conversation cleared.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: Telegram Claude Agent v1 complete"
```
