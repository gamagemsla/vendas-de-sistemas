"""SendWindowPolicy - Valida se o momento atual está dentro do horário comercial."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from vendas.domain.ports import Clock

# Mapeamento de DDD para timezone (padrão America/Sao_Paulo)
DDD_TO_TIMEZONE: dict[str, str] = {
    "11": "America/Sao_Paulo",
    "12": "America/Sao_Paulo",
    "13": "America/Sao_Paulo",
    "14": "America/Sao_Paulo",
    "15": "America/Sao_Paulo",
    "16": "America/Sao_Paulo",
    "17": "America/Sao_Paulo",
    "18": "America/Sao_Paulo",
    "19": "America/Sao_Paulo",
    "21": "America/Sao_Paulo",
    "22": "America/Sao_Paulo",
    "24": "America/Sao_Paulo",
    "27": "America/Sao_Paulo",
    "28": "America/Sao_Paulo",
    "31": "America/Sao_Paulo",
    "32": "America/Sao_Paulo",
    "33": "America/Sao_Paulo",
    "34": "America/Sao_Paulo",
    "35": "America/Sao_Paulo",
    "37": "America/Sao_Paulo",
    "38": "America/Sao_Paulo",
    "41": "America/Sao_Paulo",
    "42": "America/Sao_Paulo",
    "43": "America/Sao_Paulo",
    "44": "America/Sao_Paulo",
    "45": "America/Sao_Paulo",
    "46": "America/Sao_Paulo",
    "47": "America/Sao_Paulo",
    "48": "America/Sao_Paulo",
    "49": "America/Sao_Paulo",
    "51": "America/Sao_Paulo",
    "53": "America/Sao_Paulo",
    "54": "America/Sao_Paulo",
    "55": "America/Sao_Paulo",
    "61": "America/Sao_Paulo",
    "62": "America/Sao_Paulo",
    "64": "America/Sao_Paulo",
    "63": "America/Sao_Paulo",
    "65": "America/Sao_Paulo",
    "66": "America/Sao_Paulo",
    "67": "America/Sao_Paulo",
    "68": "America/Rio_Branco",
    "69": "America/Porto_Velho",
    "71": "America/Bahia",
    "73": "America/Bahia",
    "74": "America/Bahia",
    "75": "America/Bahia",
    "77": "America/Bahia",
    "79": "America/Maceio",
    "81": "America/Recife",
    "87": "America/Recife",
    "82": "America/Maceio",
    "83": "America/Fortaleza",
    "84": "America/Fortaleza",
    "85": "America/Fortaleza",
    "88": "America/Fortaleza",
    "86": "America/Fortaleza",
    "89": "America/Fortaleza",
    "91": "America/Belem",
    "93": "America/Belem",
    "94": "America/Belem",
    "92": "America/Manaus",
    "97": "America/Manaus",
    "95": "America/Boa_Vista",
    "96": "America/Belem",
    "98": "America/Fortaleza",
    "99": "America/Fortaleza",
}

DEFAULT_TIMEZONE = "America/Sao_Paulo"

NATIONAL_HOLIDAYS: set[tuple[int, int]] = {
    (1, 1),
    (21, 4),
    (1, 5),
    (7, 9),
    (12, 10),
    (2, 11),
    (15, 11),
    (25, 12),
}

DEFAULT_BUSINESS_START = time(8, 0)
DEFAULT_BUSINESS_END = time(18, 0)


@dataclass(frozen=True, slots=True)
class SendWindowResult:
    allowed: bool
    reason: str
    current_time: datetime
    business_start: time
    business_end: time
    timezone: str
    is_weekend: bool
    is_holiday: bool


class SendWindowPolicy:
    def __init__(
        self,
        clock: Clock,
        business_start: time = DEFAULT_BUSINESS_START,
        business_end: time = DEFAULT_BUSINESS_END,
        holidays: set[tuple[int, int]] | None = None,
        ddd_to_timezone: dict[str, str] | None = None,
        default_timezone: str = DEFAULT_TIMEZONE,
    ):
        self._clock = clock
        self._business_start = business_start
        self._business_end = business_end
        self._holidays = holidays or NATIONAL_HOLIDAYS
        self._ddd_to_timezone = ddd_to_timezone or DDD_TO_TIMEZONE
        self._default_timezone = default_timezone

    def _get_timezone(self, ddd: str) -> ZoneInfo:
        tz_name = self._ddd_to_timezone.get(ddd, self._default_timezone)
        return ZoneInfo(tz_name)

    def _is_weekend(self, dt: datetime) -> bool:
        return dt.weekday() >= 5

    def _is_holiday(self, dt: datetime) -> bool:
        return (dt.day, dt.month) in self._holidays

    def _is_business_hours(self, dt: datetime) -> bool:
        current_time = dt.time()
        return self._business_start <= current_time < self._business_end

    def check(self, phone_ddd: str, reference_time: datetime | None = None) -> SendWindowResult:
        tz = self._get_timezone(phone_ddd)
        now = reference_time or self._clock.now(tz)

        is_weekend = self._is_weekend(now)
        is_holiday = self._is_holiday(now)
        is_business_hours = self._is_business_hours(now)

        if is_weekend:
            allowed = False
            reason = "Fim de semana"
        elif is_holiday:
            allowed = False
            reason = "Feriado nacional"
        elif not is_business_hours:
            allowed = False
            reason = f"Fora do horário comercial ({self._business_start.strftime('%H:%M')}-{self._business_end.strftime('%H:%M')})"
        else:
            allowed = True
            reason = "Dentro da janela de envio"

        return SendWindowResult(
            allowed=allowed,
            reason=reason,
            current_time=now,
            business_start=self._business_start,
            business_end=self._business_end,
            timezone=str(tz),
            is_weekend=is_weekend,
            is_holiday=is_holiday,
        )

    def is_allowed(self, phone_ddd: str, reference_time: datetime | None = None) -> bool:
        return self.check(phone_ddd, reference_time).allowed
