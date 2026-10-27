"""Testes do pipeline de envio de mensagens de cadência (6 checagens + caminho feliz)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.fakes.fakes import FakeClock, InMemoryLeadRepository
from vendas.application.commands.process_cadence_step import ProcessCadenceStepCommand
from vendas.domain.entities.cadence_enrollment import CadenceEnrollment, EnrollmentStatus
from vendas.domain.entities.lead import Lead
from vendas.domain.policies.daily_cap_policy import DailyCapResult
from vendas.domain.policies.min_interval_policy import MinIntervalResult
from vendas.domain.value_objects.phone import Phone

# ---- Fakes mínimos para os testes ----


class SimpleOutbox:
    def __init__(self):
        self.messages = []

    def add(self, event_type, payload, idempotency_key):
        self.messages.append(
            {"event_type": event_type, "payload": payload, "idempotency_key": idempotency_key}
        )


class FakeEnrollmentRepository:
    def __init__(self):
        self.storage = {}

    def claim_due(self, now, batch_size=10):
        due = []
        for e in self.storage.values():
            if e.status == EnrollmentStatus.ACTIVE and e.next_run_at and e.next_run_at <= now:
                due.append(e)
                if len(due) >= batch_size:
                    break
        return due

    def save(self, enrollment):
        self.storage[str(enrollment.id)] = enrollment

    def add(self, enrollment):
        self.storage[str(enrollment.id)] = enrollment


class FakeSuppressionRepository:
    def __init__(self, suppress=False):
        self._suppress = suppress

    def is_suppressed(self, phone, email=None):
        return self._suppress


class FakeLegalBasisRepository:
    def __init__(self, allowed=True):
        self._allowed = allowed

    def has_legal_basis(self, lead_id, phone):
        return self._allowed


class FakeChannelStatePort:
    def __init__(self, connected=True):
        self._connected = connected

    def is_connected(self, channel):
        return self._connected


class FakeDailyCapPolicy:
    def __init__(self, allowed=True):
        self._allowed = allowed

    def check(self, channel="whatsapp", reference_time=None):
        return DailyCapResult(
            allowed=self._allowed,
            current_count=0,
            cap=1000,
            channel=channel,
            ref_date=reference_time.date() if reference_time else datetime.now().date(),
        )


class FakeMinIntervalPolicy:
    def __init__(self, allowed=True, next_allowed_at=None):
        self._allowed = allowed
        self._next_allowed_at = next_allowed_at

    def check(self, lead_id, channel="whatsapp", reference_time=None):
        return MinIntervalResult(
            allowed=self._allowed,
            last_sent_at=None,
            min_interval=timedelta(seconds=60),
            next_allowed_at=self._next_allowed_at,
        )


class FakeSendWindowPolicy:
    def __init__(self, allowed=True):
        self._allowed = allowed

    def is_allowed(self, ddd, now):
        return self._allowed


class FakeCadencePolicy:
    def get_next_step(self, current_step):
        class StepDef:
            template_name = f"step_{current_step + 1}"

        return StepDef()

    def get_delay_until_next(self, current_step):
        return timedelta(hours=1)


def _make_lead(clock, phone_str="+5511999999999"):
    lead = Lead.create(
        name="Test Lead",
        phone=Phone(phone_str),
        cnpj=None,
        email=None,
        at=clock.now(),
    )
    lead.enrich(company_name="Test Co", at=clock.now())
    lead.mark_as_eligible(at=clock.now())
    return lead


def _make_enrollment(lead_id, clock, next_run_at=None):
    if next_run_at is None:
        next_run_at = clock.now()
    return CadenceEnrollment.create(
        lead_id=lead_id,
        cadence_name="cold_outreach_v1",
        next_run_at=next_run_at,
        at=clock.now(),
    )


# ---- Testes ----


def test_send_blocked_by_suppression_cancels_cadence():
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository(suppress=True)
    legal_basis = FakeLegalBasisRepository(allowed=True)
    channel_state = FakeChannelStatePort(connected=True)
    daily_cap = FakeDailyCapPolicy(allowed=True)
    min_interval = FakeMinIntervalPolicy(allowed=True)
    send_window = FakeSendWindowPolicy(allowed=True)
    cadence_policy = FakeCadencePolicy()

    lead = _make_lead(clock)
    leads.add(lead)
    enrollment = _make_enrollment(lead.id, clock)
    enrollments.add(enrollment)

    class FakeUoW:
        def __init__(self):
            self.leads = leads
            self.enrollments = enrollments
            self.suppression = suppression
            self.outbox = SimpleOutbox()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def commit(self):
            pass

    uow = FakeUoW()
    cmd = ProcessCadenceStepCommand(
        uow=uow,
        clock=clock,
        send_window_policy=send_window,
        cadence_policy=cadence_policy,
        legal_basis_port=legal_basis,
        channel_state_port=channel_state,
        daily_cap_policy=daily_cap,
        min_interval_policy=min_interval,
    )
    processed = cmd.execute(batch_size=10)
    assert processed == 0
    assert enrollment.status == EnrollmentStatus.CANCELLED
    assert enrollment.cancel_reason == "telefone_na_lista_supressao"


def test_send_blocked_by_no_legal_basis_cancels_cadence():
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository(suppress=False)
    legal_basis = FakeLegalBasisRepository(allowed=False)
    channel_state = FakeChannelStatePort(connected=True)
    daily_cap = FakeDailyCapPolicy(allowed=True)
    min_interval = FakeMinIntervalPolicy(allowed=True)
    send_window = FakeSendWindowPolicy(allowed=True)
    cadence_policy = FakeCadencePolicy()

    lead = _make_lead(clock)
    leads.add(lead)
    enrollment = _make_enrollment(lead.id, clock)
    enrollments.add(enrollment)

    class FakeUoW:
        def __init__(self):
            self.leads = leads
            self.enrollments = enrollments
            self.suppression = suppression
            self.outbox = SimpleOutbox()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def commit(self):
            pass

    uow = FakeUoW()
    cmd = ProcessCadenceStepCommand(
        uow=uow,
        clock=clock,
        send_window_policy=send_window,
        cadence_policy=cadence_policy,
        legal_basis_port=legal_basis,
        channel_state_port=channel_state,
        daily_cap_policy=daily_cap,
        min_interval_policy=min_interval,
    )
    processed = cmd.execute(batch_size=10)
    assert processed == 0
    assert enrollment.status == EnrollmentStatus.CANCELLED
    assert enrollment.cancel_reason == "sem_base_legal"


def test_send_blocked_by_outside_window_skips_cycle():
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository(suppress=False)
    legal_basis = FakeLegalBasisRepository(allowed=True)
    channel_state = FakeChannelStatePort(connected=True)
    daily_cap = FakeDailyCapPolicy(allowed=True)
    min_interval = FakeMinIntervalPolicy(allowed=True)
    send_window = FakeSendWindowPolicy(allowed=False)
    cadence_policy = FakeCadencePolicy()

    lead = _make_lead(clock)
    leads.add(lead)
    enrollment = _make_enrollment(lead.id, clock)
    enrollments.add(enrollment)

    class FakeUoW:
        def __init__(self):
            self.leads = leads
            self.enrollments = enrollments
            self.suppression = suppression
            self.outbox = SimpleOutbox()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def commit(self):
            pass

    uow = FakeUoW()
    cmd = ProcessCadenceStepCommand(
        uow=uow,
        clock=clock,
        send_window_policy=send_window,
        cadence_policy=cadence_policy,
        legal_basis_port=legal_basis,
        channel_state_port=channel_state,
        daily_cap_policy=daily_cap,
        min_interval_policy=min_interval,
    )
    processed = cmd.execute(batch_size=10)
    # Deve pular ciclo, não processar, enrollment permanece ACTIVE e next_run_at inalterado
    assert processed == 0
    assert enrollment.status == EnrollmentStatus.ACTIVE


def test_send_blocked_by_daily_cap_postpones_next_run():
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository(suppress=False)
    legal_basis = FakeLegalBasisRepository(allowed=True)
    channel_state = FakeChannelStatePort(connected=True)
    daily_cap = FakeDailyCapPolicy(allowed=False)
    min_interval = FakeMinIntervalPolicy(allowed=True)
    send_window = FakeSendWindowPolicy(allowed=True)
    cadence_policy = FakeCadencePolicy()

    lead = _make_lead(clock)
    leads.add(lead)
    enrollment = _make_enrollment(lead.id, clock)
    enrollments.add(enrollment)

    class FakeUoW:
        def __init__(self):
            self.leads = leads
            self.enrollments = enrollments
            self.suppression = suppression
            self.outbox = SimpleOutbox()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def commit(self):
            pass

    uow = FakeUoW()
    cmd = ProcessCadenceStepCommand(
        uow=uow,
        clock=clock,
        send_window_policy=send_window,
        cadence_policy=cadence_policy,
        legal_basis_port=legal_basis,
        channel_state_port=channel_state,
        daily_cap_policy=daily_cap,
        min_interval_policy=min_interval,
    )
    processed = cmd.execute(batch_size=10)
    assert processed == 0
    # Deve ter reagendado para próximo dia útil 08:00
    assert enrollment.next_run_at is not None
    # Verifica que é dia útil e hora 08:00
    assert enrollment.next_run_at.hour == 8 and enrollment.next_run_at.minute == 0
    assert enrollment.next_run_at.weekday() < 5


def test_send_blocked_by_min_interval_postpones_next_run():
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository(suppress=False)
    legal_basis = FakeLegalBasisRepository(allowed=True)
    channel_state = FakeChannelStatePort(connected=True)
    daily_cap = FakeDailyCapPolicy(allowed=True)
    next_allowed = clock.now() + timedelta(minutes=10)
    min_interval = FakeMinIntervalPolicy(allowed=False, next_allowed_at=next_allowed)
    send_window = FakeSendWindowPolicy(allowed=True)
    cadence_policy = FakeCadencePolicy()

    lead = _make_lead(clock)
    leads.add(lead)
    enrollment = _make_enrollment(lead.id, clock)
    enrollments.add(enrollment)

    class FakeUoW:
        def __init__(self):
            self.leads = leads
            self.enrollments = enrollments
            self.suppression = suppression
            self.outbox = SimpleOutbox()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def commit(self):
            pass

    uow = FakeUoW()
    cmd = ProcessCadenceStepCommand(
        uow=uow,
        clock=clock,
        send_window_policy=send_window,
        cadence_policy=cadence_policy,
        legal_basis_port=legal_basis,
        channel_state_port=channel_state,
        daily_cap_policy=daily_cap,
        min_interval_policy=min_interval,
    )
    processed = cmd.execute(batch_size=10)
    assert processed == 0
    assert enrollment.next_run_at == next_allowed


def test_send_blocked_by_channel_disconnected_postpones_next_run():
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository(suppress=False)
    legal_basis = FakeLegalBasisRepository(allowed=True)
    channel_state = FakeChannelStatePort(connected=False)
    daily_cap = FakeDailyCapPolicy(allowed=True)
    min_interval = FakeMinIntervalPolicy(allowed=True)
    send_window = FakeSendWindowPolicy(allowed=True)
    cadence_policy = FakeCadencePolicy()

    lead = _make_lead(clock)
    leads.add(lead)
    enrollment = _make_enrollment(lead.id, clock)
    enrollments.add(enrollment)

    class FakeUoW:
        def __init__(self):
            self.leads = leads
            self.enrollments = enrollments
            self.suppression = suppression
            self.outbox = SimpleOutbox()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def commit(self):
            pass

    uow = FakeUoW()
    cmd = ProcessCadenceStepCommand(
        uow=uow,
        clock=clock,
        send_window_policy=send_window,
        cadence_policy=cadence_policy,
        legal_basis_port=legal_basis,
        channel_state_port=channel_state,
        daily_cap_policy=daily_cap,
        min_interval_policy=min_interval,
    )
    processed = cmd.execute(batch_size=10)
    assert processed == 0
    # backoff 5 min
    expected = clock.now() + timedelta(minutes=5)
    assert enrollment.next_run_at == expected


def test_send_succeeds_when_all_checks_pass_records_outbox_and_advances_step():
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository(suppress=False)
    legal_basis = FakeLegalBasisRepository(allowed=True)
    channel_state = FakeChannelStatePort(connected=True)
    daily_cap = FakeDailyCapPolicy(allowed=True)
    min_interval = FakeMinIntervalPolicy(allowed=True)
    send_window = FakeSendWindowPolicy(allowed=True)
    cadence_policy = FakeCadencePolicy()

    lead = _make_lead(clock)
    leads.add(lead)
    enrollment = _make_enrollment(lead.id, clock)
    enrollments.add(enrollment)

    outbox = SimpleOutbox()

    class FakeUoW:
        def __init__(self):
            self.leads = leads
            self.enrollments = enrollments
            self.suppression = suppression
            self.outbox = outbox

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def commit(self):
            pass

    uow = FakeUoW()
    cmd = ProcessCadenceStepCommand(
        uow=uow,
        clock=clock,
        send_window_policy=send_window,
        cadence_policy=cadence_policy,
        legal_basis_port=legal_basis,
        channel_state_port=channel_state,
        daily_cap_policy=daily_cap,
        min_interval_policy=min_interval,
    )
    processed = cmd.execute(batch_size=10)
    assert processed == 1
    # outbox deve ter uma mensagem
    assert len(outbox.messages) == 1
    msg = outbox.messages[0]
    assert msg["event_type"] == "SEND_CADENCE_MESSAGE"
    assert msg["payload"]["lead_id"] == lead.id
    # enrollment deve ter avançado step
    assert enrollment.current_step == 1
    assert enrollment.next_run_at is not None
