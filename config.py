import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

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
