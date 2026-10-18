"""CadencePolicy - Determina o próximo passo, intervalo e canal de fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import ClassVar, Literal


class Channel(str, Enum):
    """Canais de comunicação disponíveis."""

    WHATSAPP = "whatsapp"
    EMAIL = "email"


@dataclass(frozen=True, slots=True)
class CadenceStep:
    """Representa um passo da cadência."""

    step_number: int
    channel: Channel
    template_name: str
    delay: timedelta
    is_fallback: bool = False


class CadencePolicy:
    """
    Política para determinar o próximo passo da cadência de prospecção.

    Define a sequência de tentativas, intervalos entre elas e canal de fallback.
    """

    # Configuração padrão da cadência
    DEFAULT_STEPS: ClassVar[list[CadenceStep]] = [
        CadenceStep(1, Channel.WHATSAPP, "initial_contact", timedelta(minutes=0)),
        CadenceStep(2, Channel.WHATSAPP, "follow_up_1", timedelta(days=2)),
        CadenceStep(3, Channel.WHATSAPP, "follow_up_2", timedelta(days=3)),
        CadenceStep(4, Channel.WHATSAPP, "follow_up_3", timedelta(days=5)),
        CadenceStep(5, Channel.EMAIL, "fallback_email_1", timedelta(days=2), is_fallback=True),
        CadenceStep(6, Channel.EMAIL, "fallback_email_2", timedelta(days=3), is_fallback=True),
        CadenceStep(7, Channel.EMAIL, "fallback_email_3", timedelta(days=5), is_fallback=True),
    ]

    def __init__(
        self,
        steps: list[CadenceStep] | None = None,
        max_steps: int = 7,
    ):
        self._steps = steps or self.DEFAULT_STEPS
        self._max_steps = max_steps

    def get_next_step(
        self,
        current_step: int,
        last_channel: Channel | None = None,
        last_result: Literal["sent", "failed", "replied"] | None = None,
    ) -> CadenceStep | None:
        """
        Determina o próximo passo da cadência.

        Args:
            current_step: Passo atual (1-indexed, 0 se ainda não iniciou)
            last_channel: Canal usado na última tentativa
            last_result: Resultado da última tentativa

        Returns:
            Próximo CadenceStep ou None se a cadência terminou
        """
        next_step_number = current_step + 1

        if next_step_number > self._max_steps:
            return None

        # Se a última tentativa falhou no WhatsApp e não estamos no fallback,
        # acelera para o fallback de e-mail
        if last_result == "failed" and last_channel == Channel.WHATSAPP:
            # Procura o primeiro passo de fallback (e-mail)
            for step in self._steps:
                if step.is_fallback and step.step_number >= next_step_number:
                    return step

        # Caso normal: retorna o próximo passo sequencial
        for step in self._steps:
            if step.step_number == next_step_number:
                return step

        return None

    def get_step_by_number(self, step_number: int) -> CadenceStep | None:
        """Obtém um passo específico pelo número."""
        for step in self._steps:
            if step.step_number == step_number:
                return step
        return None

    def get_all_steps(self) -> list[CadenceStep]:
        """Retorna todos os passos da cadência."""
        return self._steps.copy()

    def is_fallback_step(self, step_number: int) -> bool:
        """Verifica se um passo é de fallback (e-mail)."""
        step = self.get_step_by_number(step_number)
        return step.is_fallback if step else False

    def get_fallback_channel(self) -> Channel:
        """Retorna o canal de fallback padrão."""
        return Channel.EMAIL

    def should_use_fallback(self, current_step: int, consecutive_failures: int) -> bool:
        """
        Determina se deve usar canal de fallback.

        Args:
            current_step: Passo atual
            consecutive_failures: Falhas consecutivas no canal atual

        Returns:
            True se deve mudar para fallback
        """
        # Após 2 falhas consecutivas no WhatsApp, muda para e-mail
        if consecutive_failures >= 2:
            step = self.get_step_by_number(current_step)
            if step and step.channel == Channel.WHATSAPP and not step.is_fallback:
                return True
        return False

    def get_delay_until_next(self, current_step: int) -> timedelta | None:
        """Retorna o delay até o próximo passo."""
        next_step = self.get_next_step(current_step)
        return next_step.delay if next_step else None

    def is_cadence_complete(self, current_step: int) -> bool:
        """Verifica se a cadência foi completada."""
        return current_step >= self._max_steps
