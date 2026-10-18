from datetime import datetime

import httpx


class ExternalCalendarAdapter:
    """Adaptador de infraestrutura para integração com provedor de agendamento externo (Google Calendar / Cal.com)."""

    def __init__(self, api_base_url: str, api_key: str, client: httpx.Client | None = None) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=20.0)

    def get_free_slots(self, start_date: datetime, end_date: datetime) -> list[datetime]:
        """Busca horários disponíveis na agenda do responsável."""
        url = f"{self._api_base_url}/slots"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        params = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        }

        try:
            response = self._client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            # Retorna lista de datetimes parseados
            return [datetime.fromisoformat(slot["start"]) for slot in data.get("slots", [])]
        except httpx.HTTPError:
            # Em caso de falha externa, retorna lista vazia (degradação para handoff)
            return []

    def book_slot(
        self, slot_time: datetime, attendee_name: str, attendee_email: str, phone: str
    ) -> str | None:
        """Efetiva o agendamento no calendário externo e retorna o ID do evento criado."""
        url = f"{self._api_base_url}/bookings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "start_time": slot_time.isoformat(),
            "attendee_name": attendee_name,
            "attendee_email": attendee_email,
            "attendee_phone": phone,
        }

        try:
            response = self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            booking_id = data.get("booking_id") or data.get("id")
            return str(booking_id) if booking_id else None
        except httpx.HTTPError:
            return None
