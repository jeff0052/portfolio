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

logger = logging.getLogger(__name__)

MAX_TELEGRAM_MESSAGE_LENGTH = 4096


class TelegramHandler:
    def __init__(self, bot_token: str, owner_user_id: int, agent: ClaudeAgent):
        self._bot_token = bot_token
        self._owner_user_id = owner_user_id
        self._agent = agent

    def _is_owner(self, update: Update) -> bool:
        return update.effective_user and update.effective_user.id == self._owner_user_id

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        await update.message.reply_text(
            "🤖 Claude Agent ready.\n\n"
            "Send me any message and I'll process it.\n"
            "Commands:\n"
            "/clear - Clear conversation history\n"
            "/help - Show this message"
        )

    async def _handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        self._agent._conversation.clear()
        await update.message.reply_text("🗑️ Conversation cleared.")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        await update.message.reply_text(
            "🤖 Claude Agent\n\n"
            "Send me any message and I'll process it using Claude.\n"
            "I can execute code, read/write files, and more.\n\n"
            "Commands:\n"
            "/clear - Clear conversation history\n"
            "/help - Show this help message"
        )

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            logger.warning("Unauthorized user: %s", update.effective_user.id)
            return

        user_message = update.message.text
        if not user_message:
            return

        logger.info("Processing message from owner: %s...", user_message[:50])

        # Send typing indicator
        await update.message.chat.send_action("typing")

        try:
            response = await self._agent.process_message(user_message)
            await self._send_long_message(update, response)
        except Exception as e:
            logger.error("Error processing message: %s", e, exc_info=True)
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")

    async def _send_long_message(self, update: Update, text: str):
        """Split long messages to fit Telegram's limit."""
        if len(text) <= MAX_TELEGRAM_MESSAGE_LENGTH:
            await update.message.reply_text(text)
            return

        # Split by newlines first, then by character limit
        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > MAX_TELEGRAM_MESSAGE_LENGTH:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = f"{current}\n{line}" if current else line
        if current:
            chunks.append(current)

        # Further split any chunks that still exceed the limit
        final_chunks = []
        for chunk in chunks:
            while len(chunk) > MAX_TELEGRAM_MESSAGE_LENGTH:
                final_chunks.append(chunk[:MAX_TELEGRAM_MESSAGE_LENGTH])
                chunk = chunk[MAX_TELEGRAM_MESSAGE_LENGTH:]
            if chunk:
                final_chunks.append(chunk)

        for chunk in final_chunks:
            await update.message.reply_text(chunk)

    def build_application(self) -> Application:
        """Build and return the Telegram application."""
        app = Application.builder().token(self._bot_token).build()
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("clear", self._handle_clear))
        app.add_handler(CommandHandler("help", self._handle_help))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        return app
