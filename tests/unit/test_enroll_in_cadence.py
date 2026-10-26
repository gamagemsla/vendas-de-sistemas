"""Testes unitários para EnrollInCadenceCommand."""

from datetime import UTC, datetime

from tests.fakes.fakes import FakeClock, InMemoryLeadRepository
from vendas.application.commands.enroll_in_cadence import EnrollInCadenceCommand
from vendas.domain.entities.cadence_enrollment import CadenceEnrollment, EnrollmentStatus
from vendas.domain.entities.lead import Lead, LeadStatus
from vendas.domain.policies.cadence_policy import CadencePolicy
from vendas.domain.policies.eligibility_policy import EligibilityPolicy
from vendas.domain.value_objects import Phone


class FakeEnrollmentRepository:
    """Fake repository for cadence enrollments."""

    def __init__(self) -> None:
        self.storage: dict[str, CadenceEnrollment] = {}

    def get_by_lead(self, lead_id) -> CadenceEnrollment | None:
        for enrollment in self.storage.values():
            if enrollment.lead_id == lead_id:
                return enrollment
        return None

    def add(self, enrollment: CadenceEnrollment) -> None:
        self.storage[str(enrollment.id)] = enrollment


class FakeSuppressionRepository:
    """Fake suppression repository that never suppresses."""

    def is_suppressed(self, phone, email: str | None = None) -> bool:
        return False


class FakeLegalBasisRepository:
    """Fake legal basis repository that always returns True."""

    def has_legal_basis(self, lead_id, phone) -> bool:
        return True


class FakeUoW:
    """Fake Unit of Work for tests."""

    def __init__(
        self,
        leads: InMemoryLeadRepository,
        enrollments: FakeEnrollmentRepository,
        suppression: FakeSuppressionRepository,
        legal_basis: FakeLegalBasisRepository,
    ) -> None:
        self.leads = leads
        self.enrollments = enrollments
        self.suppression = suppression
        self.legal_basis = legal_basis

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def commit(self) -> None:
        pass


def _make_eligible_lead(clock: FakeClock) -> Lead:
    lead = Lead.create(
        name="Test Lead",
        phone=Phone("+5511999999999"),
        cnpj=None,
        email=None,
        at=clock.now(),
    )
    lead.enrich(company_name="Test Company", at=clock.now())
    lead.mark_as_eligible(at=clock.now())
    return lead


def test_lead_ineligible_not_enrolled():
    """Lead inelegível (fora do ICP ou sem base legal) NÃO entra na cadência e é desqualificado."""
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository()

    class FakeLegalBasisFalse:
        def has_legal_basis(self, lead_id, phone) -> bool:
            return False

    legal_basis = FakeLegalBasisFalse()
    uow = FakeUoW(leads, enrollments, suppression, legal_basis)

    # Lead sem enriquecimento -> inelegível
    lead = Lead.create(
        name="Bad Lead",
        phone=Phone("+5511999999999"),
        cnpj=None,
        email=None,
        at=clock.now(),
    )
    leads.add(lead)

    eligibility_policy = EligibilityPolicy(
        suppression_port=suppression,
        legal_basis_port=legal_basis,
    )
    cadence_policy = CadencePolicy()
    command = EnrollInCadenceCommand(
        uow=uow,
        clock=clock,
        eligibility_policy=eligibility_policy,
        cadence_policy=cadence_policy,
    )

    result = command.execute(str(lead.id), "cold_outreach_b2b@v1.0.0")
    assert result is False
    # Lead deve ter sido desqualificado
    saved = leads.get(lead.id)
    assert saved is not None
    assert saved.status == LeadStatus.DISQUALIFIED
    # Nenhuma matrícula criada
    assert len(enrollments.storage) == 0


def test_duplicate_enrollment_prevented():
    """Lead já matriculado ativamente não recebe matrícula duplicada."""
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository()
    legal_basis = FakeLegalBasisRepository()
    uow = FakeUoW(leads, enrollments, suppression, legal_basis)

    lead = _make_eligible_lead(clock)
    leads.add(lead)

    # Primeira inscrição
    eligibility_policy = EligibilityPolicy(
        suppression_port=suppression,
        legal_basis_port=legal_basis,
    )
    cadence_policy = CadencePolicy()
    command = EnrollInCadenceCommand(
        uow=uow,
        clock=clock,
        eligibility_policy=eligibility_policy,
        cadence_policy=cadence_policy,
    )
    result1 = command.execute(str(lead.id), "cold_outreach_b2b@v1.0.0")
    assert result1 is True
    assert len(enrollments.storage) == 1

    # Segunda tentativa deve falhar silenciosamente
    result2 = command.execute(str(lead.id), "cold_outreach_b2b@v1.0.0")
    assert result2 is False
    assert len(enrollments.storage) == 1  # não duplicou


def test_eligible_lead_enrolled_successfully():
    """Lead elegível é matriculado com sucesso, agenda o passo 1 via Clock e transiciona para IN_CADENCE."""
    clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
    leads = InMemoryLeadRepository()
    enrollments = FakeEnrollmentRepository()
    suppression = FakeSuppressionRepository()
    legal_basis = FakeLegalBasisRepository()
    uow = FakeUoW(leads, enrollments, suppression, legal_basis)

    lead = _make_eligible_lead(clock)
    leads.add(lead)

    eligibility_policy = EligibilityPolicy(
        suppression_port=suppression,
        legal_basis_port=legal_basis,
    )
    cadence_policy = CadencePolicy()
    command = EnrollInCadenceCommand(
        uow=uow,
        clock=clock,
        eligibility_policy=eligibility_policy,
        cadence_policy=cadence_policy,
    )

    result = command.execute(str(lead.id), "cold_outreach_b2b@v1.0.0")
    assert result is True

    # Lead deve estar IN_CADENCE
    saved_lead = leads.get(lead.id)
    assert saved_lead is not None
    assert saved_lead.status == LeadStatus.IN_CADENCE

    # Matrícula criada com agendamento correto (step 1 delay = 0)
    assert len(enrollments.storage) == 1
    enrollment = next(iter(enrollments.storage.values()))
    assert enrollment.lead_id == lead.id
    assert enrollment.cadence_name == "cold_outreach_b2b@v1.0.0"
    assert enrollment.current_step == 0  # factory define 0, próximo passo será 1
    assert enrollment.status == EnrollmentStatus.ACTIVE
    # next_run_at deve ser now + delay (delay do step 1 = 0)
    assert enrollment.next_run_at == clock.now()
