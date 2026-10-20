# STATE.md — vendas-de-sistemas
Atualizado em: 20/10/2026
Branch e commit: master (após Tarefa A1.3)
Fase: Bloco A — Refatoração de Responsabilidades

Validações comprovadas (todas verdes):
- pytest tests/unit -q: 131 passed
- pytest tests/integration -q: 5 passed, 1 warning (PostgreSQL local ativo)
- python -m mypy src/vendas --strict: Success (82 source files)
- ruff check src tests: All checks passed!
- ruff format --check src tests: 98 files already formatted
- lint-imports: Contracts: 4 kept, 0 broken

Decisões consolidadas:
- Tarefa 1.1 concluída: queue/outbox.py alinhado a OutboxModel (retry_count, OutboxStatus e model.max_retries).
- Tarefa A1.1 concluída: Port Clock canônico (typing.Protocol) em domain/ports/clock.py; SystemClock com UTC em infrastructure/clock.py; FakeClock movido exclusivamente para tests/fakes/fakes.py.
- Tarefa A1.2 concluída: Clock injetado via SQLAlchemyUnitOfWork e repositórios de persistência; eliminados datetime.utcnow() e datetime.now() sem fuso em repositories.py; remoção de started_at e correção de contact_email.
- Tarefa A1.3 concluída: Clock injetado em queue/outbox.py; claim_pending filtra por scheduled_at <= now ou IS NULL com SKIP LOCKED; teste de integração comportamental adicionado.

Pendências imediatas:
- A1.4: Gerar baseline de migration Alembic em alembic/versions/ (reversível) com orm_models importado em env.py.
- Bloco A (itens restantes):
  * A2: Guardas e validação de payload no queue
  * A3: Kill switch (booleano e middleware)
  * A4: Opt-out (Contact e SuppressionList)
  * A5: Handoff com backoff exponencial
  * A6: DRY_RUN mode flag e simulação
  * A7: Logs estruturados (JSON) e correlationId
  * A8: Autenticação de API (API Key e roles)
- Infraestrutura de testes: isolar vendas_db_test para evitar conflito com docker-compose.

Próximo passo:
- Executar a Fase 2 da Tarefa A1.4 no Cline (gerar initial baseline schema no Alembic e testar upgrade head / downgrade base).