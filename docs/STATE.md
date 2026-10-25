# STATE.md — vendas-de-sistemas
Atualizado em: 25/10/2026
Branch e commit: master (Blocos A, B e C integralmente auditados e selados)
Fase atual: Transição para a Fase F2 (Ingestão de Leads e Conformidade)

Validações comprovadas (Quality Gates 100% Verdes):
- pytest tests/unit -q: 173 passed, 1 warning (execução 100% em memória, zero I/O)
- pytest tests/integration -q: 12 passed, 3 warnings (PostgreSQL ativo via vendas_db_test isolado com Alembic)
- python -m mypy src/vendas --strict: Success (0 erros em 98 source files)
- ruff check src tests: All checks passed!
- ruff format --check src tests: 128 files formatted
- lint-imports: Contracts: 4 kept, 0 broken (regras de composition root declaradas)

Decisões e Entregas Consolidadas (Blocos A, B e C):
- Bloco A: Clock(Protocol) UTC em domain/ports; schemas Pydantic por event_type na outbox; Kill Switch global na API (503 com Retry-After) e no dispatcher; Opt-out mandatório gravando em suppression_list e bloqueando cadência; backoff exponencial base 2 com jitter de 10%; ponto único de DRY_RUN no dispatcher; mascaramento recursivo de PII contra referências circulares; correlation_id de ponta a ponta; autenticação por API Key com papéis admin/operator via hmac.compare_digest.
- Bloco B: Isolamento físico do banco de testes em tests/integration/conftest.py (com trava de segurança _test e OIDs de vendas_db comprovadamente intocados); purga de datetime.utcnow() no domínio; KnowledgeBase como fonte única integrada ao inbound com PostAiValidator anti-alucinação de preços; ConversationLock com advisory locks transacionais no Postgres; dashboard Streamlit isolado de ORM/UoW operando via application.queries; worker assíncrono em interfaces/worker/main.py.
- Bloco C (Fundação e Testes): Suíte de integração cobrindo UoW, constraints de unicidade e rollbacks no Postgres; setup de testes via migrations reais do Alembic (command.upgrade("head")); modularização e versionamento de prompts no Gemini com suíte de avaliação adversarial em tests/evaluation/ (sem rede no CI); runbooks operacionais em docs/runbooks/ (sessao-caiu.md, numero-banido.md, dlq-cheia.md).
- Faxina Arquitetural: Eliminação completa de importlib.import_module no container.py, unificação de autenticação no SettingsAuthAdapter oficial e declaração formal dos 3 pontos de composição no .importlinter.

================================================================================
INVENTÁRIO DO QUE FALTA PARA TERMINAR O SISTEMA (FASES F2 A F9)
================================================================================

1. Fase F2 — Ingestão e Conformidade (Próxima Fase Imediata):
   - F2-01: Adaptador ApifyLeadSource (src/vendas/infrastructure/providers/apify.py) com timeout, paginação, limite de custo e testes de contrato com payloads gravados.
   - F2-02: Caso de uso IngestLeadsCommand (normalização de CNPJ/telefone, deduplicação em banco e gravação como NEW).
   - F2-03: Adaptador FirecrawlLeadEnricher (src/vendas/infrastructure/providers/firecrawl.py) e EnrichLeadCommand (extração web, tolerância a falhas parciais).
   - F2-04: Pipeline de Elegibilidade (validação de celular, base legal registrada com origem, verificação de supressão e filtro de ICP).
   - F2-05: Rotinas de Supressão e Opt-out (importação de lista de bloqueio inicial).
   - F2-06: Controle de custo de provedores (contador diário, corte automático ao atingir o teto de orçamento e alerta).
   - F2-07: Execução agendada de ingestão integrada ao worker.

2. Fase F3 — Cadência Ativa e E-mail:
   - F3-01: Definição da cadência em configuração versionada (passos, intervalos, canais).
   - F3-02: Caso de uso EnrollInCadenceCommand (inscrição atômica de leads elegíveis).
   - F3-03: Integração do SendMessage com validações de janela, teto diário e estado do canal.
   - F3-06: Adaptador de e-mail (SMTP/transacional) com link de descadastro (SPF/DKIM) para fallback quando o WhatsApp não responder.

3. Fase F4 — Canal WhatsApp (Evolution API / Baileys):
   - F4-01: Instância dedicada de teste e pareamento por QR Code.
   - F4-02: Adaptador EvolutionWhatsAppChannel com presença ("digitando...") e verificação se o número possui WhatsApp ativo.
   - F4-03: Rota de Webhook em interfaces/api/webhooks/whatsapp.py exposta no app.py com segredo comparado em tempo constante, gravação em inbound_events com deduplicação por provider_message_id e descarte de grupos/status.
   - F4-04: Eventos de conexão atualizando o estado do canal e pausando envios em caso de desconexão.
   - F4-05: Mapeamento de identificadores de contato e detecção de intervenção humana (takeover automático).
   - F4-06/F4-07: Testes de contrato com payloads gravados e teste ponta a ponta com número de teste.

4. Fase F5 — Conclusão da IA Conversacional:
   - F5-08: Caso de uso de retomada explícita pós-takeover humano.
   - F5-09: Tratamento de mensagens não textuais (áudio para handoff, resposta padrão para imagens/documentos).
   - F5-10: Objeto estruturado de critérios de qualificação (transição para QUALIFIED).
   - F5-11: Execução e homologação do dataset com 60+ conversas adversariais reais com o Gemini.

5. Fase F6 — Agendamento e Notificações (Telegram):
   - F6-01: Decisão formal de provedor de agenda (Google Calendar vs Cal.com) via ADR.
   - F6-02: Adaptador Calendar e testes de contrato (free_slots, book, cancel).
   - F6-03: Caso de uso ScheduleMeetingCommand com prevenção de double booking.
   - F6-04: Remarcação, cancelamento e lembretes com fuso horário explícito.
   - F6-05/F6-07: Adaptador TelegramNotifier integrado ao evento MeetingBooked via outbox para avisos ao operador em tempo real.

6. Fase F7 — Dashboard Operacional (Streamlit Completo):
   - F7-03: Telas em interfaces/dashboard/pages/ para funil de leads, gerenciamento de cadências, fila de disparos e estado da sessão Baileys (com exibição de QR Code).
   - F7-05: Ações do operador (pausar cadência, assumir conversa, editar catálogo, marcar opt-out) chamando rotas autenticadas da API (incluindo rota /conversations/{id}/takeover).
   - F7-06: Métricas, alertas de DLQ e monitoramento de consumo financeiro dos provedores.

7. Fase F8 — Hardening e Implantação:
   - F8-01: Auditoria estática de dependências, rate limit e CORS na API.
   - F8-02: Isolamento de rede (Postgres e Evolution exclusivamente internos) e proxy reverso com TLS.
   - F8-03: Rotinas de backup do banco e do volume persistente da sessão Baileys, com restauração testada.
   - F8-04: Rotina automatizada para atendimento aos direitos do titular da LGPD (exportação, anonimização e exclusão).
   - F8-05: Testes de carga (3x volume) e testes de caos.
   - F8-06/F8-07: Pipeline de deploy com migração reversível e checklist de produção 100%.

8. Fase F9 — Rollout Controlado:
   - Estágios 0 a 4 (Dry-run em prod -> Interno com números próprios -> Assistido -> Semi-autônomo -> Autônomo).

Dívidas Técnicas Menores Mapeadas para Limpeza:
- Limpar import indevido de orm_models em src/vendas/interfaces/api/routes/catalog.py (achado P0 #3).
- Podar as 5 linhas redundantes de ignore adicionadas no .importlinter (mantendo apenas as 3 legítimas do container).
- Migrar o projeto para fora da pasta do OneDrive para eliminar bloqueios de I/O em arquivos do .git.

Próximo passo:
- Iniciar a Fase F2 pela Tarefa F2-01: Adaptador ApifyLeadSource e Testes de Contrato.