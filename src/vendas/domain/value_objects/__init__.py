"""Value Objects para o domínio de vendas B2B."""

from .cnpj import Cnpj
from .email import Email
from .money import Money
from .phone import Phone, UnidentifiedContactError

__all__ = ["Cnpj", "Email", "Money", "Phone", "UnidentifiedContactError"]
