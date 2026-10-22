from typing import Any

from sqlalchemy.orm import Session

from vendas.infrastructure.persistence.orm_models import ConversationModel, MessageModel


class SqlAlchemyConversationQuery:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_handoff_conversations(self) -> list[dict[str, Any]]:
        conversations = (
            self._session.query(ConversationModel)
            .filter(ConversationModel.state == "HANDOFF")
            .all()
        )
        result = []
        for c in conversations:
            lead = c.lead
            result.append(
                {
                    "id": str(c.id),
                    "lead_id": str(c.lead_id) if c.lead_id else None,
                    "lead_name": lead.name if lead else "Desconhecido",
                    "contact_phone": c.contact_phone,
                    "channel": c.channel.value if hasattr(c.channel, "value") else str(c.channel),
                }
            )
        return result

    def get_conversation_history(self, conversation_id: str) -> list[dict[str, Any]]:
        conv = (
            self._session.query(ConversationModel)
            .filter(ConversationModel.id == conversation_id)
            .first()
        )
        if not conv:
            return []
        messages = (
            self._session.query(MessageModel)
            .filter(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
            .all()
        )
        history = []
        for m in messages:
            direction = "outbound" if m.direction.value == "outbound" else "inbound"
            history.append(
                {
                    "id": str(m.id),
                    "direction": direction,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
            )
        return history
