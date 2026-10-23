# STATE.md — vendas-de-sistemas
Atualizado em: 23/10/2026
Branch e commit: master (Gate do Bloco B Aprovado)
Fase atual: Transição para o Bloco C (Itens 13 a 15)

Validações comprovadas (Quality Gates Verdes):
- pytest tests/unit -q: 172 passed (100% em memória, zero I/O)
- pytest tests/integration -q: 7 passed (PostgreSQL ativo via vendas_db_test)
- python -m mypy src/vendas --strict: Success (0 erros em 97 source files)
- ruff check src tests: All checks passed!
- ruff format --check src tests: 124 files already formatted
- lint-imports: Contracts: 4 kept, 0 broken

Decisões e Entregas Consolidadas (Blocos A e B):
- Bloco A: Clock(Protocol) UTC, Schemas Pydantic na outbox, Kill Switch global, Opt-out mandatório, Backoff exponencial base 2, DRY_RUN no dispatcher com mascaramento recursivo de PII, Correlation ID e Autenticação por API Key.
- Bloco B: Isolamento formal do banco de testes em tests/integration/conftest.py, purga de utcnow no domínio, KnowledgeBase como fonte única com PostAiValidator, ConversationLock via advisory locks do Postgres, Dashboard via read-models e Worker assíncrono isolado de infraestrutura.

Próximo passo:
- Iniciar o Bloco C (conforme plano canônico reconciliado):
  * Item 13 (Tarefa C1): Testes de Integração em PostgreSQL Real (cobertura profunda de repositórios, UoW e transações).
  * Item 14 (Tarefa C2): Suíte de Avaliação de IA e Prompts Versionados (dataset de conversas adversariais e guardrails).
  * Item 15 (Tarefa C3): Runbooks de Operação e Contingência em docs/runbooks/.