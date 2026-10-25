"""Testes unitários para as Políticas Puras do Domínio."""

from datetime import datetime, time, timedelta
from uuid import uuid4

from vendas.domain.policies import (
    CadencePolicy,
    CadenceStep,
    Channel,
    EligibilityPolicy,
    EligibilityReason,
    HandoffPolicy,
    HandoffResult,
    HandoffTrigger,
    OptOutIntent,
    OptOutPolicy,
    SendWindowPolicy,
    SendWindowResult,
)
from vendas.domain.value_objects import Phone

from ..fakes.fakes import FakeClock


class TestSendWindowPolicy:
    """Testes para SendWindowPolicy."""

    def setup_method(self):
        self.clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0))
        self.policy = SendWindowPolicy(clock=self.clock)

    def test_allowed_during_business_hours_weekday(self):
        result = self.policy.check("11")
        assert result.allowed is True
        assert result.reason == "Dentro da janela de envio"
        assert result.is_weekend is False
        assert result.is_holiday is False

    def test_allowed_different_ddd_same_timezone(self):
        for ddd in ["11", "21", "31", "41", "51", "61", "71", "81", "85"]:
            result = self.policy.check(ddd)
            assert result.allowed is True, f"Falhou para DDD {ddd}"

    def test_allowed_different_timezones(self):
        clock_acre = FakeClock(datetime(2024, 1, 15, 8, 0, 0))
        policy_acre = SendWindowPolicy(clock=clock_acre)
        result = policy_acre.check("68")
        assert result.allowed is True

    def test_blocked_weekend_saturday(self):
        clock_sat = FakeClock(datetime(2024, 1, 13, 10, 0, 0))
        policy_sat = SendWindowPolicy(clock=clock_sat)
        result = policy_sat.check("11")
        assert result.allowed is False
        assert result.reason == "Fim de semana"
        assert result.is_weekend is True

    def test_blocked_weekend_sunday(self):
        clock_sun = FakeClock(datetime(2024, 1, 14, 10, 0, 0))
        policy_sun = SendWindowPolicy(clock=clock_sun)
        result = policy_sun.check("11")
        assert result.allowed is False
        assert result.is_weekend is True

    def test_blocked_before_business_hours(self):
        clock_early = FakeClock(datetime(2024, 1, 15, 7, 59, 0))
        policy_early = SendWindowPolicy(clock=clock_early)
        result = policy_early.check("11")
        assert result.allowed is False
        assert "Fora do horário comercial" in result.reason

    def test_blocked_after_business_hours(self):
        clock_late = FakeClock(datetime(2024, 1, 15, 18, 0, 0))
        policy_late = SendWindowPolicy(clock=clock_late)
        result = policy_late.check("11")
        assert result.allowed is False
        assert "Fora do horário comercial" in result.reason

    def test_allowed_at_exact_start_time(self):
        clock_start = FakeClock(datetime(2024, 1, 15, 8, 0, 0))
        policy_start = SendWindowPolicy(clock=clock_start)
        result = policy_start.check("11")
        assert result.allowed is True

    def test_blocked_at_exact_end_time(self):
        clock_end = FakeClock(datetime(2024, 1, 15, 18, 0, 0))
        policy_end = SendWindowPolicy(clock=clock_end)
        result = policy_end.check("11")
        assert result.allowed is False

    def test_blocked_national_holiday(self):
        clock_xmas = FakeClock(datetime(2024, 12, 25, 10, 0, 0))
        policy_xmas = SendWindowPolicy(clock=clock_xmas)
        result = policy_xmas.check("11")
        assert result.allowed is False
        assert result.reason == "Feriado nacional"
        assert result.is_holiday is True

    def test_blocked_tiradentes_holiday(self):
        clock_tiradentes = FakeClock(datetime(2024, 4, 21, 10, 0, 0))
        policy_tiradentes = SendWindowPolicy(clock=clock_tiradentes)
        result = policy_tiradentes.check("11")
        assert result.allowed is False
        assert result.is_holiday is True

    def test_custom_business_hours(self):
        policy_custom = SendWindowPolicy(
            clock=self.clock,
            business_start=time(9, 0),
            business_end=time(17, 0),
        )
        result = policy_custom.check("11")
        assert result.allowed is True
        assert result.business_start == time(9, 0)
        assert result.business_end == time(17, 0)

    def test_custom_holidays(self):
        custom_holidays = {(15, 1)}
        policy_custom = SendWindowPolicy(
            clock=self.clock,
            holidays=custom_holidays,
        )
        result = policy_custom.check("11")
        assert result.allowed is False
        assert result.is_holiday is True

    def test_is_allowed_simple_check(self):
        assert self.policy.is_allowed("11") is True
        clock_sat = FakeClock(datetime(2024, 1, 13, 10, 0, 0))
        policy_sat = SendWindowPolicy(clock=clock_sat)
        assert policy_sat.is_allowed("11") is False

    def test_result_contains_all_fields(self):
        result = self.policy.check("11")
        assert isinstance(result, SendWindowResult)
        assert hasattr(result, "allowed")
        assert hasattr(result, "reason")
        assert hasattr(result, "current_time")
        assert hasattr(result, "business_start")
        assert hasattr(result, "business_end")
        assert hasattr(result, "timezone")
        assert hasattr(result, "is_weekend")
        assert hasattr(result, "is_holiday")


class TestCadencePolicy:
    """Testes para CadencePolicy."""

    def setup_method(self):
        self.policy = CadencePolicy()

    def test_get_first_step(self):
        step = self.policy.get_next_step(0)
        assert step is not None
        assert step.step_number == 1
        assert step.channel == Channel.WHATSAPP
        assert step.template_name == "initial_contact"
        assert step.delay == timedelta(minutes=0)
        assert step.is_fallback is False

    def test_get_sequential_steps(self):
        for i in range(1, 8):
            step = self.policy.get_next_step(i - 1)
            assert step is not None
            assert step.step_number == i

    def test_returns_none_after_max_steps(self):
        step = self.policy.get_next_step(7)
        assert step is None

    def test_accelerates_to_fallback_on_whatsapp_failure(self):
        step = self.policy.get_next_step(2, last_channel=Channel.WHATSAPP, last_result="failed")
        assert step is not None
        assert step.channel == Channel.EMAIL
        assert step.is_fallback is True

    def test_does_not_accelerate_on_success(self):
        step = self.policy.get_next_step(2, last_channel=Channel.WHATSAPP, last_result="sent")
        assert step is not None
        assert step.step_number == 3
        assert step.channel == Channel.WHATSAPP

    def test_does_not_accelerate_on_reply(self):
        step = self.policy.get_next_step(2, last_channel=Channel.WHATSAPP, last_result="replied")
        assert step is not None
        assert step.step_number == 3
        assert step.channel == Channel.WHATSAPP

    def test_get_step_by_number(self):
        step = self.policy.get_step_by_number(5)
        assert step is not None
        assert step.step_number == 5
        assert step.channel == Channel.EMAIL
        assert step.is_fallback is True

    def test_get_all_steps(self):
        steps = self.policy.get_all_steps()
        assert len(steps) == 7
        assert steps[0].step_number == 1
        assert steps[-1].step_number == 7

    def test_is_fallback_step(self):
        assert self.policy.is_fallback_step(1) is False
        assert self.policy.is_fallback_step(4) is False
        assert self.policy.is_fallback_step(5) is True
        assert self.policy.is_fallback_step(7) is True

    def test_get_fallback_channel(self):
        assert self.policy.get_fallback_channel() == Channel.EMAIL

    def test_should_use_fallback_after_consecutive_failures(self):
        assert self.policy.should_use_fallback(2, 2) is True
        assert self.policy.should_use_fallback(2, 1) is False
        assert self.policy.should_use_fallback(5, 2) is False

    def test_get_delay_until_next(self):
        delay = self.policy.get_delay_until_next(1)
        assert delay == timedelta(days=2)

        delay = self.policy.get_delay_until_next(4)
        assert delay == timedelta(days=2)

    def test_is_cadence_complete(self):
        assert self.policy.is_cadence_complete(0) is False
        assert self.policy.is_cadence_complete(6) is False
        assert self.policy.is_cadence_complete(7) is True
        assert self.policy.is_cadence_complete(10) is True

    def test_custom_steps(self):
        custom_steps = [
            CadenceStep(1, Channel.WHATSAPP, "custom_1", timedelta(hours=1)),
            CadenceStep(2, Channel.EMAIL, "custom_2", timedelta(days=1), is_fallback=True),
        ]
        policy = CadencePolicy(steps=custom_steps, max_steps=2)
        assert policy.get_next_step(0).template_name == "custom_1"
        assert policy.get_next_step(1).template_name == "custom_2"
        assert policy.get_next_step(2) is None


class TestOptOutPolicy:
    """Testes para OptOutPolicy."""

    def setup_method(self):
        self.policy = OptOutPolicy()

    def test_detect_explicit_stop_sair(self):
        result = self.policy.detect("Quero sair")
        assert result.is_opt_out is True
        assert result.intent == OptOutIntent.EXPLICIT_STOP
        assert result.confidence == 0.95

    def test_detect_explicit_stop_parar(self):
        result = self.policy.detect("Por favor, pare de me mandar mensagens")
        assert result.is_opt_out is True
        assert result.intent == OptOutIntent.EXPLICIT_STOP

    def test_detect_explicit_stop_cancelar(self):
        result = self.policy.detect("Cancelar minha inscrição")
        assert result.is_opt_out is True
        assert result.intent == OptOutIntent.EXPLICIT_STOP

    def test_detect_no_interest(self):
        result = self.policy.detect("Não tenho interesse no produto")
        assert result.is_opt_out is True
        assert result.intent == OptOutIntent.NO_INTEREST
        assert result.confidence == 0.9

    def test_detect_no_interest_variations(self):
        test_cases = [
            "Sem interesse",
            "Não me interessa",
            "Não quero saber",
            "Não preciso",
            "Já tenho",
            "Não vou comprar",
        ]
        for text in test_cases:
            result = self.policy.detect(text)
            assert result.is_opt_out is True, f"Falhou para: {text}"
            assert result.intent == OptOutIntent.NO_INTEREST

    def test_detect_unsubscribe(self):
        test_cases = [
            "Descadastrar meu número",
            "Remover da lista",
            "Não quero receber mais",
            "Parar de receber",
            "Cancelar cadastro",
        ]
        for text in test_cases:
            result = self.policy.detect(text)
            assert result.is_opt_out is True, f"Falhou para: {text}"
            assert result.intent == OptOutIntent.UNSUBSCRIBE

    def test_detect_generic_opt_out(self):
        result = self.policy.detect("Não quero")
        assert result.is_opt_out is True
        assert result.intent == OptOutIntent.GENERIC_OPT_OUT
        assert result.confidence == 0.7

    def test_false_positive_nao_quero_parar(self):
        result = self.policy.detect("Não quero parar de receber suas mensagens")
        assert result.is_opt_out is False
        assert result.matched_pattern == "false_positive"

    def test_false_positive_nao_quero_sair(self):
        result = self.policy.detect("Não quero sair da lista")
        assert result.is_opt_out is False

    def test_false_positive_quero_continuar(self):
        result = self.policy.detect("Quero continuar recebendo")
        assert result.is_opt_out is False

    def test_false_positive_nao_me_tire(self):
        result = self.policy.detect("Não me tire da lista por favor")
        assert result.is_opt_out is False

    def test_false_positive_mantenha_me(self):
        result = self.policy.detect("Mantenha meu contato")
        assert result.is_opt_out is False

    def test_false_positive_continua_mandando(self):
        result = self.policy.detect("Continua me mandando as ofertas")
        assert result.is_opt_out is False

    def test_empty_text(self):
        result = self.policy.detect("")
        assert result.is_opt_out is False
        assert result.confidence == 0.0

    def test_none_text(self):
        result = self.policy.detect(None)
        assert result.is_opt_out is False

    def test_whitespace_only(self):
        result = self.policy.detect("   ")
        assert result.is_opt_out is False

    def test_case_insensitive(self):
        result = self.policy.detect("SAIR")
        assert result.is_opt_out is True
        result = self.policy.detect("Sair")
        assert result.is_opt_out is True
        result = self.policy.detect("sair")
        assert result.is_opt_out is True

    def test_is_opt_out_simple_check(self):
        assert self.policy.is_opt_out("Quero sair") is True
        assert self.policy.is_opt_out("Não quero parar") is False

    def test_result_contains_original_text(self):
        text = "Quero sair da lista"
        result = self.policy.detect(text)
        assert result.original_text == text

    def test_result_contains_matched_pattern(self):
        result = self.policy.detect("Quero sair")
        assert result.matched_pattern is not None
        assert "sair" in result.matched_pattern.lower()


class TestHandoffPolicy:
    """Testes para HandoffPolicy."""

    def setup_method(self):
        self.policy = HandoffPolicy()

    def test_detect_request_human(self):
        test_cases = [
            "Quero falar com um humano",
            "Falar com atendente",
            "Transferir para pessoa",
            "Atendente humano por favor",
            "Não é um robô",
            "É um bot ruim",
        ]
        for text in test_cases:
            result = self.policy.check(text)
            assert result.should_handoff is True, f"Falhou para: {text}"
            assert HandoffTrigger.REQUEST_HUMAN in result.triggers

    def test_detect_mentions_price(self):
        test_cases = [
            "Qual o preço?",
            "Quanto custa?",
            "Qual o valor do produto?",
            "Me mandem o orçamento",
            "Tabela de preços",
            "Tem desconto?",
            "Como é o pagamento?",
        ]
        for text in test_cases:
            result = self.policy.check(text)
            assert result.should_handoff is True, f"Falhou para: {text}"
            assert HandoffTrigger.MENTIONS_PRICE in result.triggers

    def test_detect_mentions_contract(self):
        test_cases = [
            "Quero ver o contrato",
            "Mandem a proposta",
            "Vamos fechar negócio",
            "Termos e condições",
            "Cláusula de rescisão",
            "Assinar o contrato",
        ]
        for text in test_cases:
            result = self.policy.check(text)
            assert result.should_handoff is True, f"Falhou para: {text}"
            assert HandoffTrigger.MENTIONS_CONTRACT in result.triggers

    def test_detect_hostile_tone(self):
        test_cases = [
            "Você é um idiota",
            "Que merda de bot",
            "Isso é um lixo",
            "Vai tomar no cu",
            "Isso é ridículo",
            "Vou processar vocês",
            "Quero meus dados LGPD",
        ]
        for text in test_cases:
            result = self.policy.check(text)
            assert result.should_handoff is True, f"Falhou para: {text}"
            assert HandoffTrigger.HOSTILE_TONE in result.triggers

    def test_detect_technical_question(self):
        test_cases = [
            "Como funciona a API?",
            "Vocês têm webhook?",
            "Qual a arquitetura?",
            "Como é o deploy?",
            "Vocês têm SLA?",
            "Como é a migração?",
        ]
        for text in test_cases:
            result = self.policy.check(text)
            assert result.should_handoff is True, f"Falhou para: {text}"
            assert HandoffTrigger.TECHNICAL_QUESTION in result.triggers

    def test_detect_legal_compliance(self):
        test_cases = [
            "Meu advogado vai analisar o contrato",
            "Qual o foro do contrato?",
            "Cláusula de multa",
            "Responsabilidade civil",
            "Lei de proteção de dados",
        ]
        for text in test_cases:
            result = self.policy.check(text)
            assert result.should_handoff is True, f"Falhou para: {text}"
            assert HandoffTrigger.LEGAL_COMPLIANCE in result.triggers

    def test_detect_repeated_questions(self):
        # Use neutral text that doesn't trigger other handoff patterns
        neutral_text = "Olá, tudo bem?"

        result = self.policy.check(neutral_text, repeated_questions_count=3)
        assert result.should_handoff is True
        assert HandoffTrigger.REPEATED_QUESTIONS in result.triggers

        result = self.policy.check(neutral_text, repeated_questions_count=2)
        assert result.should_handoff is False
        assert HandoffTrigger.REPEATED_QUESTIONS not in result.triggers

    def test_multiple_triggers_increase_confidence(self):
        result = self.policy.check("Quero falar com humano e qual o preço?")
        assert result.should_handoff is True
        assert len(result.triggers) >= 2
        assert result.confidence > 0.8

    def test_no_triggers_no_handoff(self):
        result = self.policy.check("Olá, tudo bem?")
        assert result.should_handoff is False
        assert len(result.triggers) == 0
        assert result.confidence == 0.0

    def test_empty_text_no_handoff(self):
        result = self.policy.check("")
        assert result.should_handoff is False

    def test_should_handoff_simple_check(self):
        assert self.policy.should_handoff("Quero falar com humano") is True
        assert self.policy.should_handoff("Olá") is False

    def test_result_contains_all_fields(self):
        result = self.policy.check("Quero falar com humano")
        assert isinstance(result, HandoffResult)
        assert hasattr(result, "should_handoff")
        assert hasattr(result, "triggers")
        assert hasattr(result, "confidence")
        assert hasattr(result, "matched_patterns")
        assert hasattr(result, "original_text")


class TestEligibilityPolicy:
    """Testes para EligibilityPolicy."""

    def setup_method(self):
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

        self.suppression_port = MockSuppressionPort()
        self.legal_basis_port = MockLegalBasisPort()
        self.policy = EligibilityPolicy(
            suppression_port=self.suppression_port,
            legal_basis_port=self.legal_basis_port,
        )
        self.lead_id = uuid4()
        self.valid_phone = Phone("+5511988887777")

    def test_eligible_valid_lead(self):
        result = self.policy.check(self.lead_id, self.valid_phone, "test@email.com")
        assert result.is_eligible is True
        assert len(result.reasons) == 0

    def test_ineligible_invalid_phone(self):
        result = self.policy.check(self.lead_id, None, "test@email.com")
        assert result.is_eligible is False
        assert EligibilityReason.INVALID_PHONE in result.reasons

    def test_ineligible_no_legal_basis(self):
        self.legal_basis_port._has_basis = False
        result = self.policy.check(self.lead_id, self.valid_phone, "test@email.com")
        assert result.is_eligible is False
        assert EligibilityReason.NO_LEGAL_BASIS in result.reasons

    def test_ineligible_suppressed(self):
        self.suppression_port._suppressed = True
        result = self.policy.check(self.lead_id, self.valid_phone, "test@email.com")
        assert result.is_eligible is False
        assert EligibilityReason.SUPPRESSED in result.reasons

    def test_ineligible_already_opted_out(self):
        result = self.policy.check(
            self.lead_id, self.valid_phone, "test@email.com", status="OPTED_OUT"
        )
        assert result.is_eligible is False
        assert EligibilityReason.ALREADY_OPTED_OUT in result.reasons

    def test_ineligible_invalid_email_when_required(self):
        policy = EligibilityPolicy(
            suppression_port=self.suppression_port,
            legal_basis_port=self.legal_basis_port,
            require_email=True,
        )
        result = policy.check(self.lead_id, self.valid_phone, "email_invalido")
        assert result.is_eligible is False
        assert EligibilityReason.INVALID_EMAIL in result.reasons

    def test_email_optional_when_not_required(self):
        result = self.policy.check(self.lead_id, self.valid_phone, email=None)
        assert result.is_eligible is True

    def test_multiple_reasons(self):
        self.legal_basis_port._has_basis = False
        self.suppression_port._suppressed = True
        result = self.policy.check(
            self.lead_id, self.valid_phone, "test@email.com", status="OPTED_OUT"
        )
        assert result.is_eligible is False
        assert len(result.reasons) == 3
        assert EligibilityReason.NO_LEGAL_BASIS in result.reasons
        assert EligibilityReason.SUPPRESSED in result.reasons
        assert EligibilityReason.ALREADY_OPTED_OUT in result.reasons

    def test_is_eligible_simple_check(self):
        assert self.policy.is_eligible(self.lead_id, self.valid_phone) is True
        self.legal_basis_port._has_basis = False
        assert self.policy.is_eligible(self.lead_id, self.valid_phone) is False

    def test_result_contains_details(self):
        result = self.policy.check(self.lead_id, self.valid_phone, "test@email.com")
        assert "phone" in result.details
        assert "email" in result.details
        assert "legal_basis" in result.details
        assert "suppression" in result.details
        assert "status" in result.details


class TestPoliciesIntegration:
    """Testes de integração entre políticas."""

    def test_send_window_and_cadence_work_together(self):
        clock = FakeClock(datetime(2024, 1, 15, 10, 0, 0))
        send_policy = SendWindowPolicy(clock=clock)
        cadence_policy = CadencePolicy()

        window_result = send_policy.check("11")
        assert window_result.allowed is True

        step = cadence_policy.get_next_step(0)
        assert step is not None
        assert step.channel == Channel.WHATSAPP

    def test_opt_out_and_handoff_priority(self):
        opt_out_policy = OptOutPolicy()
        handoff_policy = HandoffPolicy()

        text = "Não quero mais saber de preço, quero sair"
        opt_out_result = opt_out_policy.detect(text)
        handoff_result = handoff_policy.check(text)

        assert opt_out_result.is_opt_out is True
        assert handoff_result.should_handoff is True

    def test_eligibility_before_cadence(self):
        class MockSuppressionPort:
            def is_suppressed(self, phone, email=None):
                return False

        class MockLegalBasisPort:
            def has_legal_basis(self, lead_id, phone):
                return True

        eligibility_policy = EligibilityPolicy(
            suppression_port=MockSuppressionPort(),
            legal_basis_port=MockLegalBasisPort(),
        )
        cadence_policy = CadencePolicy()

        lead_id = uuid4()
        phone = Phone("+5511988887777")

        eligible = eligibility_policy.is_eligible(lead_id, phone)
        assert eligible is True

        if eligible:
            step = cadence_policy.get_next_step(0)
            assert step is not None
            assert step.step_number == 1
