# Runbook: Rollout Controlado — Estágios 0 a 4

**Versão**: 1.0  
**Data**: 29/10/2026  
**Responsáveis**: Tech Lead, Engenheiro de Plantão, Product Owner  
**Classificação**: Interno — Governança Operacional  

---

## Objetivo

Definir o processo oficial de ativação progressiva do sistema de prospecção B2B em produção, garantindo **segurança por default**, **observabilidade contínua** e **capacidade de regressão imediata** a qualquer momento.

O rollout ocorre em **5 estágios (0 a 4)**, cada um com critérios objetivos de promoção, variáveis de ambiente dedicadas e gatilhos de rollback automático.

---

## 0. Cabeçalho e Metadados

| Campo | Valor |
|-------|-------|
| **Documento** | `docs/runbooks/rollout-estagios.md` |
| **Sistema** | vendas-de-sistemas (API + Worker + Dashboard) |
| **Ambientes** | Staging → Produção (single-tenant) |
| **Frequência de Revisão** | A cada promoção de estágio + revisão trimestral |
| **Aprovação Mínima** | Tech Lead + Eng. Plantão (Estágios 0→1, 1→2); PO + Tech Lead (2→3, 3→4) |

---

## 1. Visão Geral dos 5 Estágios

| Estágio | Nome | Descrição Resumida | Flags Principais | Público-Alvo | Risco | Duração Mínima |
|---------|------|-------------------|------------------|--------------|-------|----------------|
| **0** | **Dry-run em Produção** | Logs simulados, zero envio real. Valida pipeline completo (ingestão → cadência → dispatcher → outbox) sem tocar Evolution API. | `DRY_RUN=true`<br>`AUTOMATION_ENABLED=false` | Nenhum (apenas logs) | **Zero** | 7 dias sem erros críticos |
| **1** | **Teste Interno** | Envio real apenas para números da equipe (máx. 5). Valida ida/volta, opt-out, handoff humano, agendamento. | `DRY_RUN=false`<br>`AUTOMATION_ENABLED=true`<br>`DAILY_SEND_CAP=20` | Números internos (whitelist) | **Baixo** | 5 dias + 100 msgs sem banimento |
| **2** | **Modo Assistido** | IA sugere resposta no dashboard; operador **aprova cada mensagem** antes do envio. Leads reais (baixo volume). | `DRY_RUN=false`<br>`AUTOMATION_ENABLED=true`<br>`DAILY_SEND_CAP=50`<br>`HUMAN_APPROVAL_REQUIRED=true` | 10–20 leads reais/dia | **Médio** | 7 dias + taxa aprovação > 90% |
| **3** | **Semi-Autônomo** | IA responde **preço/serviço da KB** automaticamente; demais intenções → handoff humano. Tetos ativos. | `DRY_RUN=false`<br>`AUTOMATION_ENABLED=true`<br>`DAILY_SEND_CAP=200`<br>`AUTO_REPLY_KB_ONLY=true` | 50–100 leads/dia | **Médio-Alto** | 14 dias + 0 alucinação de preço |
| **4** | **Autônomo Completo** | `qualify_and_schedule` ativo com tetos, pausas, janelas, consentimento. Supervisão por métricas/alertas. | `DRY_RUN=false`<br>`AUTOMATION_ENABLED=true`<br>`DAILY_SEND_CAP=1000`<br>`FULL_AUTONOMY=true` | Volume total (ICP filtrado) | **Controlado** | Contínuo (monitoramento permanente) |

> **Regra de Ouro**: **Nenhum estágio pula validação**. Promoção só ocorre com **checklist 100% verde** e **assinatura dos responsáveis**.
---

## 2. Matriz de Variáveis de Ambiente por Estágio

### 2.1 Tabela Consolidada

| Variável | Estágio 0 | Estágio 1 | Estágio 2 | Estágio 3 | Estágio 4 | Descrição |
|----------|-----------|-----------|-----------|-----------|-----------|-----------|
| `DRY_RUN` | `true` | `false` | `false` | `false` | `false` | Simula envio (log only) |
| `AUTOMATION_ENABLED` | `false` | `true` | `true` | `true` | `true` | Habilita worker de cadência/outbox |
| `KILL_SWITCH` | `false` | `false` | `false` | `false` | `false` | Para **todo** envio global (emergência) |
| `CADENCE_GLOBAL_PAUSE` | `false` | `false` | `false` | `false` | `false` | Pausa cadências (mantém ingestão) |
| `DAILY_SEND_CAP` | `0` | `20` | `50` | `200` | `1000` | Teto global de msgs/dia (single-tenant) |
| `MIN_SEND_INTERVAL_SECONDS` | `60` | `60` | `30` | `15` | `10` | Intervalo mínimo entre envios |
| `WORKER_POLL_INTERVAL_SECONDS` | `60` | `60` | `30` | `15` | `10` | Frequência do worker de outbox |
| `HUMAN_APPROVAL_REQUIRED` | `false` | `false` | `true` | `false` | `false` | Exige aprovação no dashboard |
| `AUTO_REPLY_KB_ONLY` | `false` | `false` | `false` | `true` | `true` | IA só responde se vier da KB |
| `FULL_AUTONOMY` | `false` | `false` | `false` | `false` | `true` | Habilita qualify_and_schedule |
| `EVOLUTION_API_URL` | `http://localhost:8080` | `https://evolution.prod` | `https://evolution.prod` | `https://evolution.prod` | `https://evolution.prod` | Endpoint Evolution |
| `WEBHOOK_SECRET` | `dev-secret` | `***` | `***` | `***` | `***` | HMAC webhook (rotacionar por estágio) |

> **Nota**: Valores `***` = segredos injetados via cofre (Vault/SealedSecrets/GitOps). **Nunca** em `.env` versionado.

### 2.2 Arquivos `.env.stageN` (Exemplos para Referência)

#### `.env.stage0` — Dry-run Produção
```bash
# ESTÁGIO 0 — DRY-RUN EM PRODUÇÃO
DRY_RUN=true
AUTOMATION_ENABLED=false
KILL_SWITCH=false
CADENCE_GLOBAL_PAUSE=false
DAILY_SEND_CAP=0
MIN_SEND_INTERVAL_SECONDS=60
WORKER_POLL_INTERVAL_SECONDS=60
HUMAN_APPROVAL_REQUIRED=false
AUTO_REPLY_KB_ONLY=false
FULL_AUTONOMY=false
EVOLUTION_API_URL=http://localhost:8080
WEBHOOK_SECRET=dev-secret-dryrun
```

#### `.env.stage1` — Teste Interno
```bash
# ESTÁGIO 1 — TESTE INTERNO (WHITELIST)
DRY_RUN=false
AUTOMATION_ENABLED=true
KILL_SWITCH=false
CADENCE_GLOBAL_PAUSE=false
DAILY_SEND_CAP=20
MIN_SEND_INTERVAL_SECONDS=60
WORKER_POLL_INTERVAL_SECONDS=60
HUMAN_APPROVAL_REQUIRED=false
AUTO_REPLY_KB_ONLY=false
FULL_AUTONOMY=false
EVOLUTION_API_URL=https://evolution.prod
WEBHOOK_SECRET=${VAULT:stage1/webhook_secret}
```

#### `.env.stage2` — Modo Assistido
```bash
# ESTÁGIO 2 — MODO ASSISTIDO (HUMAN-IN-THE-LOOP)
DRY_RUN=false
AUTOMATION_ENABLED=true
KILL_SWITCH=false
CADENCE_GLOBAL_PAUSE=false
DAILY_SEND_CAP=50
MIN_SEND_INTERVAL_SECONDS=30
WORKER_POLL_INTERVAL_SECONDS=30
HUMAN_APPROVAL_REQUIRED=true
AUTO_REPLY_KB_ONLY=false
FULL_AUTONOMY=false
EVOLUTION_API_URL=https://evolution.prod
WEBHOOK_SECRET=${VAULT:stage2/webhook_secret}
```

#### `.env.stage3` — Semi-Autônomo
```bash
# ESTÁGIO 3 — SEMI-AUTÔNOMO (KB ONLY AUTO-REPLY)
DRY_RUN=false
AUTOMATION_ENABLED=true
KILL_SWITCH=false
CADENCE_GLOBAL_PAUSE=false
DAILY_SEND_CAP=200
MIN_SEND_INTERVAL_SECONDS=15
WORKER_POLL_INTERVAL_SECONDS=15
HUMAN_APPROVAL_REQUIRED=false
AUTO_REPLY_KB_ONLY=true
FULL_AUTONOMY=false
EVOLUTION_API_URL=https://evolution.prod
WEBHOOK_SECRET=${VAULT:stage3/webhook_secret}
```

#### `.env.stage4` — Autônomo Completo
```bash
# ESTÁGIO 4 — AUTÔNOMO COMPLETO
DRY_RUN=false
AUTOMATION_ENABLED=true
KILL_SWITCH=false
CADENCE_GLOBAL_PAUSE=false
DAILY_SEND_CAP=1000
MIN_SEND_INTERVAL_SECONDS=10
WORKER_POLL_INTERVAL_SECONDS=10
HUMAN_APPROVAL_REQUIRED=false
AUTO_REPLY_KB_ONLY=true
FULL_AUTONOMY=true
EVOLUTION_API_URL=https://evolution.prod
WEBHOOK_SECRET=${VAULT:stage4/webhook_secret}
```
---

## 3. Critérios de Promoção (Gate Criteria)

### 3.1 Transição 0 → 1 (Dry-run → Interno)

| Critério | Métrica/Validação | Threshold | Evidência |
|----------|-------------------|-----------|-----------|
| **Pipeline íntegro** | `pytest tests/integration -q` | 100% verde | Log CI/CD |
| **Zero erros críticos** | Logs `ERROR`/`CRITICAL` no dispatcher/outbox | 0 em 7 dias | Grafana Loki / CloudWatch |
| **Latência P95** | `outbox_dispatch_duration_seconds` | < 2 s | Prometheus |
| **Revisão de amostra** | 50 mensagens simuladas inspecionadas manualmente | 100% payload válido | Checklist assinado |
| **Health checks** | `/health` + `/ready` | 100% OK 24/7 | Uptime monitor |
| **Aprovação** | Tech Lead + Eng. Plantão | Assinatura digital | Git commit signed-off |

### 3.2 Transição 1 → 2 (Interno → Assistido)

| Critério | Métrica/Validação | Threshold | Evidência |
|----------|-------------------|-----------|-----------|
| **Ida e volta** | Mensagens enviadas → status `delivered`/`read` | 100% em 5 min | Evolution webhook logs |
| **Opt-out funcional** | `STOP` recebido → `suppression_list` + cadência pausada | 100% em < 30 s | DB query + log |
| **Handoff humano** | Takeover via dashboard → `conversation.locked_by_operator` | 100% em < 10 s | Dashboard audit log |
| **Agendamento** | `MeetingBooked` event → Google Calendar/Cal.com confirmado | 100% | Integração testada |
| **Zero banimentos** | `evolution_banned_instances` | 0 | Prometheus alert |
| **Volume** | Mín. 100 msgs enviadas (internas) | ≥ 100 | Outbox `sent` count |
| **Aprovação** | Tech Lead + Eng. Plantão | Assinatura | Git commit signed-off |

### 3.3 Transição 2 → 3 (Assistido → Semi-Autônomo)

| Critério | Métrica/Validação | Threshold | Evidência |
|----------|-------------------|-----------|-----------|
| **Taxa de aprovação** | Mensagens aprovadas / sugeridas | > 90% | Dashboard metric |
| **Tempo médio aprovação** | `human_approval_latency_seconds` | < 30 s (P95) | Prometheus |
| **Zero alucinação preço** | Validação `PostAiValidator` em respostas KB | 0 falsos positivos em 500 msgs | Evaluation suite |
| **Handoff rate** | % conversas escaladas para humano | < 30% | Dashboard |
| **Opt-out rate** | Opt-outs / total enviados | < 2% | DB metric |
| **Aprovação** | PO + Tech Lead | Assinatura | Git commit signed-off |

### 3.4 Transição 3 → 4 (Semi-Autônomo → Autônomo)

| Critério | Métrica/Validação | Threshold | Evidência |
|----------|-------------------|-----------|-----------|
| **Qualificação precisa** | `qualify_and_schedule` → `QUALIFIED` confirmado por humano (amostragem) | > 95% precisão | Auditoria manual 100 casos |
| **Agendamento sem conflito** | `ScheduleMeetingCommand` → zero double-booking | 0 em 14 dias | Calendar audit |
| **Respeito a tetos** | `DAILY_SEND_CAP` nunca estourado | 0 violações | Prometheus alert |
| **Janelas e pausas** | Envios fora de janela / com `CADENCE_GLOBAL_PAUSE` | 0 | Logs dispatcher |
| **Consentimento** | 100% msgs com `legal_basis` válido | 100% | DB constraint + audit |
| **Carga** | 3x volume projetado em teste de caos | Estável | Relatório F8-05 |
| **Aprovação** | PO + Tech Lead + Legal (LGPD) | Assinatura tripartite | Documento assinado |

---

## 4. Procedimento de Promoção (Passo a Passo)

> **Executar na ordem exata**. Qualquer falha → **parar, investigar, não prosseguir**.

### Checklist Genérico (Aplicável a Toda Promoção)

```markdown
## Promoção Estágio N → N+1 — Checklist de Execução

### Pré-requisitos
- [ ] Critérios da Seção 3 validados e assinados
- [ ] Janela de manutenção acordada (baixo tráfego)
- [ ] Rollback plan revisado (Seção 5)
- [ ] On-call notificado (Slack/Teams @oncall)

### Execução
- [ ] 1. Atualizar variáveis no orquestrador (K8s ConfigMap / .env / Vault)
      - Aplicar `.env.stage{N+1}` correspondente
- [ ] 2. Reiniciar serviços afetados (ordem: worker → api → dashboard)
      - `kubectl rollout restart deployment/vendas-worker`
      - `kubectl rollout restart deployment/vendas-api`
      - `kubectl rollout restart deployment/vendas-dashboard`
- [ ] 3. Aguardar health checks (`/health`, `/ready`) — **máx. 2 min**
- [ ] 4. Validar flags ativas via endpoint `/config` (apenas admin)
- [ ] 5. Enviar mensagem de teste controlada (número interno)
- [ ] 6. Confirmar processamento no outbox (status `sent`)
- [ ] 7. Monitorar métricas críticas por **30 minutos contínuos**:
      - `outbox_dispatch_errors_total` = 0
      - `evolution_banned_instances` = 0
      - `daily_send_count` ≤ `DAILY_SEND_CAP * 0.8`
      - `human_approval_queue_size` (se Estágio 2) estável
- [ ] 8. Registrar promoção no **Audit Log** (tabela `rollout_audit`):
      - `stage_from`, `stage_to`, `changed_by`, `timestamp`, `git_sha`, `approval_refs`
- [ ] 9. Comunicar no canal de operações: "✅ Promovido para Estágio N+1 — monitoramento ativo"

### Pós-Promoção (Primeiras 2h)
- [ ] Dashboard operacional verificado a cada 15 min
- [ ] Alertas de regressão (Seção 5) confirmados ativos
- [ ] On-call de plantão ciente do novo estágio
```
---

## 5. Gatilhos de Regressão Automática (Rollback Triggers)

> **Regra**: Qualquer gatilho abaixo dispara **regressão imediata para Estágio 0** (`DRY_RUN=true`, `AUTOMATION_ENABLED=false`, `KILL_SWITCH=true`) sem intervenção humana.

| # | Gatilho | Detecção | Ação Automática | SLA | Responsável Pós-Ação |
|---|---------|----------|-----------------|-----|----------------------|
| **R1** | **Taxa de erro de envio > 5% em 5 min** | `rate(outbox_dispatch_errors_total[5m]) / rate(outbox_dispatched_total[5m]) > 0.05` | `KILL_SWITCH=true` + alerta P1 | < 30 s | Eng. Plantão (investigar em 15 min) |
| **R2** | **Número banido detectado** | Webhook `instance.status: banned` OU métrica `evolution_banned_instances > 0` | `KILL_SWITCH=true` + `DRY_RUN=true` | < 10 s | Eng. Plantão + Runbook `numero-banido.md` |
| **R3** | **Pico de opt-out > 10% em 1h** | `opt_out_count_1h / messages_sent_1h > 0.10` | `CADENCE_GLOBAL_PAUSE=true` + alerta | < 60 s | PO + Legal (revisar base legal) |
| **R4** | **DAILY_SEND_CAP estourado** | `daily_send_count > DAILY_SEND_CAP` | `CADENCE_GLOBAL_PAUSE=true` + alerta | < 30 s | Eng. Plantão (revisar teto) |
| **R5** | **PII leak em logs/mensagens** | Detecção regex PII (CPF, CNPJ, email, telefone) em `outbox.payload` ou logs | `KILL_SWITCH=true` + `DRY_RUN=true` + incidente LGPD | < 10 s | DPO + Eng. Plantão (incidente P0) |
| **R6** | **Desconexão Evolution > 3x em 10 min** | `evolution_connection_lost_total` increase > 3 | `KILL_SWITCH=true` + alerta | < 60 s | Eng. Plantão + Runbook `sessao-caiu.md` |
| **R7** | **Alucinação de preço detectada** | `PostAiValidator` flag `price_hallucination=true` em msg enviada | `AUTO_REPLY_KB_ONLY=true` + `HUMAN_APPROVAL_REQUIRED=true` + alerta | < 30 s | Tech Lead (revisar KB + prompts) |
| **R8** | **Double booking em agendamento** | `MeetingBooked` com mesmo slot/recurso | `FULL_AUTONOMY=false` + `CADENCE_GLOBAL_PAUSE=true` | < 60 s | Eng. Plantão + Runbook agendamento |

### 5.1 Implementação Técnica dos Gatilhos

- **PrometheusRule** (Kubernetes) ou **Grafana Alerting** para R1, R3, R4, R6
- **Webhook Handler** na API (`/webhook/evolution`) executa R2, R7 inline (síncrono, < 100 ms)
- **Outbox Dispatcher** verifica R4, R8 antes de cada `send`
- **Log Shipper** (Vector/FluentBit) com regex PII → alerta R5 via Loki ruler

> **Importante**: Regressão automática **não requer aprovação**. Ação é **imediata e irreversível** até investigação humana.
---

## 6. Runbook por Estágio (Detalhado)

### 6.1 Estágio 0 — Dry-run em Produção

**Objetivo**: Validar pipeline completo em produção com tráfego real, sem enviar mensagens.

#### Validações Diárias (Checklist)
- [ ] Worker de ingestão roda a cada 5 min (`WORKER_INGEST_INTERVAL_SECONDS=300`)
- [ ] Leads entram como `NEW` → elegibilidade → `ENROLLED` ou `REJECTED` (com motivo)
- [ ] Cadência cria `outbox` entries com `status=pending` (não `sending`)
- [ ] Dispatcher lê `pending`, loga `[DRY_RUN] Would send to <phone>`, marca `sent` (simulado)
- [ ] Zero chamadas HTTP para `EVOLUTION_API_URL` (verificar access logs)
- [ ] Métricas `outbox_dispatched_total{stage="0"}` incrementando
- [ ] Health checks `/health` `/ready` 200 OK

#### Testes de Fumaça (Executar Diariamente)
```bash
# 1. Ingestão de lead sintético
curl -X POST https://api.prod/leads/ingest \
  -H "Authorization: Bearer $API_ADMIN_TOKEN" \
  -d '{"cnpj":"12345678000195","phone":"+5511999999999","source":"test"}'

# 2. Verificar outbox
psql -c "SELECT * FROM outbox WHERE correlation_id LIKE 'test-%' ORDER BY created_at DESC LIMIT 5;"

# 3. Verificar logs dispatcher (deve conter [DRY_RUN])
kubectl logs -l app=vendas-worker -c dispatcher | grep "DRY_RUN" | tail -20
```

#### Números de Controle
- Nenhum (apenas logs)

#### Dashboard a Observar
- **Grafana**: `Vendas / Outbox Dry-run` (painel dedicado)
- **Loki**: Query `{app="vendas-worker"} |= "DRY_RUN"`

---

### 6.2 Estágio 1 — Teste Interno (Whitelist)

**Objetivo**: Provar ida/volta real, opt-out, handoff e agendamento com números da equipe.

#### Pré-requisitos
- Lista de **máx. 5 números internos** cadastrados em `internal_whitelist` (tabela `phone_numbers` com `is_internal=true`)
- `DAILY_SEND_CAP=20` aplicado

#### Validações por Funcionalidade

| Funcionalidade | Teste | Critério de Sucesso |
|----------------|-------|---------------------|
| **Envio WhatsApp** | Disparar cadência para 3 números internos | Status `delivered` em < 30 s (webhook) |
| **Resposta inbound** | Responder "Oi" de um número | `inbound_events` gravado, sessão aberta |
| **Opt-out** | Enviar "STOP" / "SAIR" | `suppression_list` inserido + cadência pausada em < 30 s |
| **Handoff** | Operador clica "Assumir" no dashboard | `conversation.locked_by_operator` = user_id |
| **Agendamento** | IA sugere horário → operador aprova → `MeetingBooked` | Evento no Calendar confirmado |

#### Checklist de Encerramento (5 dias)
- [ ] Mín. 100 mensagens enviadas (internas)
- [ ] 0 banimentos (`evolution_banned_instances = 0`)
- [ ] 100% opt-outs processados corretamente
- [ ] 100% handoffs funcionais
---

### 6.3 Estágio 2 — Modo Assistido (Human-in-the-Loop)

**Objetivo**: IA sugere, operador aprova. Leads reais, volume controlado.

#### Configuração Específica
- `HUMAN_APPROVAL_REQUIRED=true` → dispatcher **não envia**; cria `outbox` com `status=awaiting_approval`
- Dashboard exibe fila "Aguardando Aprovação" com preview da mensagem
- Operador clica **Aprovar** → `status=pending` → dispatcher envia
- Operador clica **Rejeitar/Editar** → abre modal de edição → reenvia para aprovação

#### Métricas Críticas
| Métrica | Target | Alerta Se |
|---------|--------|-----------|
| `human_approval_queue_size` | < 20 | > 50 por 10 min |
| `human_approval_latency_seconds` (P95) | < 30 s | > 60 s |
| `approval_rate` | > 90% | < 80% |

#### Validações Diárias
- [ ] Fila de aprovação não acumula (worker processa em < 5 min)
- [ ] Edições do operador são auditadas (`outbox.payload` versionado)
- [ ] Zero envios sem aprovação (query: `status=sent AND approval_id IS NULL` = 0)
- [ ] Leads reais processados: 10–20/dia

#### Critério de Promoção (7 dias)
- Taxa de aprovação > 90% consistentemente
- Tempo médio aprovação < 30 s
- Zero reclamações de lead sobre tom/qualidade
- Assinatura: PO + Tech Lead

---

### 6.4 Estágio 3 — Semi-Autônomo (KB Only Auto-Reply)

**Objetivo**: IA responde **apenas** quando a resposta vem da Knowledge Base (preço, serviço, FAQ). Demais → handoff.

#### Configuração Específica
- `AUTO_REPLY_KB_ONLY=true` → `InboundCommand`:
  1. Chama `KnowledgeBase.query(pergunta)`
  2. Se `confidence > 0.9` E `source == "KB"` → responde automaticamente
  3. Caso contrário → `handoff_reason="kb_no_match"` → fila de operador
- `DAILY_SEND_CAP=200`

#### Validações Contínuas
- [ ] **Zero alucinação de preço**: `PostAiValidator` roda em 100% respostas auto
- [ ] Taxa de handoff < 30% (meta: KB cobre 70%+ das FAQs)
- [ ] Tempo de resposta auto < 3 s (P95)
- [ ] Auditoria semanal: amostra 50 respostas auto → 100% factualmente corretas

#### Gatilhos Específicos deste Estágio
- **R7** (alucinação preço) → regressão imediata para Estágio 2 (`HUMAN_APPROVAL_REQUIRED=true`)

#### Critério de Promoção (14 dias)
- 0 alucinações de preço em 14 dias
- Cobertura KB > 70% (handoff rate < 30%)
- Precisão qualificação (amostragem) > 95%
- Assinatura: PO + Tech Lead

---

### 6.5 Estágio 4 — Autônomo Completo

**Objetivo**: `qualify_and_schedule` ativo com todas as guardas (tetos, janelas, pausas, consentimento).

#### Configuração Específica
- `FULL_AUTONOMY=true` → habilita:
  - `QualifyLeadCommand` automático pós-conversa
  - `ScheduleMeetingCommand` com verificação de conflitos
  - Respeito a `CADENCE_GLOBAL_PAUSE`, `KILL_SWITCH`, janelas de envio
  - `DAILY_SEND_CAP=1000` (configurável por ICP tier)

#### Guardas Ativas (Sempre)
| Guarda | Implementação | Local |
|--------|---------------|-------|
| Teto diário | `DailySendCapPolicy` no dispatcher | `domain/policies/send_cap.py` |
| Janela de envio | `SendingWindowPolicy` (ex.: 08h–18h BRT) | `domain/policies/sending_window.py` |
| Pausa global | `CADENCE_GLOBAL_PAUSE` lido a cada batch | Dispatcher loop |
| Kill switch | `KILL_SWITCH` lido a cada mensagem | Dispatcher + API middleware |
| Consentimento | `LegalBasisPolicy` valida `suppression_list` + `legal_basis` | `EnrollInCadenceCommand` |
| Double booking | `CalendarAdapter.free_slots` + lock otimista | `ScheduleMeetingCommand` |

#### Monitoramento Permanente (Dashboards)
- **Grafana**: `Vendas / Autonomous Mode` (painel dedicado)
  - `qualification_accuracy` (amostragem humana semanal)
  - `meeting_no_show_rate`
  - `opt_out_rate` (meta < 1%)
  - `daily_send_utilization` (`sent / DAILY_SEND_CAP`)
  - `hallucination_alerts_total` (deve ser 0)

---

## 7. Procedimento de Emergência (Kill Switch Total)

> **Use quando**: Qualquer gatilho da Seção 5 disparar **OU** decisão humana de parar tudo.

### Checklist de Ativação Imediata (< 2 minutos)

```markdown
## KILL SWITCH TOTAL — ATIVAÇÃO DE EMERGÊNCIA

### Ação Imediata (Executar em Ordem)
- [ ] 1. Definir variáveis (via orquestrador / kubectl / .env):
      - `KILL_SWITCH=true`
      - `DRY_RUN=true`
      - `AUTOMATION_ENABLED=false`
      - `CADENCE_GLOBAL_PAUSE=true`
- [ ] 2. Reiniciar worker + api (propaga flags em < 30 s):
      `kubectl rollout restart deployment/vendas-worker deployment/vendas-api`
- [ ] 3. Confirmar nos logs (grep nos 2 pods):
      `[KILL_SWITCH] Envio bloqueado`
      `[DRY_RUN] Modo simulação ativo`
- [ ] 4. Notificar canal de operações:
      `@oncall 🚨 KILL SWITCH ATIVADO — Estágio atual: N — Motivo: <R1-R8 ou decisão humana>`
- [ ] 5. Criar incidente P0 no tracker (Jira/Linear/GitHub Issues)
      - Título: `[P0] Kill Switch Ativado — Rollout Estágio N`
      - Campos: gatilho, horário, responsável, logs relevantes
- [ ] 6. Comunicar stakeholders (PO, Legal se LGPD, liderança)
```

### Pós-Ativação (Investigação)
- [ ] Analisar causa raiz (logs, métricas, webhook Evolution)
- [ ] Corrigir / mitigar (ex.: trocar número banido, ajustar KB, corrigir bug)
- [ ] Validar correção em **Staging** (suite completa + teste de fumaça)
- [ ] **Somente após correção validada**: Reverter para Estágio 0 e reiniciar promoção controlada
- [ ] Documentar no `rollout_audit` e no incidente

---

## 8. Auditoria e Rastreabilidade

### 8.1 Tabela `rollout_audit` (Criar via Migration)

```sql
CREATE TABLE rollout_audit (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_from      SMALLINT NOT NULL,  -- 0-4
    stage_to        SMALLINT NOT NULL,  -- 0-4
    changed_by      VARCHAR(255) NOT NULL,  -- user/email/ci-bot
    git_sha         VARCHAR(40) NOT NULL,   -- commit da promoção
    approval_refs   JSONB NOT NULL,         -- [{role, user, timestamp, signature}]
    trigger         VARCHAR(50),            -- 'promotion' | 'rollback_auto_R1' | 'rollback_manual'
    reason          TEXT,                   -- descrição livre
    env_snapshot    JSONB NOT NULL,         -- snapshot das vars relevantes
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rollout_audit_created_at ON rollout_audit(created_at DESC);
CREATE INDEX idx_rollout_audit_trigger ON rollout_audit(trigger);
```

### 8.2 Campos de Correlação (Obrigatórios em Todos Logs)
- `correlation_id` (UUID v4) — propagado: API → Worker → Outbox → Evolution Webhook → Dashboard
- `rollout_stage` — estágio ativo no momento do log (injetado via middleware)

### 8.3 Retenção
- `rollout_audit`: **90 dias** (política de retenção via pg_partman ou job cron)
- Logs estruturados (Loki/CloudWatch): **30 dias** quente, **1 ano** frio (S3/Glacier)
- Métricas Prometheus: **15 dias** alta resolução, **1 ano** downsampled

---

## 9. Referências Rápidas

| Recurso | Link / Comando |
|---------|----------------|
| **Painel Evolution (Prod)** | `https://evolution.prod.seudominio.com/admin` |
| **Grafana — Rollout Overview** | `https://grafana.seudominio.com/d/vendas-rollout` |
| **Grafana — Outbox / DLQ** | `https://grafana.seudominio.com/d/vendas-outbox` |
| **Grafana — Autonomous Mode (Estágio 4)** | `https://grafana.seudominio.com/d/vendas-autonomous` |
| **Loki — Logs Dispatcher** | `{app="vendas-worker", container="dispatcher"}` |
| **Cofre de Segredos (Vault)** | `vault/secrets/vendas/rollout/{stage0..stage4}` |
| **Canal de Operações** | `#ops-alertas` (Slack) / `Operações - Alertas` (Teams) |
| **On-call Atual** | `https://ops.seudominio.com/oncall` |
| **ADR-001** | Arquitetura Hexagonal (`docs/architecture.md`) |
| **ADR-007** | Outbox Pattern + Dispatcher (`docs/adr/007-outbox-pattern.md`) |
| **ADR-012** | Kill Switch Global (`docs/adr/012-kill-switch.md`) |
| **Runbook: Sessão Caída** | `docs/runbooks/sessao-caiu.md` |
| **Runbook: Número Banido** | `docs/runbooks/numero-banido.md` |
| **Runbook: DLQ Cheia** | `docs/runbooks/dlq-cheia.md` |
| **Runbook: Backup/Restore** | `docs/runbooks/backup-restore.md` |
| **Política de Supressão/Opt-out** | `docs/policies/suppression-policy.md` |
| **Knowledge Base (KB)** | `src/vendas/domain/knowledge_base/` + `docs/kb/` |

---

## Histórico de Versões

| Versão | Data | Autor | Mudança |
|--------|------|-------|---------|
| 1.0 | 29/10/2026 | Tech Lead | Criação inicial — Fase F9 Tarefa F9-01 |

---

**Fim do Documento**  
*Este runbook deve ser revisado a cada promoção de estágio e trimestralmente. Qualquer alteração requer aprovação de Tech Lead + Eng. Plantão.*