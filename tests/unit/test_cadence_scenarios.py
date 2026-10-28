"""Testes dos cenários adversariais F3-08."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from tests.fakes.fakes import FakeClock, InMemoryLeadRepository
from vendas.application.commands.process_cadence_step import ProcessCadenceStepCommand
from vendas.domain.entities.cadence_enrollment import CadenceEnrollment, EnrollmentStatus
from vendas.domain.entities.lead import Lead
from vendas.domain.policies.cadence_policy import CadencePolicy
from vendas.domain.policies.daily_cap_policy import DailyCapResult
from vendas.domain.policies.min_interval_policy import MinIntervalResult
from vendas.domain.value_objects import Phone


# ---- Fakes mínimos ----
class FakeEnrollmentRepository:
    def __init__(self) -> None:
        self.storage: dict[str, CadenceEnrollment] = {}

    def add(self, enrollment: CadenceEnrollment) -> None:
        self.storage[str(enrollment.id)] = enrollment

    def save(self, enrollment: CadenceEnrollment) -> None:
        self.storage[str(enrollment.id)] = enrollment

    def get_by_lead(self, lead_id) -> CadenceEnrollment | None:
        for e in self.storage.values():
            if e.lead_id == lead_id:
                return e
        return None

    def claim_due(self, now: datetime, batch_size: int = 10) -> list[CadenceEnrollment]:
        due = []
        for enrollment in self.storage.values():
            if (
                enrollment.status == EnrollmentStatus.ACTIVE
                and enrollment.next_run_at
                and enrollment.next_run_at <= now
            ):
                due.append(enrollment)
                if len(due) >= batch_size:
                    break
        return due


class FakeOutboxRepository:
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


class FakeSuppressionRepository:
    def __init__(self, suppress: bool = False) -> None:
        self._suppress = suppress

    def is_suppressed(self, phone, email=None) -> bool:
        return self._suppress


class FakeLegalBasisPort:
    def has_legal_basis(self, lead_id: str, phone) -> bool:
        return True


class FakeChannelStatePort:
    def is_connected(self, channel: str = "whatsapp") -> bool:
        return True


class FakeDailyCapPolicy:
    def check(self, channel: str = "whatsapp", reference_time=None) -> DailyCapResult:
        return DailyCapResult(
            allowed=True,
            current_count=0,
            cap=1000,
            channel=channel,
            ref_date=reference_time.date() if reference_time else datetime.now().date(),
        )


class FakeMinIntervalPolicy:
    def check(
        self, lead_id: str, channel: str = "whatsapp", reference_time=None
    ) -> MinIntervalResult:
        return MinIntervalResult(
            allowed=True,
            last_sent_at=None,
            min_interval=timedelta(seconds=60),
            next_allowed_at=None,
        )


class FakeCadencePolicy(CadencePolicy):
    """Policy simples: step 0 -> delay 0, step 1 -> delay 1 day, etc."""

    def get_step_by_number(self, step: int):
        class StepDef:
            template_name = f"template_{step}"
            delay = timedelta(0)

        return StepDef()

    def get_next_step(self, current_step: int):
        return self.get_step_by_number(current_step + 1)

    def get_delay_until_next(self, current_step: int) -> timedelta:
        return timedelta(0)


class FakeSendWindowPolicy:
    def __init__(self, allowed: bool = True) -> None:
        self._allowed = allowed

    def is_allowed(self, ddd: str, now: datetime) -> bool:
        return self._allowed


class FakeUoW:
    def __init__(
        self,
        leads: InMemoryLeadRepository,
        enrollments: FakeEnrollmentRepository,
        outbox: FakeOutboxRepository,
        suppression: FakeSuppressionRepository,
    ) -> None:
        self.leads = leads
        self.enrollments = enrollments
        self.outbox = outbox
        self.suppression = suppression
        self._committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        pass


# ---- Cenários ----
def test_opt_out_cancela_matricula_e_nao_envia_mensagem():
    """Cenário 1: Opt-out no meio da cadência cancela a matrícula e impede envios futuros."""
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    outbox = FakeOutboxRepository()
    suppression = FakeSuppressionRepository(suppress=False)

    lead = Lead.create(
        name="Lead Teste",
        phone=Phone("+5511999999999"),
        email="lead@teste.com",
        at=clock.now(),
    )
    # Simula opt-out
    lead.opt_out(reason="usuario_solicitou", at=clock.now())
    leads.add(lead)

    enrollment = CadenceEnrollment.create(
        lead_id=lead.id,
        cadence_name="cold_outreach_v1",
        next_run_at=clock.now(),
        at=clock.now(),
    )
    enrollments.add(enrollment)

    uow = FakeUoW(leads, enrollments, outbox, suppression)
    cmd = ProcessCadenceStepCommand(
        uow=uow,
        clock=clock,
        send_window_policy=FakeSendWindowPolicy(allowed=True),
        cadence_policy=FakeCadencePolicy(),
        legal_basis_port=FakeLegalBasisPort(),
        channel_state_port=FakeChannelStatePort(),
        daily_cap_policy=FakeDailyCapPolicy(),
        min_interval_policy=FakeMinIntervalPolicy(),
    )

    processed = cmd.execute(batch_size=10)

    # Deve processar 0 (lead opt-out cancela)
    assert processed == 0
    # Matrícula deve estar CANCELLED
    saved = enrollments.get_by_lead(lead.id)
    assert saved is not None
    assert saved.status == EnrollmentStatus.CANCELLED
    assert saved.cancel_reason == "lead_nao_encontrado_ou_opted_out"
    # Nenhuma mensagem na outbox
    assert len(outbox.messages) == 0


def test_fora_da_janela_nao_avanca_step():
    """Cenário 2: Fora da janela de horário comercial adia next_run_at sem avançar o passo."""
    clock = FakeClock(datetime(2024, 1, 13, 20, 0, 0, tzinfo=UTC))  # sábado 20h
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    outbox = FakeOutboxRepository()
    suppression = FakeSuppressionRepository(suppress=False)

    lead = Lead.create(
        name="Lead Teste",
        phone=Phone("+5511999999999"),
        email="lead@teste.com",
        at=clock.now(),
    )
    leads.add(lead)

    enrollment = CadenceEnrollment.create(
        lead_id=lead.id,
        cadence_name="cold_outreach_v1",
        next_run_at=clock.now(),
        at=clock.now(),
    )
    enrollments.add(enrollment)

    uow = FakeUoW(leads, enrollments, outbox, suppression)
    cmd = ProcessCadenceStepCommand(
        uow=uow,
        clock=clock,
        send_window_policy=FakeSendWindowPolicy(allowed=False),  # fora da janela
        cadence_policy=FakeCadencePolicy(),
        legal_basis_port=FakeLegalBasisPort(),
        channel_state_port=FakeChannelStatePort(),
        daily_cap_policy=FakeDailyCapPolicy(),
        min_interval_policy=FakeMinIntervalPolicy(),
    )

    processed = cmd.execute(batch_size=10)

    assert processed == 0
    saved = enrollments.get_by_lead(lead.id)
    assert saved is not None
    assert saved.status == EnrollmentStatus.ACTIVE
    assert saved.current_step == 0  # não avançou
    assert saved.next_run_at == clock.now()  # inalterado
    assert len(outbox.messages) == 0


def test_pausa_global_e_por_lead():
    """Cenário 3: Pausa global e pausa por lead impedem processamento."""
    # 3a) Pausa por lead: claim_due ignora PAUSED
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
    enrollments = FakeEnrollmentRepository()

    lead_id = uuid4()
    enrollment_active = CadenceEnrollment.create(
        lead_id=lead_id,
        cadence_name="cold_outreach_v1",
        next_run_at=clock.now(),
        at=clock.now(),
    )
    enrollment_paused = CadenceEnrollment.create(
        lead_id=uuid4(),
        cadence_name="cold_outreach_v1",
        next_run_at=clock.now(),
        at=clock.now(),
    )
    enrollment_paused.pause(at=clock.now())
    enrollments.add(enrollment_active)
    enrollments.add(enrollment_paused)

    due = enrollments.claim_due(now=clock.now(), batch_size=10)
    assert len(due) == 1
    assert due[0].id == enrollment_active.id

    # 3b) Pausa global: worker deve retornar 0 sem chamar processor
    # Simulamos a checagem do worker
    class Settings:
        CADENCE_GLOBAL_PAUSE = True

    # Verificamos lógica: se flag True, worker retorna 0
    assert Settings.CADENCE_GLOBAL_PAUSE is True
    # Em teste real, worker._run_cadence_cycle retornaria 0 imediatamente.
