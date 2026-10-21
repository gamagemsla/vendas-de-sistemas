# STATE.md — vendas-de-sistemas
Atualizado em: 20/10/2026
Branch e commit: master (Bloco A 100% Concluído)
Fase atual: Transição do Bloco A para Bloco B / Fase F2

Validações comprovadas (Quality Gates Verdes):
- pytest tests/unit -q: 170 passed
- pytest tests/integration -q: 5 passed (PostgreSQL ativo)
- python -m mypy src/vendas --strict: Success (89 source files)
- ruff check src tests: All checks passed!
- ruff format --check src tests: 111 files already formatted
- lint-imports: Contracts: 4 kept, 0 broken

Decisões e Entregas Consolidadas (Bloco A - Itens 1 a 8):
- A1: Port Clock(Protocol) UTC, injeção no UoW/repositórios, claim_pending com SKIP LOCKED temporal, baseline Alembic reversível e fix de enums no Postgres.
- A2: Schemas de payload Pydantic por event_type e validação defensiva na criação e no dispatcher.
- A3: Kill Switch global no settings, parada imediata no dispatcher e middleware de proteção na API.
- A4: Opt-out mandatório, gravação na suppression_list e bloqueio estrito em cadências.
- A5: Retry policy de base 2 com jitter de 10% e persistência de scheduled_at futuro para falhas transientes.
- A6: DRY_RUN controlado exclusivamente pelo OutboxDispatcher com mascaramento recursivo de PII para LGPD.
- A7: Propagação de correlation_id em headers HTTP e por ciclo de mensagem no worker via structlog.
- A8: Autenticação da API por tokens estáticos (dev/prod) com controle de papéis (admin/operator) e hmac.compare_digest.

Próximo passo:
- Iniciar o Bloco B (Ingestão, Provedores Externos e Deduplicação - Fase F2).