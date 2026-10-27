"""Adaptador de infraestrutura para envio de e-mails via SMTP."""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import structlog

from vendas.bootstrap.settings import settings
from vendas.domain.ports.message_channel import MessageChannel

logger = structlog.get_logger(__name__)


class EmailChannel(MessageChannel):
    """Adaptador para envio de e-mails transacionais via SMTP."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        from_email: str | None = None,
        use_tls: bool = True,
    ) -> None:
        self._host = host or settings.SMTP_HOST
        self._port = port or settings.SMTP_PORT
        self._username = username or settings.SMTP_USER
        self._password = password or settings.SMTP_PASS
        self._from_email = from_email or settings.EMAIL_FROM
        self._use_tls = use_tls

    def send(self, msg_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Envia e-mail via SMTP.

        Espera payload com chaves:
        - to_email: str
        - subject: str
        - html_content: str
        - text_content: str | None
        - unsubscribe_link: str
        - channel: "email"
        """
        to_email = msg_payload.get("to_email")
        subject = msg_payload.get("subject")
        html_content = msg_payload.get("html_content")
        text_content = msg_payload.get("text_content")
        unsubscribe_link = msg_payload.get("unsubscribe_link")

        if not to_email or not subject or not html_content or not unsubscribe_link:
            raise ValueError("Payload de e-mail inválido: campos obrigatórios ausentes.")

        # DRY_RUN: apenas loga e retorna recibo simulado sem conectar ao SMTP
        if settings.DRY_RUN:
            logger.info(
                "dry_run_email_simulado",
                to_email=to_email,
                subject=subject,
                from_email=self._from_email,
                unsubscribe_link=unsubscribe_link,
            )
            return {
                "status": "sent",
                "to": to_email,
                "subject": subject,
                "message_id": f"dry-run-{hash((to_email, subject)) & 0xFFFFFFFF:08x}",
                "dry_run": True,
            }

        # Monta a mensagem MIME
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self._from_email
        message["To"] = to_email
        # Cabeçalho List-Unsubscribe para conformidade anti-spam (RFC 8058)
        message["List-Unsubscribe"] = f"<{unsubscribe_link}>"

        # Parte texto (fallback)
        if text_content:
            part_text = MIMEText(text_content, "plain", "utf-8")
        else:
            # Gera versão texto simples a partir do HTML (básico)
            import re

            text_content = re.sub("<[^<]+?>", "", html_content)
            part_text = MIMEText(text_content, "plain", "utf-8")

        # Parte HTML
        part_html = MIMEText(html_content, "html", "utf-8")

        message.attach(part_text)
        message.attach(part_html)

        # Envia via SMTP
        try:
            if self._use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self._host, self._port) as server:
                    server.starttls(context=context)
                    if self._username and self._password:
                        server.login(self._username, self._password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(self._host, self._port) as server:
                    if self._username and self._password:
                        server.login(self._username, self._password)
                    server.send_message(message)

            return {
                "status": "sent",
                "to": to_email,
                "subject": subject,
                "message_id": message.get("Message-ID", ""),
            }

        except smtplib.SMTPException as e:
            raise RuntimeError(f"Falha ao enviar e-mail via SMTP: {e}") from e
