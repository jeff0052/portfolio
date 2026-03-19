# Telegram Claude Agent - Design Spec

## Overview

A personal Telegram bot that acts as a remote Claude AI agent. Users send messages via Telegram, Claude processes them and can autonomously execute commands in a Docker sandbox. Only the owner can use the bot.

## Architecture

Single-process Python application with four core modules:

```
┌─────────────┐     ┌──────────────────────────────┐
│  Telegram   │────▶│  Bot Process (Python)         │
│  (Mobile)   │◀────│                               │
└─────────────┘     │  ├─ TelegramHandler           │
                    │  │   Receive msgs, verify ID   │
                    │  │                             │
                    │  ├─ ConversationManager        │
                    │  │   Multi-turn context mgmt   │
                    │  │                             │
                    │  ├─ ClaudeAgent                │
                    │  │   Claude API + tool use     │
                    │  │                             │
                    │  └─ DockerExecutor             │
                    │      Sandboxed cmd execution   │
                    └──────────────────────────────┘
```

## Module Design

### TelegramHandler (`telegram_handler.py`)

- Library: `python-telegram-bot`
- Validates every message against owner's Telegram user ID; ignores all others silently
- Commands: `/start` (welcome), `/clear` (reset conversation), `/help`
- Long messages (>4096 chars) automatically split into multiple Telegram messages

### ConversationManager (`conversation.py`)

- Maintains conversation history in memory as `list[dict]`
- Tracks token count by summing `usage.input_tokens` from each Claude API response
- **Compression trigger**: when history reaches **100k tokens**
  1. Preserve the most recent ~20k tokens of raw conversation
  2. Send older conversation to Claude to generate a summary
  3. Inject summary into system prompt as prior context
- `/clear` command resets all history and summaries
- Compression threshold configurable in `config.py`

### ClaudeAgent (`claude_agent.py`)

- Library: `anthropic` Python SDK
- Uses Claude API tool use (function calling) to decide when to execute commands
- Defined tools:

| Tool | Parameters | Description |
|------|-----------|-------------|
| `run_command` | `command: str` | Execute shell command in Docker container |
| `read_file` | `path: str` | Read file content from workspace |
| `write_file` | `path: str, content: str` | Write file to workspace |
| `list_files` | `path: str` | List directory contents |

- All file paths validated with `os.path.realpath()` then checked against `/workspace` prefix to prevent path traversal (including symlink escapes)
- Claude model configurable in `config.py` (default: `claude-sonnet-4-20250514`)
- Supports chained tool calls (e.g., write code then execute it)
- System prompt defines role and safety constraints

### DockerExecutor (`docker_executor.py`)

- Library: `docker` Python SDK
- **Session container model**: one long-lived container per conversation session, reaped after 5 minutes idle (avoids 1-3s startup cost per command)
- Base image: `python:3.12-slim`
- Container constraints:
  - `network_disabled=True` — no network access
  - `mem_limit="512m"` — max 512MB memory
  - `cpu_period` / `cpu_quota` — CPU throttling
  - 30-second per-command execution timeout
  - `--read-only` root filesystem, only `/workspace` and `/tmp` (tmpfs, 100MB) are writable
  - `--user 1000:1000` — non-root execution
  - `--cap-drop=ALL` — drop all Linux capabilities
  - `--security-opt=no-new-privileges`
- Host workspace directory (e.g., `~/agent-workspace/`) mounted to `/workspace:rw,nosuid,nodev`
- Container manually removed after capturing output (no `auto_remove` to avoid race conditions)
- **All tool operations** (`run_command`, `read_file`, `write_file`, `list_files`) execute inside the Docker container — never on the host process

## Security Design

### Authentication
- Owner Telegram user ID configured in `.env`
- All messages checked at entry point; non-owner messages silently dropped

### Sandbox Isolation
- Docker containers have no network access
- Resource limits on memory and CPU
- 30-second per-command hard timeout
- Session containers reaped after idle timeout; output captured before manual removal
- Workspace mount is the only host filesystem exposure

### API Key Protection
- Telegram Bot Token and Anthropic API Key stored in `.env`
- `.env` added to `.gitignore`

## Error Handling

- **Claude API failure**: retry up to 2 times with exponential backoff; on final failure, send user a message: "Claude API temporarily unavailable, please retry"
- **Docker daemon unavailable**: on startup check Docker connectivity; if unavailable, bot starts in chat-only mode (no tool execution) and notifies user
- **Container timeout**: force-kill container, return timeout error to Claude for it to report to user
- **Telegram network issues**: `python-telegram-bot` handles reconnection automatically
- **Graceful shutdown (SIGTERM/SIGINT)**: stop accepting new messages, wait for in-flight container to finish (max 30s), then exit
- **Progress feedback**: send Telegram "typing" indicator while Claude is processing; for multi-step tool chains, send intermediate status messages

## Persistence

- v1: conversation history is in-memory only; lost on restart (acceptable for personal use)
- Future option: persist to SQLite if needed

## Logging

- Python `logging` module, level configurable in `config.py` (default: `INFO`)
- Logs to stdout (viewable in terminal)

## File Structure

```
claude-telegram-agent/
├── .env                  # API keys (not in git)
├── .gitignore
├── requirements.txt      # Dependencies
├── config.py             # Configuration (thresholds, user ID, Docker limits)
├── main.py               # Entry point, starts bot
├── telegram_handler.py   # Message handling & auth
├── conversation.py       # Conversation management & compression
├── claude_agent.py       # Claude API & tool use
├── docker_executor.py    # Docker container management
└── Dockerfile            # Base image for execution environment
```

## Dependencies

- `python-telegram-bot` — Telegram Bot API
- `anthropic` — Claude API SDK
- `docker` — Docker SDK for Python
- `python-dotenv` — Environment variable loading

## Deployment

- Runs locally on Mac
- Requires Docker Desktop installed and running
- Started via `python main.py`

## Configuration (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `COMPRESSION_TOKEN_THRESHOLD` | `100000` | Trigger compression at this token count |
| `COMPRESSION_KEEP_TOKENS` | `20000` | Keep this many recent tokens after compression |
| `DOCKER_IMAGE` | `python:3.12-slim` | Base Docker image |
| `DOCKER_MEM_LIMIT` | `512m` | Container memory limit |
| `DOCKER_TIMEOUT` | `30` | Container execution timeout (seconds) |
| `WORKSPACE_DIR` | `~/agent-workspace` | Host directory mounted into containers |
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Claude model to use |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CONTAINER_IDLE_TIMEOUT` | `300` | Seconds before idle session container is reaped |

## Quick Start

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env`, fill in `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `OWNER_USER_ID`
3. Ensure Docker Desktop is running
4. `python main.py`
