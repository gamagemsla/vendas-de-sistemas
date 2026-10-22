"""Testes unitários para o fluxo completo de Opt-out e Supressão."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from tests.fakes.fakes import FakeClock, InMemoryConversationLock, InMemoryLeadRepository
from vendas.application.commands.handle_inbound import HandleInboundCommand
from vendas.application.commands.process_cadence_step import ProcessCadenceStepCommand
from vendas.domain.entities.cadence_enrollment import CadenceEnrollment, EnrollmentStatus
from vendas.domain.entities.lead import Lead, LeadStatus
from vendas.domain.entities.suppression_record import SuppressionReason, SuppressionRecord
from vendas.domain.policies.opt_out_policy import OptOutPolicy
from vendas.domain.policies.send_window_policy import SendWindowPolicy
from vendas.domain.value_objects import Phone


class FakeSuppressionRepository:
    """Fake repository for suppression list."""

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self.storage: dict[str, SuppressionRecord] = {}

    def add(self, entity: SuppressionRecord) -> None:
        self.storage[entity.phone_e164] = entity

    def is_suppressed(self, phone_e164: str) -> bool:
        now = self._clock.now()
        record = self.storage.get(phone_e164)
        if not record:
            return False
        return record.is_active(now)

    def add_suppression(
        self,
        phone_e164: str,
        reason: SuppressionReason = SuppressionReason.OPT_OUT,
        source: str = "whatsapp_opt_out",
        notes: str | None = None,
    ) -> SuppressionRecord:
        now = self._clock.now()
        record = SuppressionRecord.create(
            phone_e164=phone_e164,
            reason=reason,
            source=source,
            notes=notes,
            expires_at=None,
            created_at=now,
        )
        self.add(record)
        return record


class FakeEnrollmentRepository:
    """Fake repository for cadence enrollments."""

    def __init__(self) -> None:
        self.storage: dict[str, CadenceEnrollment] = {}

    def claim_due(self, now: datetime, batch_size: int = 10) -> list[CadenceEnrollment]:
        due = []
        for enrollment in self.storage.values():
            if enrollment.status == EnrollmentStatus.ACTIVE and enrollment.next_run_at <= now:
                due.append(enrollment)
                if len(due) >= batch_size:
                    break
        return due

    def save(self, enrollment: CadenceEnrollment) -> None:
        self.storage[str(enrollment.id)] = enrollment

    def add(self, enrollment: CadenceEnrollment) -> None:
        self.storage[str(enrollment.id)] = enrollment


class FakeOutboxRepository:
    """Fake outbox repository."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    def add(self, event_type: str, payload: dict, idempotency_key: str) -> None:
        self.messages.append(
            {
                "event_type": event_type,
                "payload": payload,
                "idempotency_key": idempotency_key,
            }
        )


class FakeUoW:
    """Fake Unit of Work for tests."""

    def __init__(
        self,
        leads: InMemoryLeadRepository,
        enrollments: FakeEnrollmentRepository,
        suppression: FakeSuppressionRepository,
        outbox: FakeOutboxRepository,
    ) -> None:
        self.leads = leads
        self.enrollments = enrollments
        self.suppression = suppression
        self.outbox = outbox
        self.inbound_events = None
        self.conversations = None
        # Dummy session for lock factory compatibility
        self.session = object()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def commit(self) -> None:
        pass


class TestOptOutFlow:
    """Testes do fluxo completo de Opt-out."""

    def setup_method(self) -> None:
        self.clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
        self.leads = InMemoryLeadRepository()
        self.enrollments = FakeEnrollmentRepository()
        self.suppression = FakeSuppressionRepository(self.clock)
        self.outbox = FakeOutboxRepository()
        self.uow = FakeUoW(self.leads, self.enrollments, self.suppression, self.outbox)

        # Create a lead
        self.lead = Lead.create(
            name="Test Lead",
            phone=Phone("+5511999999999"),
            cnpj=None,
            email=None,
            at=self.clock.now(),
        )
        self.leads.add(self.lead)

        # Create enrollment
        self.enrollment = CadenceEnrollment.create(
            lead_id=self.lead.id,
            cadence_name="test_cadence",
            next_run_at=self.clock.now(),
            at=self.clock.now(),
        )
        self.enrollments.add(self.enrollment)

    def test_opt_out_detection_registers_suppression_and_marks_lead(self) -> None:
        """Mensagem de opt-out registra na suppression_list e marca lead como OPTED_OUT."""
        # Arrange
        agent = None  # not used because opt-out returns early
        command = HandleInboundCommand(
            uow=self.uow,
            agent=agent,
            knowledge_base=MagicMock(),
            clock=self.clock,
            conversation_lock_factory=lambda _session: InMemoryConversationLock(),
        )

        # Act
        command.execute(
            sender_phone="+5511999999999",
            message_text="PARAR",
            provider_message_id="msg-1",
            at=self.clock.now(),
        )

        # Assert
        # Lead status should be OPTED_OUT
        lead = self.leads.get(self.lead.id)
        assert lead is not None
        assert lead.status == LeadStatus.OPTED_OUT

        # Suppression record should exist
        assert self.suppression.is_suppressed("+5511999999999") is True
        record = self.suppression.storage.get("+5511999999999")
        assert record is not None
        assert record.reason == SuppressionReason.OPT_OUT
        assert record.source == "whatsapp_opt_out"

    def test_process_cadence_step_blocks_when_suppressed(self) -> None:
        """process_cadence_step NÃO enfileira mensagem se telefone na suppression_list."""
        # Arrange: add suppression for the lead's phone
        self.suppression.add_suppression("+5511999999999", reason=SuppressionReason.OPT_OUT)

        # Lead status is still IN_CADENCE (not OPTED_OUT)
        # Need to transition through proper states: NEW -> ENRICHED -> ELIGIBLE -> IN_CADENCE
        self.lead.enrich(company_name="Test Company", at=self.clock.now())
        self.lead.mark_as_eligible(at=self.clock.now())
        self.lead.start_cadence(at=self.clock.now())
        self.leads.save(self.lead)

        send_window_policy = SendWindowPolicy(clock=self.clock)
        command = ProcessCadenceStepCommand(
            uow=self.uow, clock=self.clock, send_window_policy=send_window_policy
        )

        # Act
        processed = command.execute(batch_size=10)

        # Assert
        assert processed == 0
        # Enrollment should be cancelled
        enrollment = self.enrollments.storage.get(str(self.enrollment.id))
        assert enrollment is not None
        assert enrollment.status == EnrollmentStatus.CANCELLED
        # No outbox message should be enqueued
        assert len(self.outbox.messages) == 0

    def test_process_cadence_step_allows_when_not_suppressed(self) -> None:
        """process_cadence_step enfileira mensagem quando telefone NÃO está na suppression_list."""
        # Arrange: lead is IN_CADENCE, no suppression
        # Need to transition through proper states: NEW -> ENRICHED -> ELIGIBLE -> IN_CADENCE
        self.lead.enrich(company_name="Test Company", at=self.clock.now())
        self.lead.mark_as_eligible(at=self.clock.now())
        self.lead.start_cadence(at=self.clock.now())
        self.leads.save(self.lead)

        send_window_policy = SendWindowPolicy(clock=self.clock)
        command = ProcessCadenceStepCommand(
            uow=self.uow, clock=self.clock, send_window_policy=send_window_policy
        )

        # Act
        processed = command.execute(batch_size=10)

        # Assert
        assert processed == 1
        assert len(self.outbox.messages) == 1
        msg = self.outbox.messages[0]
        assert msg["event_type"] == "SEND_CADENCE_MESSAGE"
        assert msg["payload"]["phone"] == "+5511999999999"

    def test_suppression_record_is_active_with_various_expirations(self) -> None:
        """Testa SuppressionRecord.is_active com datas passadas, futuras e expires_at=None."""
        now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Permanent (expires_at=None)
        permanent = SuppressionRecord.create(
            phone_e164="+5511999999999",
            reason=SuppressionReason.OPT_OUT,
            created_at=now,
            expires_at=None,
        )
        assert permanent.is_active(now) is True
        assert permanent.is_active(now + timedelta(days=365)) is True

        # Future expiration
        future = SuppressionRecord.create(
            phone_e164="+5511888888888",
            reason=SuppressionReason.DNC,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
        assert future.is_active(now) is True
        assert future.is_active(now + timedelta(days=15)) is True
        assert future.is_active(now + timedelta(days=31)) is False

        # Past expiration
        past = SuppressionRecord.create(
            phone_e164="+5511777777777",
            reason=SuppressionReason.BOUNCE,
            created_at=now - timedelta(days=60),
            expires_at=now - timedelta(days=1),
        )
        assert past.is_active(now) is False
        assert past.is_active(now - timedelta(days=30)) is True

    def test_opt_out_policy_detects_various_patterns(self) -> None:
        """Testa detecção de vários padrões de opt-out."""
        policy = OptOutPolicy()

        # Explicit stop
        assert policy.detects_opt_out("PARAR") is True
        assert policy.detects_opt_out("SAIR") is True
        assert policy.detects_opt_out("CANCELAR") is True

        # Unsubscribe
        assert policy.detects_opt_out("DESCADASTRAR") is True
        assert policy.detects_opt_out("REMOVER DA LISTA") is True
        assert policy.detects_opt_out("NÃO QUERO RECEBER MAIS") is True

        # No interest
        assert policy.detects_opt_out("NÃO TENHO INTERESSE") is True
        assert policy.detects_opt_out("SEM INTERESSE") is True
        assert policy.detects_opt_out("JÁ TENHO") is True

        # Generic
        assert policy.detects_opt_out("NÃO QUERO") is True

        # False positives
        assert policy.detects_opt_out("NÃO QUERO PARAR") is False
        assert policy.detects_opt_out("QUERO CONTINUAR") is False
        assert policy.detects_opt_out("MANTENHA-ME") is False

        # Empty/None
        assert policy.detects_opt_out("") is False
        assert policy.detects_opt_out(None) is False
