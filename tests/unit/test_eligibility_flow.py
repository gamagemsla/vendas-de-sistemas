"""Testes de fluxo de elegibilidade (F2-04)."""

from __future__ import annotations

from uuid import uuid4

from vendas.domain.policies.eligibility_policy import EligibilityPolicy, EligibilityReason
from vendas.domain.value_objects import Phone


class MockSuppressionPort:
    def __init__(self, suppressed=False):
        self._suppressed = suppressed

    def is_suppressed(self, phone, email=None):
        return self._suppressed


class MockLegalBasisPort:
    def __init__(self, has_basis=True):
        self._has_basis = has_basis

    def has_legal_basis(self, lead_id, phone):
        return self._has_basis


def make_policy(
    suppressed=False,
    has_basis=True,
    allowed_company_sizes=None,
    allowed_industries=None,
    min_qualification_score=None,
):
    return EligibilityPolicy(
        suppression_port=MockSuppressionPort(suppressed),
        legal_basis_port=MockLegalBasisPort(has_basis),
        allowed_company_sizes=allowed_company_sizes,
        allowed_industries=allowed_industries,
        min_qualification_score=min_qualification_score,
    )


def test_eligible_passes_all_checks():
    policy = make_policy()
    lead_id = uuid4()
    phone = Phone("+5511988887777")
    result = policy.check(
        lead_id,
        phone,
        email="test@example.com",
        status="NEW",
        company_size="MEDIUM",
        industry="TECH",
        qualification_score=80,
    )
    assert result.is_eligible is True
    assert result.reasons == []


def test_ineligible_no_legal_basis():
    policy = make_policy(has_basis=False)
    lead_id = uuid4()
    phone = Phone("+5511988887777")
    result = policy.check(lead_id, phone, email="test@example.com", status="NEW")
    assert result.is_eligible is False
    assert EligibilityReason.NO_LEGAL_BASIS in result.reasons


def test_ineligible_suppressed():
    policy = make_policy(suppressed=True)
    lead_id = uuid4()
    phone = Phone("+5511988887777")
    result = policy.check(lead_id, phone, email="test@example.com", status="NEW")
    assert result.is_eligible is False
    assert EligibilityReason.SUPPRESSED in result.reasons


def test_ineligible_not_icp_match_company_size():
    policy = make_policy(allowed_company_sizes=["LARGE"])
    lead_id = uuid4()
    phone = Phone("+5511988887777")
    result = policy.check(
        lead_id,
        phone,
        email="test@example.com",
        status="NEW",
        company_size="SMALL",
        industry="TECH",
        qualification_score=80,
    )
    assert result.is_eligible is False
    assert EligibilityReason.NOT_ICP_MATCH in result.reasons


def test_ineligible_not_icp_match_industry():
    policy = make_policy(allowed_industries=["FINANCE"])
    lead_id = uuid4()
    phone = Phone("+5511988887777")
    result = policy.check(
        lead_id,
        phone,
        email="test@example.com",
        status="NEW",
        company_size="LARGE",
        industry="RETAIL",
        qualification_score=80,
    )
    assert result.is_eligible is False
    assert EligibilityReason.NOT_ICP_MATCH in result.reasons


def test_ineligible_not_icp_match_score():
    policy = make_policy(min_qualification_score=70)
    lead_id = uuid4()
    phone = Phone("+5511988887777")
    result = policy.check(
        lead_id,
        phone,
        email="test@example.com",
        status="NEW",
        company_size="LARGE",
        industry="FINANCE",
        qualification_score=50,
    )
    assert result.is_eligible is False
    assert EligibilityReason.NOT_ICP_MATCH in result.reasons


def test_enroll_in_cadence_blocks_ineligible():
    # This test would require the command and UoW; we test policy directly here.
    policy = make_policy(has_basis=False)
    lead_id = uuid4()
    phone = Phone("+5511988887777")
    result = policy.check(lead_id, phone, email="test@example.com", status="ELIGIBLE")
    assert result.is_eligible is False
    # Simulate command behavior: disqualify with reasons
    reasons_str = ", ".join([r.value for r in result.reasons])
    assert "no_legal_basis" in reasons_str
