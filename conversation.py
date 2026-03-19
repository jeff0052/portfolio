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
        if len(self._messages) <= keep_last_n:
            return []
        return self._messages[:-keep_last_n]

    def apply_compression(self, summary: str, keep_last_n: int = 10) -> None:
        logger.info(
            "Compressing conversation: %d messages -> summary + %d recent",
            len(self._messages),
            keep_last_n,
        )
        self._summary = summary
        if len(self._messages) > keep_last_n:
            self._messages = self._messages[-keep_last_n:]
        self.total_tokens = 0

    def clear(self) -> None:
        self._messages.clear()
        self._summary = None
        self.total_tokens = 0
        logger.info("Conversation cleared")
