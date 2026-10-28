"""Implementação do ChannelStatePort usando SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from vendas.domain.ports import ChannelStatePort
from vendas.infrastructure.persistence.orm_models import ChannelState


class SQLAlchemyChannelStatePort(ChannelStatePort):
    """Adaptador que persiste o estado do canal no banco de dados."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _get_session(self) -> Session:
        return self._session_factory()

    def is_connected(self, channel: str = "whatsapp") -> bool:
        with self._get_session() as session:
            stmt = select(ChannelState).where(ChannelState.channel == channel)
            result = session.execute(stmt).scalar_one_or_none()
            return result.connected if result else False

    def set_connection_state(
        self, channel: str, connected: bool, reason: str | None = None
    ) -> None:
        with self._get_session() as session:
            stmt = select(ChannelState).where(ChannelState.channel == channel)
            state = session.execute(stmt).scalar_one_or_none()
            if state is None:
                state = ChannelState(channel=channel, connected=connected, reason=reason)
                session.add(state)
            else:
                state.connected = connected
                state.reason = reason
            session.commit()

    def set_qr_pending(self, channel: str, qr_code: str | None = None) -> None:
        with self._get_session() as session:
            stmt = select(ChannelState).where(ChannelState.channel == channel)
            state = session.execute(stmt).scalar_one_or_none()
            if state is None:
                state = ChannelState(channel=channel, connected=False, qr_code=qr_code)
                session.add(state)
            else:
                state.connected = False
                state.qr_code = qr_code
            session.commit()
