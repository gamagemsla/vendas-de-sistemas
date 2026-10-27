from datetime import datetime

from vendas.domain.ports import Clock, UnitOfWork
from vendas.domain.ports.notifier import NotifierPort


class ScheduleMeetingCommand:
    def __init__(self, uow: UnitOfWork, notifier: NotifierPort, clock: Clock) -> None:
        self._uow = uow
        self._notifier = notifier
        self._clock = clock

    def execute(
        self, lead_id: str, slot_time: datetime, timezone: str = "America/Sao_Paulo"
    ) -> bool:
        with self._uow as uow:
            lead = uow.leads.get(lead_id)
            if not lead:
                return False

            if hasattr(uow, "bookings") and uow.bookings:
                if uow.bookings.exists_at(slot_time):
                    return False
                uow.bookings.create(
                    lead_id=lead.id,
                    slot_time=slot_time,
                    timezone=timezone,
                    status="CONFIRMED",
                )

            uow.leads.save(lead)
            uow.commit()

        alert_message = (
            " *NOVA REUNIÃO AGENDADA!*\n\n"
            f" *Lead:* {lead.name}\n"
            f" *Data/Hora:* `{slot_time.strftime('%d/%m/%Y às %H:%M')} ({timezone})`\n"
            f" *Telefone:* `{lead.phone}`"
        )
        self._notifier.send_alert(alert_message)
        return True
