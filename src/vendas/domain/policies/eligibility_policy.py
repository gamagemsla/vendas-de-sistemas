"""EligibilityPolicy - Valida se o lead possui celular válido, base legal e não está na supressão."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from uuid import UUID

from vendas.domain.value_objects import Phone


class SuppressionListPort(Protocol):
    """Port para verificar se um telefone/email está na lista de supressão."""

    def is_suppressed(self, phone: Phone, email: str | None = None) -> bool:
        """Verifica se o contato está na lista de supressão (opt-out global, DNC, etc.)."""
        ...


class LegalBasisPort(Protocol):
    """Port para verificar se há base legal registrada para o lead."""

    def has_legal_basis(self, lead_id: UUID, phone: Phone) -> bool:
        """Verifica se existe base legal (consentimento, legítimo interesse, etc.) registrada."""
        ...


class EligibilityReason(str, Enum):
    """Motivos de inelegibilidade."""

    INVALID_PHONE = "invalid_phone"
    NO_LEGAL_BASIS = "no_legal_basis"
    SUPPRESSED = "suppressed"
    ALREADY_OPTED_OUT = "already_opted_out"
    INVALID_EMAIL = "invalid_email"
    NOT_ICP_MATCH = "not_icp_match"


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    """Resultado da verificação de elegibilidade."""

    is_eligible: bool
    reasons: list[EligibilityReason]
    details: dict[str, str]


class EligibilityPolicy:
    """
    Política para validar se um lead está elegível para prospecção.

    Verifica:
    1. Celular válido (formato E.164, DDD válido, é celular)
    2. Base legal registrada (consentimento, legítimo interesse)
    3. Não está na lista de supressão (opt-out global, DNC, etc.)
    4. E-mail válido (se fornecido)
    5. Perfil de cliente ideal (ICP) - opcional, se critérios configurados
    """

    def __init__(
        self,
        suppression_port: SuppressionListPort,
        legal_basis_port: LegalBasisPort,
        require_email: bool = False,
        allowed_company_sizes: list[str] | None = None,
        allowed_industries: list[str] | None = None,
        min_qualification_score: int | None = None,
    ):
        self._suppression_port = suppression_port
        self._legal_basis_port = legal_basis_port
        self._require_email = require_email
        self._allowed_company_sizes = allowed_company_sizes
        self._allowed_industries = allowed_industries
        self._min_qualification_score = min_qualification_score

    def check(
        self,
        lead_id: UUID,
        phone: Phone,
        email: str | None = None,
        status: str | None = None,
        company_size: str | None = None,
        industry: str | None = None,
        qualification_score: int | None = None,
    ) -> EligibilityResult:
        """
        Verifica a elegibilidade do lead.

        Args:
            lead_id: ID do lead
            phone: Telefone do lead (Value Object Phone)
            email: E-mail do lead (opcional)
            status: Status atual do lead (opcional)
            company_size: Porte da empresa (opcional, para ICP)
            industry: Setor da empresa (opcional, para ICP)
            qualification_score: Score de qualificação (opcional, para ICP)

        Returns:
            EligibilityResult com o resultado da verificação
        """
        reasons = []
        details = {}

        # 1. Valida telefone (já validado pelo VO Phone, mas verifica se não é None)
        if phone is None:
            reasons.append(EligibilityReason.INVALID_PHONE)
            details["phone"] = "Telefone é obrigatório"
        else:
            details["phone"] = phone.value

        # 2. Valida e-mail se fornecido ou obrigatório
        if self._require_email or email is not None:
            if email is None or not email.strip():
                reasons.append(EligibilityReason.INVALID_EMAIL)
                details["email"] = "E-mail é obrigatório"
            else:
                # Validação básica de formato
                if "@" not in email or "." not in email.split("@")[-1]:
                    reasons.append(EligibilityReason.INVALID_EMAIL)
                    details["email"] = f"E-mail inválido: {email}"
                else:
                    details["email"] = email

        # 3. Verifica base legal
        if not self._legal_basis_port.has_legal_basis(lead_id, phone):
            reasons.append(EligibilityReason.NO_LEGAL_BASIS)
            details["legal_basis"] = "Base legal não encontrada"
        else:
            details["legal_basis"] = "OK"

        # 4. Verifica lista de supressão
        if self._suppression_port.is_suppressed(phone, email):
            reasons.append(EligibilityReason.SUPPRESSED)
            details["suppression"] = "Contato na lista de supressão"
        else:
            details["suppression"] = "OK"

        # 5. Verifica se já fez opt-out (status terminal)
        if status == "OPTED_OUT":
            reasons.append(EligibilityReason.ALREADY_OPTED_OUT)
            details["status"] = "Lead já fez opt-out"
        else:
            details["status"] = status or "UNKNOWN"

        # 6. Verifica ICP (perfil de cliente ideal) se critérios configurados
        icp_configured = (
            self._allowed_company_sizes is not None
            or self._allowed_industries is not None
            or self._min_qualification_score is not None
        )
        if icp_configured:
            icp_ok = True
            icp_details = []
            if self._allowed_company_sizes is not None and (
                company_size is None or company_size not in self._allowed_company_sizes
            ):
                icp_ok = False
                icp_details.append(
                    f"company_size: {company_size} not in allowed {self._allowed_company_sizes}"
                )
            if self._allowed_industries is not None and (
                industry is None or industry not in self._allowed_industries
            ):
                icp_ok = False
                icp_details.append(
                    f"industry: {industry} not in allowed {self._allowed_industries}"
                )
            if self._min_qualification_score is not None and (
                qualification_score is None or qualification_score < self._min_qualification_score
            ):
                icp_ok = False
                icp_details.append(
                    f"qualification_score: {qualification_score} below min {self._min_qualification_score}"
                )
            if not icp_ok:
                reasons.append(EligibilityReason.NOT_ICP_MATCH)
                details["icp"] = "; ".join(icp_details)
            else:
                details["icp"] = "OK"
        else:
            details["icp"] = "NOT_CONFIGURED"

        is_eligible = len(reasons) == 0

        return EligibilityResult(
            is_eligible=is_eligible,
            reasons=reasons,
            details=details,
        )

    def is_eligible(
        self,
        lead_id: UUID,
        phone: Phone,
        email: str | None = None,
        status: str | None = None,
        company_size: str | None = None,
        industry: str | None = None,
        qualification_score: int | None = None,
    ) -> bool:
        """Verificação simples se o lead é elegível."""
        return self.check(
            lead_id,
            phone,
            email,
            status,
            company_size=company_size,
            industry=industry,
            qualification_score=qualification_score,
        ).is_eligible

    @staticmethod
    def quick_check(lead: object) -> bool:
        """Método estático para verificação rápida de elegibilidade.

        Verifica se o lead tem telefone válido e não está em status OPTED_OUT.
        Para verificação completa, use a instância da política com os ports necessários.
        """
        phone = getattr(lead, "phone", None)
        status = getattr(lead, "status", None)
        return phone is not None and status != "OPTED_OUT"
