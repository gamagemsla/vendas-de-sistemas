"""Testes unitários para comandos LGPD (Direitos do Titular)."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID, uuid4

import pytest

from vendas.application.commands.lead_data_subject import (
    AnonymizeLeadDataCommand,
    AnonymizeLeadDataHandler,
    DeleteLeadDataCommand,
    DeleteLeadDataHandler,
    ExportLeadDataCommand,
    ExportLeadDataHandler,
)
from vendas.domain.ports.lead_data_subject import LeadDataExport, LeadDataSubjectPort


class FakeLeadDataSubjectPort(LeadDataSubjectPort):
    """Fake do port para testes unitários."""

    def __init__(self) -> None:
        self.exported_lead_id: UUID | None = None
        self.anonymized_lead_id: UUID | None = None
        self.deleted_lead_id: UUID | None = None
        self._export_result: LeadDataExport | None = None

    def set_export_result(self, result: LeadDataExport) -> None:
        self._export_result = result

    async def export(self, lead_id: UUID) -> LeadDataExport:
        self.exported_lead_id = lead_id
        if self._export_result is None:
            raise ValueError("Export result not configured")
        return self._export_result

    async def anonymize(self, lead_id: UUID) -> None:
        self.anonymized_lead_id = lead_id

    async def delete(self, lead_id: UUID) -> None:
        self.deleted_lead_id = lead_id


class FakeUnitOfWork:
    """Fake UoW para testes."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    async def commit_async(self) -> None:
        self.committed = True

    async def rollback_async(self) -> None:
        self.rolled_back = True


@pytest.fixture
def fake_port() -> FakeLeadDataSubjectPort:
    return FakeLeadDataSubjectPort()


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def sample_export() -> LeadDataExport:
    lead_id = uuid4()
    return LeadDataExport(
        lead_id=lead_id,
        phone="+5511999999999",
        email="test@example.com",
        name="Test Lead",
        cnpj="12345678000199",
        status="NEW",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        inbound_events=[],
        outbox_messages=[],
        cadence_enrollments=[],
        conversation_history=[],
        suppression_records=[],
    )


class TestExportLeadDataHandler:
    """Testes para ExportLeadDataHandler."""

    @pytest.mark.asyncio
    async def test_export_returns_data(
        self, fake_port: FakeLeadDataSubjectPort, sample_export: LeadDataExport
    ) -> None:
        fake_port.set_export_result(sample_export)
        handler = ExportLeadDataHandler(port=fake_port)
        command = ExportLeadDataCommand(lead_id=sample_export.lead_id)

        result = await handler.handle(command)

        assert result == sample_export
        assert fake_port.exported_lead_id == sample_export.lead_id

    @pytest.mark.asyncio
    async def test_export_raises_when_port_raises(self, fake_port: FakeLeadDataSubjectPort) -> None:
        handler = ExportLeadDataHandler(port=fake_port)
        command = ExportLeadDataCommand(lead_id=uuid4())

        with pytest.raises(ValueError, match="Export result not configured"):
            await handler.handle(command)


class TestAnonymizeLeadDataHandler:
    """Testes para AnonymizeLeadDataHandler."""

    @pytest.mark.asyncio
    async def test_anonymize_calls_port_and_commits(
        self, fake_port: FakeLeadDataSubjectPort, fake_uow: FakeUnitOfWork
    ) -> None:
        handler = AnonymizeLeadDataHandler(port=fake_port, uow=fake_uow)
        lead_id = uuid4()
        command = AnonymizeLeadDataCommand(lead_id=lead_id)

        await handler.handle(command)

        assert fake_port.anonymized_lead_id == lead_id
        assert fake_uow.committed is True
        assert fake_uow.rolled_back is False

    @pytest.mark.asyncio
    async def test_anonymize_rolls_back_on_error(
        self, fake_port: FakeLeadDataSubjectPort, fake_uow: FakeUnitOfWork
    ) -> None:
        async def failing_anonymize(lead_id: UUID) -> None:
            raise RuntimeError("DB error")

        fake_port.anonymize = failing_anonymize  # type: ignore[method-assign]
        handler = AnonymizeLeadDataHandler(port=fake_port, uow=fake_uow)
        command = AnonymizeLeadDataCommand(lead_id=uuid4())

        with pytest.raises(RuntimeError, match="DB error"):
            await handler.handle(command)

        assert fake_uow.rolled_back is True
        assert fake_uow.committed is False


class TestDeleteLeadDataHandler:
    """Testes para DeleteLeadDataHandler."""

    @pytest.mark.asyncio
    async def test_delete_calls_port_and_commits(
        self, fake_port: FakeLeadDataSubjectPort, fake_uow: FakeUnitOfWork
    ) -> None:
        handler = DeleteLeadDataHandler(port=fake_port, uow=fake_uow)
        lead_id = uuid4()
        command = DeleteLeadDataCommand(lead_id=lead_id)

        await handler.handle(command)

        assert fake_port.deleted_lead_id == lead_id
        assert fake_uow.committed is True
        assert fake_uow.rolled_back is False

    @pytest.mark.asyncio
    async def test_delete_rolls_back_on_error(
        self, fake_port: FakeLeadDataSubjectPort, fake_uow: FakeUnitOfWork
    ) -> None:
        async def failing_delete(lead_id: UUID) -> None:
            raise RuntimeError("DB error")

        fake_port.delete = failing_delete  # type: ignore[method-assign]
        handler = DeleteLeadDataHandler(port=fake_port, uow=fake_uow)
        command = DeleteLeadDataCommand(lead_id=uuid4())

        with pytest.raises(RuntimeError, match="DB error"):
            await handler.handle(command)

        assert fake_uow.rolled_back is True
        assert fake_uow.committed is False
