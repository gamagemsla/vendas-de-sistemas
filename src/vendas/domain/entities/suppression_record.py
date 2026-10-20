"""Entidade SuppressionRecord - Registro de telefone/email na lista de supressão (LGPD, opt-out, DNC)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class SuppressionReason(str, Enum):
    """Motivos de supressão."""

    OPT_OUT = "opt_out"  # Lead pediu para sair (qualquer canal)
    DNC = "dnc"  # Do Not Call (lista pública)
    BOUNCE = "bounce"  # E-mail não entregável
    COMPLAINT = "complaint"  # Reclamação de spam
    MANUAL = "manual"  # Adicionado manualmente por admin


@dataclass(slots=True)
class SuppressionRecord:
    """Registro de telefone/email na lista de supressão.

    Attributes:
        id: Identificador único do registro.
        phone_e164: Telefone em formato E.164 (ex: "+5511999999999").
        reason: Motivo da supressão.
        created_at: Timestamp de criação (timezone-aware).
        source: Fonte/origem da supressão (ex: "lead_opted_out", "whatsapp_webhook").
        notes: Notas adicionais.
        expires_at: Timestamp de expiração (None = permanente).
    """

    id: UUID
    phone_e164: str
    reason: SuppressionReason
    created_at: datetime
    source: str | None = None
    notes: str | None = None
    expires_at: datetime | None = None

    @classmethod
    def create(
        cls,
        phone_e164: str,
        reason: SuppressionReason | str,
        source: str | None = None,
        notes: str | None = None,
        expires_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> SuppressionRecord:
        """Factory para criar novo registro de supressão.

        Args:
            created_at: Timestamp de criação (timezone-aware). Se não fornecido, deve ser passado pelo chamador.
        """
        if created_at is None:
            raise ValueError("created_at é obrigatório e deve ser timezone-aware")
        reason_enum = reason if isinstance(reason, SuppressionReason) else SuppressionReason(reason)
        return cls(
            id=uuid4(),
            phone_e164=phone_e164,
            reason=reason_enum,
            source=source.strip() if source and source.strip() else None,
            notes=notes.strip() if notes and notes.strip() else None,
            created_at=created_at,
            expires_at=expires_at,
        )

    def is_active(self, at: datetime) -> bool:
        """Verifica se o registro está ativo (não expirou) no momento 'at'.

        Args:
            at: Timestamp de referência (timezone-aware) para avaliar expiração.
        """
        if self.expires_at is None:
            return True  # Sem expiração = permanente
        return at < self.expires_at

    def is_opt_out(self) -> bool:
        """Verifica se é opt-out (vs DNC, bounce, etc)."""
        return self.reason == SuppressionReason.OPT_OUT

    def extend_expiration(self, new_expires_at: datetime) -> None:
        """Estende a data de expiração."""
        self.expires_at = new_expires_at

    def make_permanent(self) -> None:
        """Remove data de expiração (torna permanente)."""
        self.expires_at = None
