"""Testes unitários para Value Objects do domínio."""

import pytest

from vendas.domain.value_objects import Cnpj, Email, Money, Phone


class TestPhone:
    """Testes para o Value Object Phone."""

    def test_phone_valid_mobile_sp(self):
        """Valida telefone móvel de SP com nono dígito."""
        phone = Phone("+5511988887777")
        assert phone.value == "+5511988887777"
        assert phone.ddd == "11"
        assert phone.number == "988887777"
        assert phone.is_mobile is True

    def test_phone_valid_mobile_sp_with_formatting(self):
        """Valida telefone móvel de SP com formatação variada."""
        test_cases = [
            "(11) 98888-7777",
            "11 98888-7777",
            "11988887777",
            "+55 11 98888-7777",
            "+55 (11) 98888-7777",
        ]
        for case in test_cases:
            phone = Phone(case)
            assert phone.value == "+5511988887777", f"Falhou para {case}"

    def test_phone_valid_mobile_other_ddd(self):
        """Valida telefones móveis de outros DDDs válidos do Brasil."""
        test_cases = [
            ("+5521988887777", "21"),  # RJ
            ("+5531988887777", "31"),  # MG
            ("+5541988887777", "41"),  # PR
            ("+5551988887777", "51"),  # RS
            ("+5561988887777", "61"),  # DF
            ("+5571988887777", "71"),  # BA
            ("+5581988887777", "81"),  # PE
            ("+5585988887777", "85"),  # CE
        ]
        for phone_str, expected_ddd in test_cases:
            phone = Phone(phone_str)
            assert phone.value == phone_str
            assert phone.ddd == expected_ddd
            assert phone.is_mobile is True

    def test_phone_invalid_landline_rejected(self):
        """Valida que telefones fixos (sem nono dígito) são rejeitados."""
        landlines = [
            "+551133334444",  # SP fixo
            "+552122223333",  # RJ fixo
            "(11) 3333-4444",
            "11 3333-4444",
        ]
        for case in landlines:
            with pytest.raises(ValueError, match="apenas celulares"):
                Phone(case)

    def test_phone_invalid_ddd_rejected(self):
        """Valida que DDDs inválidos são rejeitados."""
        invalid_ddds = [
            "+5500988887777",  # DDD 00 inválido
            "+5510988887777",  # DDD 10 não existe
            "+5590988887777",  # DDD 90 não existe
        ]
        for case in invalid_ddds:
            with pytest.raises(ValueError, match="DDD inválido"):
                Phone(case)

    def test_phone_invalid_ddi_rejected(self):
        """Valida que DDI diferente de 55 (Brasil) é rejeitado."""
        with pytest.raises(ValueError, match="DDI deve ser 55"):
            Phone("+111988887777")  # EUA

    def test_phone_invalid_format_rejected(self):
        """Valida que formatos inválidos são rejeitados."""
        invalid_cases = [
            "abc",
            "+551198888777",  # curto demais
            "+55119888877777",  # longo demais
            "1198888777",  # sem DDI
            "",  # vazio
            None,  # None
        ]
        for case in invalid_cases:
            with pytest.raises(ValueError):
                Phone(case)

    def test_phone_equality(self):
        """Valida igualdade entre Phones."""
        phone1 = Phone("+5511988887777")
        phone2 = Phone("(11) 98888-7777")
        phone3 = Phone("+5521988887777")

        assert phone1 == phone2
        assert phone1 != phone3
        assert hash(phone1) == hash(phone2)

    def test_phone_str_representation(self):
        """Valida representação em string."""
        phone = Phone("+5511988887777")
        assert str(phone) == "+5511988887777"
        assert repr(phone) == "Phone('+5511988887777')"

    def test_phone_immutability(self):
        """Valida que Phone é imutável."""
        phone = Phone("+5511988887777")
        with pytest.raises(AttributeError):
            phone.value = "+5511999999999"


class TestCnpj:
    """Testes para o Value Object Cnpj."""

    def test_cnpj_valid(self):
        """Valida CNPJs válidos com dígitos verificadores corretos."""
        valid_cnpjs = [
            "11.222.333/0001-81",
            "11222333000181",
            "  11.222.333/0001-81  ",
        ]
        for case in valid_cnpjs:
            cnpj = Cnpj(case)
            assert cnpj.value == "11222333000181"
            assert cnpj.formatted == "11.222.333/0001-81"

    def test_cnpj_invalid_check_digits(self):
        """Valida que CNPJs com dígitos verificadores inválidos são rejeitados."""
        invalid_cnpjs = [
            "11.222.333/0001-82",  # dígito errado
            "11222333000182",
            "00.000.000/0000-00",  # todos zeros
        ]
        for case in invalid_cnpjs:
            with pytest.raises(ValueError, match="CNPJ inválido"):
                Cnpj(case)

    def test_cnpj_invalid_format(self):
        """Valida que formatos inválidos são rejeitados."""
        invalid_cases = [
            "abc",
            "1122233300018",  # curto
            "112223330001812",  # longo
            "",
            None,
        ]
        for case in invalid_cases:
            with pytest.raises(ValueError):
                Cnpj(case)

    def test_cnpj_equality(self):
        """Valida igualdade entre CNPJs."""
        cnpj1 = Cnpj("11.222.333/0001-81")
        cnpj2 = Cnpj("11222333000181")

        assert cnpj1 == cnpj2
        assert hash(cnpj1) == hash(cnpj2)

    def test_cnpj_str_representation(self):
        """Valida representação em string."""
        cnpj = Cnpj("11.222.333/0001-81")
        assert str(cnpj) == "11222333000181"
        assert repr(cnpj) == "Cnpj('11222333000181')"

    def test_cnpj_immutability(self):
        """Valida que Cnpj é imutável."""
        cnpj = Cnpj("11.222.333/0001-81")
        with pytest.raises(AttributeError):
            cnpj.value = "11222333000182"


class TestEmail:
    """Testes para o Value Object Email."""

    def test_email_valid(self):
        """Valida e-mails válidos."""
        valid_emails = [
            "usuario@exemplo.com",
            "usuario.nome@exemplo.com.br",
            "usuario+tag@exemplo.org",
            "user@sub.domain.com",
            "USER@EXEMPLO.COM",  # case insensitive no domínio
        ]
        for case in valid_emails:
            email = Email(case)
            assert email.value == case.lower()

    def test_email_invalid_format(self):
        """Valida que formatos inválidos são rejeitados."""
        invalid_cases = [
            "usuario",  # sem @
            "usuario@",  # sem domínio
            "@exemplo.com",  # sem usuário
            "usuario@exemplo",  # sem TLD
            "usuario@.com",  # domínio vazio
            "usuario@exemplo..com",  # duplo ponto
            "usuario @exemplo.com",  # espaço
            "",
            None,
        ]
        for case in invalid_cases:
            with pytest.raises(ValueError, match="E-mail inválido"):
                Email(case)

    def test_email_normalization(self):
        """Valida normalização (lowercase)."""
        email = Email("USUARIO@EXEMPLO.COM")
        assert email.value == "usuario@exemplo.com"

    def test_email_equality(self):
        """Valida igualdade entre Emails."""
        email1 = Email("usuario@exemplo.com")
        email2 = Email("USUARIO@EXEMPLO.COM")
        email3 = Email("outro@exemplo.com")

        assert email1 == email2
        assert email1 != email3
        assert hash(email1) == hash(email2)

    def test_email_str_representation(self):
        """Valida representação em string."""
        email = Email("usuario@exemplo.com")
        assert str(email) == "usuario@exemplo.com"
        assert repr(email) == "Email('usuario@exemplo.com')"

    def test_email_immutability(self):
        """Valida que Email é imutável."""
        email = Email("usuario@exemplo.com")
        with pytest.raises(AttributeError):
            email.value = "outro@exemplo.com"


class TestMoney:
    """Testes para o Value Object Money."""

    def test_money_from_cents(self):
        """Valida criação a partir de centavos."""
        money = Money.from_cents(1000)  # R$ 10,00
        assert money.cents == 1000
        assert money.value == 10.00

    def test_money_from_reais(self):
        """Valida criação a partir de reais (float)."""
        money = Money.from_reais(10.50)
        assert money.cents == 1050
        assert money.value == 10.50

    def test_money_from_string(self):
        """Valida criação a partir de string."""
        test_cases = [
            ("10.00", 1000),
            ("10,00", 1000),
            ("10.50", 1050),
            ("10,50", 1050),
            ("0.01", 1),
            ("1000.00", 100000),
        ]
        for case, expected_cents in test_cases:
            money = Money(case)
            assert money.cents == expected_cents, f"Falhou para {case}"

    def test_money_invalid_input(self):
        """Valida que entradas inválidas são rejeitadas."""
        invalid_cases = [
            "abc",
            "-10.00",  # negativo não permitido
            "",
            None,
        ]
        for case in invalid_cases:
            with pytest.raises(ValueError):
                Money(case)

    def test_money_addition(self):
        """Valida soma de Money."""
        money1 = Money.from_cents(1000)  # R$ 10,00
        money2 = Money.from_cents(500)  # R$ 5,00
        result = money1 + money2
        assert result.cents == 1500
        assert result.value == 15.00

    def test_money_subtraction(self):
        """Valida subtração de Money."""
        money1 = Money.from_cents(1000)  # R$ 10,00
        money2 = Money.from_cents(300)  # R$ 3,00
        result = money1 - money2
        assert result.cents == 700
        assert result.value == 7.00

    def test_money_subtraction_negative_raises(self):
        """Valida que subtração resultando em negativo levanta erro."""
        money1 = Money.from_cents(500)  # R$ 5,00
        money2 = Money.from_cents(1000)  # R$ 10,00
        with pytest.raises(ValueError, match="não pode ser negativo"):
            money1 - money2

    def test_money_multiplication(self):
        """Valida multiplicação por inteiro."""
        money = Money.from_cents(1000)  # R$ 10,00
        result = money * 3
        assert result.cents == 3000
        assert result.value == 30.00

    def test_money_division(self):
        """Valida divisão por inteiro."""
        money = Money.from_cents(1000)  # R$ 10,00
        result = money / 2
        assert result.cents == 500
        assert result.value == 5.00

    def test_money_comparison(self):
        """Valida comparação entre Money."""
        money1 = Money.from_cents(1000)
        money2 = Money.from_cents(500)
        money3 = Money.from_cents(1000)

        assert money1 > money2
        assert money2 < money1
        assert money1 == money3
        assert money1 >= money3
        assert money2 <= money1

    def test_money_zero(self):
        """Valida Money zero."""
        money = Money.from_cents(0)
        assert money.cents == 0
        assert money.value == 0.0
        assert bool(money) is False

    def test_money_str_representation(self):
        """Valida representação em string."""
        money = Money.from_cents(1050)
        assert str(money) == "10.50"
        assert repr(money) == "Money(1050)"

    def test_money_formatted_brl(self):
        """Valida formatação BRL."""
        money = Money.from_cents(1050)
        assert money.format_brl() == "R$ 10,50"

        money2 = Money.from_cents(1000)
        assert money2.format_brl() == "R$ 10,00"

        money3 = Money.from_cents(1234567)
        assert money3.format_brl() == "R$ 12.345,67"

    def test_money_immutability(self):
        """Valida que Money é imutável."""
        money = Money.from_cents(1000)
        with pytest.raises(AttributeError):
            money.cents = 2000
