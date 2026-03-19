import logging
import sys
import signal
from config import (
    TELEGRAM_BOT_TOKEN,
    ANTHROPIC_API_KEY,
    OWNER_USER_ID,
    CLAUDE_MODEL,
    DOCKER_IMAGE,
    DOCKER_MEM_LIMIT,
    DOCKER_TIMEOUT,
    WORKSPACE_DIR,
    CONTAINER_IDLE_TIMEOUT,
    LOG_LEVEL,
)
from docker_executor import DockerExecutor
from conversation import ConversationManager
from claude_agent import ClaudeAgent
from telegram_handler import TelegramHandler


def setup_logging():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, LOG_LEVEL),
    )
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Claude Telegram Agent")
    logger.info("Owner user ID: %s", OWNER_USER_ID)
    logger.info("Workspace: %s", WORKSPACE_DIR)
    logger.info("Claude model: %s", CLAUDE_MODEL)

    # Initialize components
    executor = DockerExecutor(
        image=DOCKER_IMAGE,
        workspace_dir=WORKSPACE_DIR,
        mem_limit=DOCKER_MEM_LIMIT,
        timeout=DOCKER_TIMEOUT,
        idle_timeout=CONTAINER_IDLE_TIMEOUT,
    )

    # Check Docker availability
    if not executor.is_available():
        logger.error("Docker is not available. Please start Docker Desktop.")
        sys.exit(1)

    conversation = ConversationManager()
    agent = ClaudeAgent(
        api_key=ANTHROPIC_API_KEY,
        model=CLAUDE_MODEL,
        docker_executor=executor,
        conversation=conversation,
    )
    handler = TelegramHandler(
        bot_token=TELEGRAM_BOT_TOKEN,
        owner_user_id=OWNER_USER_ID,
        agent=agent,
    )

    # Cleanup on shutdown
    def shutdown(signum, frame):
        logger.info("Shutting down...")
        executor.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Build and run
    app = handler.build_application()
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
