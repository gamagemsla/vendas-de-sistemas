# STATE.md — vendas-de-sistemas
Atualizado em: 20/10/2026
Branch e commit: (conferir: git branch --show-current; git log --oneline -1)
Fase: correções do Bloco A, Item 1 (repositórios completos)

Validações (relatadas pelo Cline, a reconfirmar):
- unit: 130 passam; integração: 3 passam e 1 falha conhecida (test_outbox_contract_between_repositories)
- mypy strict, ruff e lint-imports (4 contratos): verdes

Decisões:
- Outbox, Opção B reduzida: OutboxModel ganha event_type, payload e idempotency_key (única); sem aggregate_* nem priority
- Tarefa 1 (refatoração do Outbox) mergeada; Tarefa 1.1 alinha queue/outbox.py (attempts para retry_count; status em minúsculas)
- Ordem seguinte: Clock e datetimes com fuso; ports e assinaturas; claim_due com SKIP LOCKED; migration inicial; testes de integração dos repositórios; depois itens 2 a 8 do Bloco A

Pendências:
- Confirmar o estado de main: pode conter arquivos .diff e o teste de integração que ainda falha
- Banco de testes usa o mesmo banco do docker-compose (vendas_db) com drop_all/create_all: separar para vendas_db_test
- Projeto dentro do OneDrive (bloqueia arquivos do .git): mover
- A verificar na auditoria: Conversation.add grava started_at (coluna inexistente?); contact_email ignorado no mapper; claim_pending sem filtro scheduled_at; mark_processing e is_suppressed com assinatura divergente do port
- Dois SQLAlchemyOutboxRepository (persistence e queue): escolher o canônico e ligar o unit_of_work
- type: ignore em ConversationState; índices duplicados em Lead, Opportunity, Conversation, KnowledgeChangeLog e Contact
- Regra de dead-letter duplicada e divergente (limite fixo de 5 em queue/outbox.py)
- alembic/versions vazio: nenhuma migration existe
- Agenda: Google Calendar ou Cal.com, em aberto. Bot do Telegram: token e chat_id por configurar

Próximo passo: Tarefa 1.1