"""Value Object Phone - Telefone brasileiro normalizado para E.164."""

import re
from dataclasses import dataclass

# DDDs válidos do Brasil (códigos de área)
VALID_DDDS = {
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",  # SP
    "21",
    "22",
    "24",  # RJ
    "27",
    "28",  # ES
    "31",
    "32",
    "33",
    "34",
    "35",
    "37",
    "38",  # MG
    "41",
    "42",
    "43",
    "44",
    "45",
    "46",  # PR
    "47",
    "48",
    "49",  # SC
    "51",
    "53",
    "54",
    "55",  # RS
    "61",  # DF
    "62",
    "64",  # GO
    "63",  # TO
    "65",
    "66",  # MT
    "67",  # MS
    "68",  # AC
    "69",  # RO
    "71",
    "73",
    "74",
    "75",
    "77",  # BA
    "79",  # SE
    "81",
    "87",  # PE
    "82",  # AL
    "83",  # PB
    "84",  # RN
    "85",
    "88",  # CE
    "86",
    "89",  # PI
    "91",
    "93",
    "94",  # PA
    "92",
    "97",  # AM
    "95",  # RR
    "96",  # AP
    "98",
    "99",  # MA
}


@dataclass(frozen=True, slots=True)
class Phone:
    """
    Value Object para telefone brasileiro.

    Normaliza para formato E.164 (+55DDD9XXXXXXXX).
    Aceita apenas celulares (com nono dígito = 9).
    """

    value: str

    def __post_init__(self) -> None:
        normalized = self._normalize(self.value)
        self._validate(normalized)
        object.__setattr__(self, "value", normalized)

    @staticmethod
    def _normalize(raw: str | None) -> str:
        """Normaliza o telefone para formato E.164."""
        if raw is None:
            raise ValueError("Telefone não pode ser None")

        # Suporta JID do WhatsApp (ex: "5511999999999@s.whatsapp.net")
        # Extrai a parte antes do '@' se presente
        candidate = raw.split("@")[0] if "@" in raw else raw

        # Remove tudo que não é dígito
        digits = re.sub(r"\D", "", candidate)

        # Se começa com +, remove o +
        if candidate.strip().startswith("+"):
            # Já tem DDI explícito, valida se é 55
            if not digits.startswith("55"):
                raise ValueError("DDI deve ser 55")
        else:
            # Sem DDI explícito, assume Brasil
            digits = digits.removeprefix("0")  # Remove 0 inicial de DDD
            # Evita duplicar o DDI se já estiver presente (ex: "5511999999999")
            if not digits.startswith("55"):
                digits = "55" + digits

        return f"+{digits}"

    @staticmethod
    def _validate(normalized: str) -> None:
        """Valida o telefone normalizado."""
        # Verifica DDI primeiro
        if not normalized.startswith("+55"):
            raise ValueError("DDI deve ser 55")

        # Verifica se é celular (nono dígito = 9) - antes do regex para dar erro mais específico
        if len(normalized) >= 6:
            ninth_digit = normalized[5]
            if ninth_digit != "9":
                raise ValueError("apenas celulares")

        # Formato esperado: +55DDD9XXXXXXXX (13 dígitos após +)
        if not re.match(r"^\+55\d{11}$", normalized):
            raise ValueError("Formato de telefone inválido")

        ddd = normalized[3:5]
        if ddd not in VALID_DDDS:
            raise ValueError("DDD inválido")

    @property
    def ddd(self) -> str:
        """Retorna o DDD (código de área)."""
        return self.value[3:5]

    @property
    def number(self) -> str:
        """Retorna o número sem DDD e sem DDI (9 dígitos)."""
        return self.value[5:]

    @property
    def is_mobile(self) -> bool:
        """Retorna True se for celular (sempre True para este VO)."""
        return True

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Phone('{self.value}')"
