from typing import Any, Protocol


class ConversationQueryPort(Protocol):
    def get_handoff_conversations(self) -> list[dict[str, Any]]: ...

    def get_conversation_history(self, conversation_id: str) -> list[dict[str, Any]]: ...
