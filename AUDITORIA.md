# Auditoria Estrutural — Vendas de Sistemas

**Data da Auditoria:** 17 de outubro de 2026  
**Ferramentas de Verificação:** pytest / mypy (strict) / lint-imports / ruff  
**Escopo:** Revisão estática e dinâmica de `src/`, `tests/` e configurações da raiz.

---

## 1. Status dos Portões de Qualidade (Make Check)

| Gate | Comando | Esperado | Observado | Status |
| :--- | :--- | :--- | :--- | :--- |
| **pytest** | `pytest tests` | 128+ verdes | 125 passed, 3 failed | **Vermelho** |
| **mypy** | `mypy src` | 0 erros (strict) | 2 erros em `catalog.py` | **Vermelho** |
| **import-linter** | `lint-imports` | 4 kept, 0 broken | 4 kept, 0 broken (Falso Verde via `importlib`) | **Amarelo** |
| **ruff** | `ruff check src tests`| 0 erros | 15 erros (`uow` + `catalog Depends`) | **Vermelho** |

---

## 2. Diagnóstico por Camada Hexagonal

* **Domain:** Parcial. Entidades, VOs e políticas sem SQLAlchemy/FastAPI. Porém, `Clock` e fakes vivem embolados em `ports/__init__.py`; entidades ainda usam `datetime.utcnow()` (depreciado no Python 3.12).
* **Application:** Violado. `catalog.py` importa `Session` do SQLAlchemy e carrega o ORM via `importlib` dinâmico explicitamente para furar o linter. Geração de tempo via `datetime.now`, não pelo port `Clock`.
* **Infrastructure:** Incompleto. Adaptadores Gemini, Apify, Firecrawl, Evolution, Telegram e Calendar existem. Contudo, `SQLAlchemyUnitOfWork` não inicializa `outbox` nem `enrollments`. Schema da tabela outbox diverge da interface do repositório.
* **Interfaces:** Violado. A API de catálogo importa `SqlAlchemyKnowledgeBase` diretamente. O webhook do WhatsApp não está incluído no `create_app` do FastAPI. Não existe ponto de entrada para o worker (`interfaces/worker.py`). Dashboard consulta ORM via container.
* **Bootstrap:** OK com ressalvas. `DRY_RUN=true` e `AUTOMATION_ENABLED=false` por padrão. `Settings` carrega o arquivo `.env` na importação do módulo.

---

## 3. Achados Priorizados

### [P0] - Crítico (Falhas de Testes, Bypasses e Falsos Verdes)
1. **Testes / Catálogo:** UUID cru em `KnowledgeChangeLog.entity_id` e `actor_id` quebra no SQLite (2 unitários falhando). No PostgreSQL real, `drop_all`/`create_all` nos testes de integração explode no tipo enum/tabela `companies`.
2. **Arquitetura (Application):** `application/commands/catalog.py` declara importação dinâmica via `importlib` classificada no código como *"invisível ao import-linter"*. Violação grave de fronteira hexagonal.
3. **Arquitetura (Interfaces):** `interfaces/api/routes/catalog.py` importa `vendas.infrastructure` diretamente. Deveria quebrar o contrato 4 do linter, mas o linter reportou falso positivo.

### [P1] - Alto (Composição de Runtime, Outbox e Falhas de Segurança)
1. **Composição do UoW:** `SQLAlchemyUnitOfWork` só instancia `leads`. Chamadas em cadência e inbound para `uow.outbox` e `uow.enrollments` retornam `None`.
2. **Divergência de Schema da Outbox:** O método `Outbox.add` espera `event_type`, `payload` e `attempts`; o modelo ORM do banco foi mapeado com `channel`, `to_phone` e `retry_count`.
3. **Runtime Incompleto:** Webhook do WhatsApp não possui `include_router` no `create_app`. Não existe arquivo executável `interfaces/worker.py`. A biblioteca `google-generativeai` está em uso mas não foi declarada no `pyproject.toml`.
4. **Segurança Básica:** Autenticação do catálogo aceita qualquer token Bearer se acompanhado do cabeçalho `X-User-Role`. Dashboard envia `Bearer local-dev` fixo. Ausência de `.gitignore` na raiz (risco crítico de expor `.env` no Git).

### [P2] - Médio (LGPD nos Logs, Resiliência e Débitos Técnicos)
1. **LGPD / Logs:** Máscara de sanitização só atua se a chave do dicionário contiver `phone` ou `email`. O webhook loga abertamente `remote_jid` e `content_preview`. O Dispatcher em `DRY_RUN` loga o payload completo com dados pessoais.
2. **Resiliência:** Falha do Gemini faz fallback ingênuo para handoff (não possui circuit-breaker real para 429/503). Firecrawl e Calendar apenas devolvem dict/lista vazia sem tratamento. Apify lança `RuntimeError` não tratado. Sem política de retentativa exponencial.
3. **Domínio e Depreciações:** `domain/ports/__init__.py` possui ~800 linhas duplicando outros ports menores. Entidades usam `datetime.utcnow()`.
4. **Streamlit & Migrations:** `1_Catalogo.py` usa `form_submit_button` fora de `st.form`. Métricas do dashboard Overview possuem valores hardcoded (`contatados=0`, `em conversa=1`). A pasta `alembic/versions` está vazia (schema de testes via `Base.metadata.create_all`).

---

## 4. Próximo Corte de Ação Recomendado (Fase P0)
1. Serializar UUID como `str` nos logs/modelo