"""Ports (Interfaces) do Domínio - Contratos para implementações de infraestrutura."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, Self, TypeVar
from uuid import UUID

from vendas.domain.entities.lead import Lead, LeadStatus
from vendas.domain.events import DomainEvent
from vendas.domain.value_objects import Cnpj, Email, Money, Phone

# =============================================================================
# Base Protocols
# =============================================================================


class Entity(Protocol):
    """Protocol base para entidades com ID."""

    id: UUID


TEntity = TypeVar("TEntity")

# Type alias for flexible ID handling (UUID or string)
EntityId = UUID | str


class Repository(Protocol[TEntity]):
    """Protocol base para repositórios."""

    def add(self, entity: TEntity) -> None:
        """Adiciona uma entidade ao repositório."""
        ...

    def get(self, entity_id: EntityId) -> TEntity | None:
        """Busca uma entidade por ID."""
        ...

    def save(self, entity: TEntity) -> None:
        """Salva/atualiza uma entidade existente no repositório."""
        ...

    def remove(self, entity: TEntity) -> None:
        """Remove uma entidade do repositório."""
        ...


# =============================================================================
# Clock Port
# =============================================================================

from .budget_tracker import BudgetTracker
from .clock import Clock

# =============================================================================
# Lead Repository Port
# =============================================================================


@dataclass(frozen=True, slots=True)
class LeadFilter:
    """Filtros para busca de leads."""

    status: LeadStatus | None = None
    statuses: Sequence[LeadStatus] | None = None
    phone: Phone | None = None
    email: Email | None = None
    cnpj: Cnpj | None = None
    assigned_to: UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int = 100
    offset: int = 0


class LeadRepository(Repository[Lead], Protocol):
    """Port para persistência de Leads."""

    def get_by_phone(self, phone: Phone) -> Lead | None:
        """Busca lead por telefone."""
        ...

    def get_by_email(self, email: Email) -> Lead | None:
        """Busca lead por e-mail."""
        ...

    def get_by_cnpj(self, cnpj: Cnpj) -> Lead | None:
        """Busca lead por CNPJ."""
        ...

    def find_by_dedupe_key(self, cnpj: Cnpj | None, phone: Phone | None) -> Lead | None:
        """Busca lead por chave de deduplicação (CNPJ ou telefone)."""
        ...

    def list(self, filter: LeadFilter) -> Sequence[Lead]:
        """Lista leads com filtros e paginação."""
        ...

    def count(self, filter: LeadFilter) -> int:
        """Conta leads com filtros (sem paginação)."""
        ...

    def get_next_for_cadence(
        self,
        limit: int = 100,
    ) -> Sequence[Lead]:
        """Busca próximos leads elegíveis para cadência (status ELIGIBLE)."""
        ...

    def get_for_handoff(
        self,
        limit: int = 100,
    ) -> Sequence[Lead]:
        """Busca leads prontos para handoff (status QUALIFIED)."""
        ...


# =============================================================================
# Conversation Repository Port
# =============================================================================


@dataclass(slots=True)
class Conversation:
    """Entidade de conversa (simplificada para o port)."""

    id: UUID
    lead_id: UUID
    channel: str  # "whatsapp" | "email"
    contact_phone: str
    contact_email: str | None
    state: str  # "open" | "closed" | "handoff"
    current_step: int
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def is_under_human_takeover(self) -> bool:
        """Verifica se a conversa está sob takeover humano (estado handoff)."""
        return self.state == "handoff"

    def add_message(self, sender: str, text: str, timestamp: datetime) -> None:
        """Adiciona uma mensagem à conversa (atualiza last_message_at)."""
        self.last_message_at = timestamp
        self.updated_at = timestamp

    def trigger_handoff(self, reason: str, at: datetime | None = None) -> None:
        """Marca a conversa para handoff humano."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para trigger_handoff")
        self.state = "handoff"
        self.updated_at = at


@dataclass(frozen=True, slots=True)
class Message:
    """Mensagem de uma conversa."""

    id: UUID
    conversation_id: UUID
    direction: str  # "inbound" | "outbound"
    content: str
    message_type: str  # "text" | "image" | "document" | "audio"
    template_name: str | None
    status: str  # "pending" | "sent" | "delivered" | "read" | "failed"
    external_id: str | None  # ID no provedor (Evolution, etc.)
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None


@dataclass(frozen=True, slots=True)
class ConversationFilter:
    """Filtros para busca de conversas."""

    lead_id: UUID | None = None
    channel: str | None = None
    state: str | None = None
    contact_phone: str | None = None
    limit: int = 100
    offset: int = 0


class ConversationRepository(Repository[Conversation], Protocol):
    """Port para persistência de Conversas."""

    def get_by_lead(self, lead_id: EntityId) -> Conversation | None:
        """Busca conversa ativa por lead."""
        ...

    def get_by_lead_id(self, lead_id: EntityId) -> Conversation | None:
        """Alias para get_by_lead para compatibilidade."""
        ...

    def get_by_contact(
        self,
        channel: str,
        contact_phone: str,
    ) -> Conversation | None:
        """Busca conversa por canal e contato."""
        ...

    def list(self, filter: ConversationFilter) -> Sequence[Conversation]:
        """Lista conversas com filtros e paginação."""
        ...

    def add_message(self, message: Message) -> None:
        """Adiciona uma mensagem à conversa."""
        ...

    def get_messages(
        self,
        conversation_id: EntityId,
        limit: int = 100,
        before: datetime | None = None,
    ) -> Sequence[Message]:
        """Busca mensagens de uma conversa (mais recentes primeiro)."""
        ...

    def update_message_status(
        self,
        message_id: EntityId,
        status: str,
        external_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Atualiza status de uma mensagem."""
        ...


# =============================================================================
# Outbox Repository Port
# =============================================================================

from vendas.domain.entities.outbox_message import OutboxMessage


@dataclass(frozen=True, slots=True)
class OutboxFilter:
    """Filtros para busca na outbox."""

    status: str | None = None
    channel: str | None = None
    scheduled_before: datetime | None = None
    limit: int = 100


class OutboxRepository(Repository[OutboxMessage], Protocol):
    """Port para persistência da Outbox (padrão Transactional Outbox)."""

    def add(
        self,
        message: OutboxMessage | None = None,
        *,
        event_type: str | None = None,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        channel: str | None = None,
        destination: str | None = None,
        template_name: str | None = None,
        template_params: dict[str, Any] | None = None,
        max_attempts: int = 3,
        scheduled_at: datetime | None = None,
    ) -> None:
        """Adiciona mensagem à outbox (dentro da mesma transação do domínio).

        Pode ser chamado com um objeto OutboxMessage ou com parâmetros nomeados.
        """
        ...

    def add_message(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        channel: str | None = None,
        destination: str | None = None,
        template_name: str | None = None,
        template_params: dict[str, Any] | None = None,
        max_attempts: int = 3,
        scheduled_at: datetime | None = None,
    ) -> None:
        """Adiciona mensagem à outbox usando parâmetros nomeados (convenience method)."""
        ...

    def get_pending(
        self,
        limit: int = 100,
        channels: Sequence[str] | None = None,
    ) -> Sequence[OutboxMessage]:
        """Busca mensagens pendentes para processamento (ordered by priority, scheduled_at)."""
        ...

    def mark_processing(self, message_id: EntityId) -> bool:
        """Marca mensagem como em processamento (retorna False se já processada)."""
        ...

    def mark_sent(self, message_id: EntityId, external_id: str | None = None) -> None:
        """Marca mensagem como enviada com sucesso."""
        ...

    def mark_failed(
        self,
        message_id: EntityId,
        error: str,
        will_retry: bool,
    ) -> None:
        """Marca mensagem como falhada (incrementa attempts)."""
        ...

    def get_dead_letters(self, limit: int = 100) -> Sequence[OutboxMessage]:
        """Busca mensagens em dead letter (excederam max_attempts)."""
        ...

    def cleanup_old(self, older_than: datetime, statuses: Sequence[str]) -> int:
        """Remove mensagens antigas com status finalizados. Retorna quantidade removida."""
        ...


# =============================================================================
# Message Channel Port
# =============================================================================


@dataclass(frozen=True, slots=True)
class SendResult:
    """Resultado do envio de mensagem."""

    success: bool
    external_id: str | None = None
    error: str | None = None
    error_code: str | None = None


class MessageChannel(Protocol):
    """Port para envio de mensagens via canais (WhatsApp, E-mail, etc.)."""

    @property
    def channel_name(self) -> str:
        """Nome do canal (ex: 'whatsapp', 'email')."""
        ...

    async def send_text(
        self,
        to: str,
        text: str,
    ) -> SendResult:
        """Envia mensagem de texto simples."""
        ...

    async def send_template(
        self,
        to: str,
        template_name: str,
        parameters: dict[str, Any],
    ) -> SendResult:
        """Envia mensagem usando template pré-aprovado."""
        ...

    async def send_media(
        self,
        to: str,
        media_url: str,
        media_type: str,  # "image" | "document" | "audio" | "video"
        caption: str | None = None,
    ) -> SendResult:
        """Envia mídia (imagem, documento, áudio, vídeo)."""
        ...

    async def validate_webhook(self, payload: dict[str, Any]) -> bool:
        """Valida assinatura do webhook do provedor."""
        ...

    async def parse_webhook(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parseia webhook do provedor.
        Retorna dict com: direction, content, message_type, external_id, contact_phone, contact_name
        ou None se não for mensagem de usuário (ex: status update).
        """
        ...


# =============================================================================
# Lead Source Port (Apify)
# =============================================================================


@dataclass(frozen=True, slots=True)
class RawLead:
    """Lead bruto vindo de fonte externa (Apify, etc.)."""

    source: str  # "apify", "manual", "import"
    external_id: str  # ID na fonte original
    name: str
    phone: str  # Será validado/normalizado pelo VO Phone
    email: str | None = None
    cnpj: str | None = None
    company_name: str | None = None
    company_size: str | None = None
    industry: str | None = None
    raw_data: dict[str, Any] | None = None  # Dados originais completos
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class LeadSourceConfig:
    """Configuração para busca de leads."""

    query: str  # Ex: "empresas de tecnologia em São Paulo"
    location: str | None = None
    industry: str | None = None
    company_size: str | None = None
    max_results: int = 100
    filters: dict[str, Any] | None = None


class LeadSource(Protocol):
    """Port para busca de leads em fontes externas (Apify, etc.)."""

    @property
    def source_name(self) -> str:
        """Nome da fonte (ex: 'apify')."""
        ...

    async def search(self, config: LeadSourceConfig) -> AsyncIterator[RawLead]:
        """Busca leads de forma assíncrona (streaming)."""
        ...

    async def get_by_id(self, external_id: str) -> RawLead | None:
        """Busca um lead específico pelo ID externo."""
        ...

    async def health_check(self) -> bool:
        """Verifica se a fonte está disponível."""
        ...


# =============================================================================
# Lead Enricher Port (Firecrawl)
# =============================================================================


@dataclass(frozen=True, slots=True)
class EnrichedLeadData:
    """Dados enriquecidos do lead."""

    company_name: str | None = None
    company_size: str | None = None  # "1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"
    industry: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    description: str | None = None
    technologies: list[str] | None = None
    location: str | None = None
    founded_year: int | None = None
    revenue_range: str | None = None
    raw_data: dict[str, Any] | None = None


class LeadEnricher(Protocol):
    """Port para enriquecimento de leads via fontes externas (Firecrawl, etc.)."""

    @property
    def enricher_name(self) -> str:
        """Nome do enriquecedor (ex: 'firecrawl')."""
        ...

    def enrich(self, website_url: str) -> dict[str, Any] | None:
        """Enriquece lead a partir da URL do site da empresa (síncrono)."""
        ...

    async def enrich_by_domain(self, domain: str) -> EnrichedLeadData | None:
        """Enriquece lead a partir do domínio do site da empresa."""
        ...

    async def enrich_by_cnpj(self, cnpj: Cnpj) -> EnrichedLeadData | None:
        """Enriquece lead a partir do CNPJ (consulta ReceitaWS, etc.)."""
        ...

    async def enrich_by_linkedin(self, linkedin_url: str) -> EnrichedLeadData | None:
        """Enriquece lead a partir do LinkedIn da empresa."""
        ...

    async def health_check(self) -> bool:
        """Verifica se o enriquecedor está disponível."""
        ...


# =============================================================================
# Conversation Agent Port (Gemini)
# =============================================================================


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Contexto para o agente de conversação."""

    lead: Lead
    conversation_history: Sequence[Message]
    current_step: int
    cadence_step_template: str | None
    lead_enriched_data: EnrichedLeadData | None
    knowledge_base: dict[str, Any]  # Base de conhecimento (preços, FAQ, etc.)


@dataclass(frozen=True, slots=True)
class AgentDecision:
    """Decisão do agente de conversação."""

    action: str  # "reply" | "handoff" | "qualify" | "disqualify" | "opt_out" | "wait"
    response_text: str | None = None
    template_name: str | None = None
    template_params: dict[str, Any] | None = None
    handoff_reason: str | None = None
    qualification_score: int | None = None
    qualification_notes: str | None = None
    disqualification_reason: str | None = None
    opt_out_intent: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] | None = None


class ConversationAgent(Protocol):
    """Port para agente de IA que toma decisões na conversação (Gemini, etc.)."""

    @property
    def agent_name(self) -> str:
        """Nome do agente (ex: 'gemini')."""
        ...

    def decide(self, context: AgentContext) -> AgentDecision:
        """Toma decisão baseada no contexto da conversa."""
        ...


# =============================================================================
# Job Queue Port
# =============================================================================


@dataclass(frozen=True, slots=True)
class Job:
    """Job para processamento assíncrono."""

    id: UUID
    name: str  # Nome do job (ex: "send_message", "enrich_lead", "run_cadence")
    payload: dict[str, Any]
    priority: int = 0  # Maior = mais prioritário
    scheduled_at: datetime | None = None  # None = imediato
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: int = 300
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class JobResult:
    """Resultado da execução de um job."""

    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    should_retry: bool = False


class JobQueue(Protocol):
    """Port para enfileiramento de jobs assíncronos."""

    async def enqueue(self, job: Job) -> UUID:
        """Adiciona job à fila. Retorna o ID do job."""
        ...

    async def enqueue_batch(self, jobs: Sequence[Job]) -> list[UUID]:
        """Adiciona múltiplos jobs à fila."""
        ...

    async def dequeue(
        self,
        worker_id: str,
        max_jobs: int = 10,
        queue_names: Sequence[str] | None = None,
    ) -> Sequence[Job]:
        """Remove e retorna jobs da fila para processamento."""
        ...

    async def complete(self, job_id: UUID, result: JobResult) -> None:
        """Marca job como concluído (sucesso ou falha final)."""
        ...

    async def requeue(self, job_id: UUID, delay_seconds: int = 0) -> None:
        """Reencfileira job para retry."""
        ...

    async def get_job(self, job_id: UUID) -> Job | None:
        """Busca job por ID."""
        ...

    async def cancel(self, job_id: UUID) -> bool:
        """Cancela job pendente. Retorna True se cancelado."""
        ...

    async def get_queue_stats(self, queue_name: str | None = None) -> dict[str, int]:
        """Retorna estatísticas da fila (pending, processing, completed, failed)."""
        ...


# =============================================================================
# Unit of Work Port
# =============================================================================


class UnitOfWork(Protocol):
    """Port para gerenciamento de transações e repositórios (Unit of Work pattern)."""

    # Repositórios acessíveis dentro da UoW
    leads: LeadRepository
    conversations: ConversationRepository
    outbox: OutboxRepository
    enrollments: Any
    bookings: Any
    inbound_events: Any
    suppression: Any

    def __enter__(self) -> Self:
        """Inicia a transação (síncrono)."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Finaliza a transação (commit se sem exceção, rollback caso contrário)."""
        ...

    def commit(self) -> None:
        """Commit explícito da transação."""
        ...

    def rollback(self) -> None:
        """Rollback explícito da transação."""
        ...

    def collect_events(self) -> list[DomainEvent]:
        """Coleta eventos de domínio das entidades modificadas nesta UoW."""
        ...


# =============================================================================
# Suppression List Port (referenciado em eligibility_policy.py)
# =============================================================================


class SuppressionListPort(Protocol):
    """Port para verificar se um telefone/email está na lista de supressão."""

    def is_suppressed(self, phone: Phone, email: str | None = None) -> bool:
        """Verifica se o contato está na lista de supressão (opt-out global, DNC, etc.)."""
        ...


# =============================================================================
# Legal Basis Port (referenciado em eligibility_policy.py)
# =============================================================================


class LegalBasisPort(Protocol):
    """Port para verificar se há base legal registrada para o lead."""

    def has_legal_basis(self, lead_id: EntityId, phone: Phone) -> bool:
        """Verifica se existe base legal (consentimento, legítimo interesse, etc.) registrada."""
        ...


# =============================================================================
# Conversation Lock Port
# =============================================================================

from .conversation_lock import ConversationLock

# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AgentContext",
    "AgentDecision",
    "AuthContext",
    "AuthPort",
    "BudgetTracker",
    "Clock",
    "Conversation",
    "ConversationAgent",
    "ConversationFilter",
    "ConversationLock",
    "ConversationRepository",
    "EnrichedLeadData",
    "Entity",
    "Job",
    "JobQueue",
    "JobResult",
    "LeadEnricher",
    "LeadFilter",
    "LeadRepository",
    "LeadSource",
    "LeadSourceConfig",
    "LegalBasisPort",
    "Message",
    "MessageChannel",
    "Money",
    "OutboxFilter",
    "OutboxMessage",
    "OutboxRepository",
    "RawLead",
    "Repository",
    "Role",
    "SendResult",
    "SuppressionListPort",
    "UnitOfWork",
]
