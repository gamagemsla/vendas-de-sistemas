# STATE.md — vendas-de-sistemas
Atualizado em: 29/10/2026
Branch e commit: master (Plano de Construção F0 a F9 Concluído com Sucesso)
Fase atual: Sistema Pronto para Operação / Estágio 0 do Rollout Controlado

Métricas Finais de Qualidade (Quality Gates 100% Verdes):
- pytest tests/unit -q: 239 passed (execução pura em memória, zero I/O)
- pytest tests/integration -q: 12 passed (PostgreSQL ativo via vendas_db_test isolado com migrations do Alembic)
- tests/contract: 18 passed (Apify, Firecrawl e Evolution validados com MockTransport sem rede)
- tests/evaluation: 7 passed (suíte adversarial de IA contra prompt injection e alucinação de preços)
- python -m mypy src/vendas --strict: Success (0 erros em 117 source files)
- ruff check src tests: All checks passed!
- ruff format --check src tests: 100% formatado
- lint-imports: Contracts: 4 kept, 0 broken

Status de Entrega das Fases (100% Concluídas):
- F0 Fundação: Concluída e auditada.
- F1 Domínio e Persistência: Concluída e auditada.
- F2 Ingestão e Conformidade: Concluída e auditada.
- F3 Cadência e Outbox: Concluída e auditada.
- F4 Canal Evolution: Concluída e auditada.
- F5 IA e Base Comercial: Concluída e auditada.
- F6 Agendamento: Concluída e auditada.
- F7 Dashboard e Operação: Concluída e auditada.
- F8 Hardening e Implantação: Concluída e auditada.
- F9 Rollout Controlado: Concluída e homologada (docs/runbooks/rollout-estagios.md).

Próximo passo:
- Iniciar a operação no Estágio 0 (Dry-Run em Produção) seguindo rigorosamente o checklist de docs/runbooks/rollout-estagios.md.