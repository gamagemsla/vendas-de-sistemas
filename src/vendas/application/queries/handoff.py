from typing import Any

from vendas.domain.ports.conversation import ConversationQueryPort


class GetHandoffConversationsQuery:
    def __init__(self, query_port: ConversationQueryPort) -> None:
        self._query_port = query_port

    def execute(self) -> list[dict[str, Any]]:
        return self._query_port.get_handoff_conversations()


class GetConversationHistoryQuery:
    def __init__(self, query_port: ConversationQueryPort) -> None:
        self._query_port = query_port

    def execute(self, conversation_id: str) -> list[dict[str, Any]]:
        return self._query_port.get_conversation_history(conversation_id)
