"""Lead Domain Entity - B2B Sales Prospecting Lifecycle Management.

State Machine:
    NEW -> ENRICHED -> ELIGIBLE -> IN_CADENCE -> REPLIED -> QUALIFYING -> QUALIFIED -> HANDOFF -> WON/LOST
    DISQUALIFIED/OPTED_OUT are terminal states reachable from any non-terminal state.
    OPTED_OUT can be called from ANY state (including terminal).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from vendas.domain.events import (
    DomainEvent,
    LeadCreated,
    LeadDisqualified,
    LeadEnriched,
    LeadHandoff,
    LeadLost,
    LeadOptedOut,
    LeadQualified,
    LeadStatusChanged,
    LeadWon,
)
from vendas.domain.value_objects import Cnpj, Email, Phone


class LeadStatus(str, Enum):
    """Estados do ciclo de vida do Lead."""

    NEW = "NEW"
    ENRICHED = "ENRICHED"
    ELIGIBLE = "ELIGIBLE"
    IN_CADENCE = "IN_CADENCE"
    REPLIED = "REPLIED"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    HANDOFF = "HANDOFF"
    WON = "WON"
    LOST = "LOST"
    DISQUALIFIED = "DISQUALIFIED"
    OPTED_OUT = "OPTED_OUT"


# Transições válidas do estado atual para os próximos estados permitidos
VALID_TRANSITIONS: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.NEW: {LeadStatus.ENRICHED, LeadStatus.DISQUALIFIED, LeadStatus.OPTED_OUT},
    LeadStatus.ENRICHED: {LeadStatus.ELIGIBLE, LeadStatus.DISQUALIFIED, LeadStatus.OPTED_OUT},
    LeadStatus.ELIGIBLE: {LeadStatus.IN_CADENCE, LeadStatus.DISQUALIFIED, LeadStatus.OPTED_OUT},
    LeadStatus.IN_CADENCE: {LeadStatus.REPLIED, LeadStatus.DISQUALIFIED, LeadStatus.OPTED_OUT},
    LeadStatus.REPLIED: {LeadStatus.QUALIFYING, LeadStatus.DISQUALIFIED, LeadStatus.OPTED_OUT},
    LeadStatus.QUALIFYING: {LeadStatus.QUALIFIED, LeadStatus.DISQUALIFIED, LeadStatus.OPTED_OUT},
    LeadStatus.QUALIFIED: {LeadStatus.HANDOFF, LeadStatus.DISQUALIFIED, LeadStatus.OPTED_OUT},
    LeadStatus.HANDOFF: {
        LeadStatus.WON,
        LeadStatus.LOST,
        LeadStatus.DISQUALIFIED,
        LeadStatus.OPTED_OUT,
    },
    LeadStatus.WON: set(),
    LeadStatus.LOST: set(),
    LeadStatus.DISQUALIFIED: set(),
    LeadStatus.OPTED_OUT: set(),
}

TERMINAL_STATES: set[LeadStatus] = {
    LeadStatus.WON,
    LeadStatus.LOST,
    LeadStatus.DISQUALIFIED,
    LeadStatus.OPTED_OUT,
}


@dataclass(slots=True)
class Lead:
    """Entidade Lead - Aggregate Root do domínio de prospecção B2B.

    Gerencia o ciclo de vida completo de um lead desde a criação até o fechamento
    (ganho/perdido) ou término (desqualificado/opt-out).

    Attributes:
        id: Identificador único do lead.
        name: Nome do contato/empresa.
        phone: Telefone do contato (Value Object Phone).
        cnpj: CNPJ da empresa (Value Object Cnpj, opcional).
        email: E-mail do contato (Value Object Email, opcional).
        status: Estado atual do lead na máquina de estados.
        company_name: Nome da empresa enriquecido (opcional).
        company_size: Porte da empresa (opcional).
        industry: Setor da empresa (opcional).
        qualification_score: Score de qualificação (0-100).
        qualification_notes: Observações da qualificação.
        assigned_to: ID do vendedor responsável (após handoff).
        handoff_notes: Observações do handoff.
        deal_value: Valor do negócio fechado (em centavos).
        loss_reason: Motivo da perda.
        loss_code: Código de classificação da perda.
        disqualification_reason: Motivo da desqualificação.
        disqualification_code: Código de classificação da desqualificação.
        opt_out_reason: Motivo do opt-out.
        opt_out_channel: Canal pelo qual o opt-out foi feito.
        created_at: Timestamp de criação.
        updated_at: Timestamp da última atualização.
        events: Lista de eventos de domínio não publicados.
    """

    id: UUID
    name: str
    phone: Phone
    cnpj: Cnpj | None
    email: Email | None
    status: LeadStatus = LeadStatus.NEW
    company_name: str | None = None
    company_size: str | None = None
    industry: str | None = None
    qualification_score: int = 0
    qualification_notes: str | None = None
    assigned_to: UUID | None = None
    handoff_notes: str | None = None
    deal_value: int = 0
    loss_reason: str = ""
    loss_code: str | None = None
    disqualification_reason: str = ""
    disqualification_code: str | None = None
    opt_out_reason: str | None = None
    opt_out_channel: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    events: list[DomainEvent] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validações pós-inicialização."""
        if not self.name or not self.name.strip():
            raise ValueError("Nome do lead é obrigatório")
        if self.qualification_score < 0 or self.qualification_score > 100:
            raise ValueError("Score de qualificação deve estar entre 0 e 100")

    @classmethod
    def create(
        cls,
        name: str,
        phone: str | Phone,
        cnpj: str | Cnpj | None = None,
        email: str | Email | None = None,
    ) -> Lead:
        """Factory method para criar um novo Lead.

        Args:
            name: Nome do contato/empresa.
            phone: Telefone (string ou Phone VO).
            cnpj: CNPJ (string ou Cnpj VO, opcional).
            email: E-mail (string ou Email VO, opcional).

        Returns:
            Nova instância de Lead com status NEW e evento LeadCreated.
        """
        phone_vo = phone if isinstance(phone, Phone) else Phone(phone)
        cnpj_vo = cnpj if isinstance(cnpj, Cnpj) else (Cnpj(cnpj) if cnpj else None)
        email_vo = email if isinstance(email, Email) else (Email(email) if email else None)

        lead = cls(
            id=uuid4(),
            name=name.strip(),
            phone=phone_vo,
            cnpj=cnpj_vo,
            email=email_vo,
            status=LeadStatus.NEW,
        )

        lead._add_event(
            LeadCreated(
                aggregate_id=lead.id,
                name=lead.name,
                phone=str(lead.phone),
                cnpj=str(lead.cnpj) if lead.cnpj else None,
                email=str(lead.email) if lead.email else None,
                status=lead.status.value,
            )
        )

        return lead

    @classmethod
    def create_new(
        cls,
        name: str,
        phone: str | Phone,
        cnpj: str | Cnpj | None = None,
        email: str | Email | None = None,
    ) -> Lead:
        """Alias for create() for backward compatibility."""
        return cls.create(name=name, phone=phone, cnpj=cnpj, email=email)

    def enrich_data(self, enrichment_data: dict[str, Any]) -> None:
        """Alias for enrich() using a dict for backward compatibility."""
        self.enrich(
            cnpj=enrichment_data.get("cnpj"),
            email=enrichment_data.get("email"),
            company_name=enrichment_data.get("company_name"),
            company_size=enrichment_data.get("company_size"),
            industry=enrichment_data.get("industry"),
        )

    def mark_as_eligible(self) -> None:
        """Transition lead to ELIGIBLE status if currently ENRICHED."""
        if self.status == LeadStatus.ENRICHED:
            self._transition_to(LeadStatus.ELIGIBLE, reason="Lead marcado como elegível")

    def mark_as_opted_out(self, reason: str | None = None, channel: str | None = None) -> None:
        """Alias for opt_out() for backward compatibility."""
        self.opt_out(reason=reason, channel=channel)

    def _add_event(self, event: DomainEvent) -> None:
        """Adiciona evento à lista de eventos pendentes."""
        self.events.append(event)

    def _transition_to(self, new_status: LeadStatus, reason: str | None = None) -> None:
        """Realiza transição de estado com validação.

        Args:
            new_status: Novo estado para transição.
            reason: Motivo da transição (opcional).

        Raises:
            ValueError: Se a transição não for permitida.
        """
        if self.status == new_status:
            return

        if self.status in TERMINAL_STATES and new_status != LeadStatus.OPTED_OUT:
            raise ValueError(
                f"Não é possível transicionar de {self.status.value} "
                f"(estado terminal) para {new_status.value}"
            )

        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Transição inválida: {self.status.value} -> {new_status.value}. "
                f"Permitidas: {[s.value for s in allowed]}"
            )

        previous_status = self.status
        self.status = new_status
        self.updated_at = datetime.utcnow()

        self._add_event(
            LeadStatusChanged(
                aggregate_id=self.id,
                previous_status=previous_status.value,
                new_status=new_status.value,
                reason=reason,
            )
        )

    def enrich(
        self,
        cnpj: str | Cnpj | None = None,
        email: str | Email | None = None,
        company_name: str | None = None,
        company_size: str | None = None,
        industry: str | None = None,
    ) -> None:
        if self.status not in (LeadStatus.NEW, LeadStatus.ENRICHED):
            raise ValueError(
                f"Enriquecimento só permitido em NEW ou ENRICHED, atual: {self.status.value}"
            )

        if cnpj is not None:
            self.cnpj = cnpj if isinstance(cnpj, Cnpj) else Cnpj(cnpj)
        if email is not None:
            self.email = email if isinstance(email, Email) else Email(email)
        if company_name is not None:
            self.company_name = company_name.strip() if company_name.strip() else None
        if company_size is not None:
            self.company_size = company_size.strip() if company_size.strip() else None
        if industry is not None:
            self.industry = industry.strip() if industry.strip() else None

        self.updated_at = datetime.utcnow()

        if self.status == LeadStatus.NEW:
            self._transition_to(LeadStatus.ENRICHED, reason="Lead enriquecido com dados externos")

        self._add_event(
            LeadEnriched(
                aggregate_id=self.id,
                cnpj=str(self.cnpj) if self.cnpj else None,
                email=str(self.email) if self.email else None,
                company_name=self.company_name,
                company_size=self.company_size,
                industry=self.industry,
            )
        )

    def qualify(self, score: int, notes: str | None = None) -> None:
        if self.status != LeadStatus.QUALIFYING:
            raise ValueError(f"Qualificação só permitida em QUALIFYING, atual: {self.status.value}")

        if not 0 <= score <= 100:
            raise ValueError("Score deve estar entre 0 e 100")

        self.qualification_score = score
        self.qualification_notes = notes.strip() if notes and notes.strip() else None
        self.updated_at = datetime.utcnow()

        self._transition_to(LeadStatus.QUALIFIED, reason=f"Lead qualificado com score {score}")

        self._add_event(
            LeadQualified(
                aggregate_id=self.id,
                qualification_score=score,
                qualification_notes=self.qualification_notes,
            )
        )

    def disqualify(self, reason: str, code: str | None = None) -> None:
        if self.status in TERMINAL_STATES:
            raise ValueError(
                f"Não é possível desqualificar lead em estado terminal: {self.status.value}"
            )

        if not reason or not reason.strip():
            raise ValueError("Motivo da desqualificação é obrigatório")

        self.disqualification_reason = reason.strip()
        self.disqualification_code = code.strip() if code and code.strip() else None
        self.updated_at = datetime.utcnow()

        self._transition_to(LeadStatus.DISQUALIFIED, reason=reason.strip())

        self._add_event(
            LeadDisqualified(
                aggregate_id=self.id,
                reason=reason.strip(),
                disqualification_code=self.disqualification_code,
            )
        )

    def opt_out(self, reason: str | None = None, channel: str | None = None) -> None:
        if self.status == LeadStatus.OPTED_OUT:
            return

        self.opt_out_reason = reason.strip() if reason and reason.strip() else None
        self.opt_out_channel = channel.strip() if channel and channel.strip() else None
        self.updated_at = datetime.utcnow()

        previous_status = self.status
        self.status = LeadStatus.OPTED_OUT

        self._add_event(
            LeadStatusChanged(
                aggregate_id=self.id,
                previous_status=previous_status.value,
                new_status=LeadStatus.OPTED_OUT.value,
                reason=reason,
            )
        )

        self._add_event(
            LeadOptedOut(
                aggregate_id=self.id,
                reason=self.opt_out_reason,
                channel=self.opt_out_channel,
            )
        )

    def handoff(self, assigned_to: UUID, notes: str | None = None) -> None:
        if self.status != LeadStatus.QUALIFIED:
            raise ValueError(f"Handoff só permitido em QUALIFIED, atual: {self.status.value}")

        self.assigned_to = assigned_to
        self.handoff_notes = notes.strip() if notes and notes.strip() else None
        self.updated_at = datetime.utcnow()

        self._transition_to(LeadStatus.HANDOFF, reason=f"Handoff para vendedor {assigned_to}")

        self._add_event(
            LeadHandoff(
                aggregate_id=self.id,
                assigned_to=assigned_to,
                handoff_notes=self.handoff_notes,
            )
        )

    def win(self, deal_value: int) -> None:
        if self.status != LeadStatus.HANDOFF:
            raise ValueError(f"Win só permitido em HANDOFF, atual: {self.status.value}")

        if deal_value < 0:
            raise ValueError("Valor do negócio não pode ser negativo")

        self.deal_value = deal_value
        self.updated_at = datetime.utcnow()

        self._transition_to(LeadStatus.WON, reason=f"Negócio fechado: {deal_value} centavos")

        self._add_event(
            LeadWon(
                aggregate_id=self.id,
                deal_value=deal_value,
                closed_at=datetime.utcnow(),
            )
        )

    def lose(self, reason: str, code: str | None = None) -> None:
        if self.status != LeadStatus.HANDOFF:
            raise ValueError(f"Loss só permitido em HANDOFF, atual: {self.status.value}")

        if not reason or not reason.strip():
            raise ValueError("Motivo da perda é obrigatório")

        self.loss_reason = reason.strip()
        self.loss_code = code.strip() if code and code.strip() else None
        self.updated_at = datetime.utcnow()

        self._transition_to(LeadStatus.LOST, reason=reason.strip())

        self._add_event(
            LeadLost(
                aggregate_id=self.id,
                loss_reason=reason.strip(),
                loss_code=self.loss_code,
            )
        )

    def start_cadence(self) -> None:
        if self.status != LeadStatus.ELIGIBLE:
            raise ValueError(
                f"Iniciar cadência só permitido em ELIGIBLE, atual: {self.status.value}"
            )

        self._transition_to(LeadStatus.IN_CADENCE, reason="Cadência de prospecção iniciada")

    def register_reply(self) -> None:
        if self.status != LeadStatus.IN_CADENCE:
            raise ValueError(
                f"Registrar resposta só permitido em IN_CADENCE, atual: {self.status.value}"
            )

        self._transition_to(LeadStatus.REPLIED, reason="Lead respondeu à prospecção")

    def start_qualification(self) -> None:
        if self.status != LeadStatus.REPLIED:
            raise ValueError(
                f"Iniciar qualificação só permitido em REPLIED, atual: {self.status.value}"
            )

        self._transition_to(LeadStatus.QUALIFYING, reason="Qualificação iniciada")

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    def can_transition_to(self, new_status: LeadStatus) -> bool:
        if self.status == new_status:
            return True
        # OPTED_OUT can be called from ANY state (including terminal)
        if new_status == LeadStatus.OPTED_OUT:
            return True
        if self.status in TERMINAL_STATES:
            return False
        return new_status in VALID_TRANSITIONS.get(self.status, set())

    def get_allowed_transitions(self) -> list[LeadStatus]:
        if self.status in TERMINAL_STATES:
            return [LeadStatus.OPTED_OUT] if self.status != LeadStatus.OPTED_OUT else []
        return list(VALID_TRANSITIONS.get(self.status, set()))

    def clear_events(self) -> list[DomainEvent]:
        events = self.events.copy()
        self.events.clear()
        return events

    def __repr__(self) -> str:
        return f"Lead(id={self.id}, name='{self.name}', status={self.status.value})"
