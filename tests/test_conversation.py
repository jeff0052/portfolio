import pytest
from conversation import ConversationManager


@pytest.fixture
def manager():
    return ConversationManager(
        compression_threshold=1000,
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
        for i in range(20):
            manager.add_user_message(f"message {i}")
            manager.add_assistant_message(f"response {i}")
        manager.update_token_count(1500)
        summary = "Summary of earlier conversation"
        manager.apply_compression(summary, keep_last_n=4)
        assert manager.get_summary() == summary
        assert len(manager.get_messages()) == 4
        assert manager.total_tokens == 0
