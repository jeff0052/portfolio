import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from telegram_handler import TelegramHandler, MAX_TELEGRAM_MESSAGE_LENGTH


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.process_message = AsyncMock(return_value="Hello from Claude!")
    agent._conversation = MagicMock()
    return agent


@pytest.fixture
def handler(mock_agent):
    return TelegramHandler(
        bot_token="test-token",
        owner_user_id=12345,
        agent=mock_agent,
    )


def make_update(user_id=12345, text="hello"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    return update


class TestOwnerVerification:
    def test_is_owner(self, handler):
        update = make_update(user_id=12345)
        assert handler._is_owner(update) is True

    def test_is_not_owner(self, handler):
        update = make_update(user_id=99999)
        assert handler._is_owner(update) is False


class TestMessageHandling:
    @pytest.mark.asyncio
    async def test_handle_message_from_owner(self, handler, mock_agent):
        update = make_update(user_id=12345, text="hello")
        await handler._handle_message(update, MagicMock())
        mock_agent.process_message.assert_called_once_with("hello")
        update.message.reply_text.assert_called_once_with("Hello from Claude!")

    @pytest.mark.asyncio
    async def test_handle_message_from_stranger(self, handler, mock_agent):
        update = make_update(user_id=99999, text="hello")
        await handler._handle_message(update, MagicMock())
        mock_agent.process_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_error(self, handler, mock_agent):
        mock_agent.process_message.side_effect = Exception("API error")
        update = make_update(text="hello")
        await handler._handle_message(update, MagicMock())
        reply = update.message.reply_text.call_args[0][0]
        assert "Error" in reply


class TestCommands:
    @pytest.mark.asyncio
    async def test_clear_command(self, handler, mock_agent):
        update = make_update()
        await handler._handle_clear(update, MagicMock())
        mock_agent._conversation.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_command(self, handler):
        update = make_update()
        await handler._handle_start(update, MagicMock())
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_help_command(self, handler):
        update = make_update()
        await handler._handle_help(update, MagicMock())
        update.message.reply_text.assert_called_once()


class TestLongMessages:
    @pytest.mark.asyncio
    async def test_short_message(self, handler):
        update = make_update()
        await handler._send_long_message(update, "short")
        assert update.message.reply_text.call_count == 1

    @pytest.mark.asyncio
    async def test_long_message_split(self, handler):
        long_text = "a" * 5000
        update = make_update()
        await handler._send_long_message(update, long_text)
        assert update.message.reply_text.call_count >= 2


class TestBuildApplication:
    def test_build_application(self, handler):
        with patch("telegram_handler.Application") as mock_app_cls:
            mock_builder = MagicMock()
            mock_app_cls.builder.return_value = mock_builder
            mock_builder.token.return_value = mock_builder
            mock_builder.build.return_value = MagicMock()
            app = handler.build_application()
            assert app is not None
