# STATE.md — vendas-de-sistemas
Atualizado em: 20/10/2026
Branch e commit: master (após Tarefa A1.1)
Fase: Bloco A — Refatoração de Responsabilidades

Validações comprovadas (todas verdes):
- unit: 131 passed
- integração: 4 passed, 1 warning
- mypy strict: Success (82 arquivos)
- ruff check: All checks passed
- ruff format: All files are formatted
- lint-imports: 4 kept, 0 broken

Decisões consolidadas:
- Tarefa 1.1 concluída: queue/outbox.py compatível com OutboxModel (retry_count e OutboxStatus).
- Tarefa A1.1 concluída: Port Clock canônico definido via typing.Protocol em src/vendas/domain/ports/clock.py.
- SystemClock implementado em src/vendas/infrastructure/clock.py garantindo datetime com fuso UTC explícito.
- Purgada a violação de fakes em src/: FakeClock movido estritamente para tests/fakes/fakes.py; domain/ports exporta apenas o port Clock.
- Bootstrap/container.py atualizado para resolver SystemClock da infraestrutura.

Pendências imediatas:
- A1.2: Injetar Clock no UnitOfWork e nos repositórios; eliminar datetime.utcnow() e now() sem fuso em repositories.py; corrigir started_at e contact_email.
- A1.3: Injetar Clock em queue/outbox.py e filtrar claim_pending por scheduled_at <= now.
- A1.4: Baseline inicial e migrations do Alembic (alembic/versions continua vazia).
- Infraestrutura de testes: separar o banco de integração (vendas_db_test) para evitar concorrência com docker-compose.

Próximo passo:
- Iniciar a Tarefa A1.2 na nova janela do Cline (executando apenas a Fase 1: Diagnóstico somente leitura).