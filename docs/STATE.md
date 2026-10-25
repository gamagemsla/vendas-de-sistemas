# STATE.md — vendas-de-sistemas
Atualizado em: 23/10/2026
Branch e commit: master (Bloco C 100% Concluído)
Fase atual: Transição do Bloco C para a Fase F2 / Bloco D (Ingestão de Leads)

Validações comprovadas (Quality Gates Verdes):
- pytest tests/unit -q: 172 passed (100% em memória, zero I/O)
- pytest tests/integration -q: 7 passed (PostgreSQL real via vendas_db_test migrado pelo Alembic)
- python -m mypy src/vendas --strict: Success (0 erros em 97+ source files)
- ruff check src tests: All checks passed!
- ruff format --check src tests: All files formatted
- lint-imports: Contracts: 4 kept, 0 broken

Decisões e Entregas Consolidadas (Bloco C - Concluído):
- C1: Cobertura exaustiva de testes de integração em PostgreSQL real, isolamento blindado com trava de _test, e aplicação de schema via migrations do Alembic (`command.upgrade("head")`).
- C2: Modularização e versionamento de prompts no adaptador Gemini com suíte de avaliação adversarial (sem chamadas de rede no CI).
- C3: Manuais de operação e contingência documentados em docs/runbooks/ (sessao-caiu.md, numero-banido.md, dlq-cheia.md).

Próximo passo:
- Iniciar a Fase F2 / Bloco D: Ingestão e Conformidade (Adaptador Apify para buscas geolocalizadas, normalização de dados, deduplicação por CNPJ/telefone, e enriquecimento via Firecrawl).