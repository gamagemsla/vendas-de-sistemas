"""Políticas Puras do Domínio - Regras de negócio sem dependências externas."""

from .cadence_policy import CadencePolicy, CadenceStep, Channel
from .eligibility_policy import EligibilityPolicy, EligibilityReason, EligibilityResult
from .handoff_policy import HandoffPolicy, HandoffResult, HandoffTrigger
from .opt_out_policy import OptOutIntent, OptOutPolicy, OptOutResult
from .send_window_policy import SendWindowPolicy, SendWindowResult

__all__ = [
    "CadencePolicy",
    "CadenceStep",
    "Channel",
    "EligibilityPolicy",
    "EligibilityReason",
    "EligibilityResult",
    "HandoffPolicy",
    "HandoffResult",
    "HandoffTrigger",
    "OptOutIntent",
    "OptOutPolicy",
    "OptOutResult",
    "SendWindowPolicy",
    "SendWindowResult",
]
