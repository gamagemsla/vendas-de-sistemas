from vendas.bootstrap.settings import settings
from vendas.infrastructure.channels.email_channel import EmailChannel


def test_email_channel_dry_run_simulates_sending(monkeypatch):
    monkeypatch.setattr(settings, "DRY_RUN", True)
    channel = EmailChannel()
    payload = {
        "to_email": "lead@empresa.com",
        "subject": "Contato Comercial",
        "html_content": "<p>Olá lead</p>",
        "unsubscribe_link": "http://localhost:8000/unsubscribe?lead_id=123",
        "channel": "email",
    }
    receipt = channel.send(payload)
    assert receipt is not None
