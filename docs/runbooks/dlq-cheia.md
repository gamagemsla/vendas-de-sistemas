# Runbook: DLQ Cheia (Dead‑Letter Queue da Outbox)

**Objetivo**: Identificar, classificar e tratar mensagens que caíram na *dead‑letter queue* da tabela `outbox`, evitando perda de dados e restaurando o fluxo normal de envio.

---

## 1. Detecção da DLQ Cheia
- [ ] Alerta de monitoramento: métrica `outbox_dead_letter_count > THRESHOLD` (ex.: 100 mensagens).
- [ ] Dashboard mostra crescimento contínuo da contagem de `status = 'dead_letter'`.
- [ ] Operador recebe notificação no canal de operações.

## 2. Inspeção das Mensagens na Outbox
- [ ] Conectar ao banco de dados (SQLite em testes / PostgreSQL em produção) com usuário de leitura.
- [ ] Executar query de inspeção:

```sql
SELECT id, correlation_id, payload, error_msg, attempts, created_at, updated_at
FROM outbox
WHERE status = 'dead_letter'
ORDER BY created_at DESC
LIMIT 50;
```

- [ ] Exportar resultado para CSV/planilha para análise conjunta.

## 3. Classificação das Falhas
| Categoria | Critério | Ação Padrão |
|-----------|----------|-------------|
| **Retryable** | Erros transitórios: `timeout`, `connection_reset`, `rate_limit`, `temporary_unavailable` | Re‑enfileirar (ver passo 4). |
| **Non‑retryable** | Erros definitivos: `invalid_payload`, `number_not_exists`, `blocked_by_user`, `banned_number` | Mover para auditoria / descartar (ver passo 5). |
| **Desconhecido** | Mensagem de erro genérica ou vazia | Investigar manualmente; decidir caso a caso. |

## 4. Re‑enfileiramento (Retryable)
Para cada mensagem classificada como **retryable**:

1. Atualizar a linha na tabela `outbox`:

```sql
UPDATE outbox
SET status = 'pending',
    attempts = 0,
    error_msg = NULL,
    updated_at = NOW()
WHERE id = '<ID_DA_MENSAGEM>';
```

> **Nota**: Resetar `attempts` para **0** garante que a política de retentativa (ex.: max 3 tentativas) seja reaplicada do início.

2. Confirmar que o worker de outbox (processo `outbox-dispatcher`) pegou a mensagem (logs mostram `Processing message <id>`).

## 5. Descarte / Auditoria (Non‑retryable)
Para cada mensagem **non‑retryable**:

1. Inserir registro na tabela de auditoria (ex.: `outbox_audit`):

```sql
INSERT INTO outbox_audit (original_id, correlation_id, payload, error_msg, attempts, created_at, resolved_at, resolution)
VALUES (<id>, <correlation_id>, <payload>, <error_msg>, <attempts>, <created_at>, NOW(), 'discarded_non_retryable');
```

2. Remover da `outbox` (ou marcar como `archived` se a política exigir retenção):

```sql
DELETE FROM outbox WHERE id = '<ID_DA_MENSAGEM>';
-- OU
UPDATE outbox SET status = 'archived' WHERE id = '<ID_DA_MENSAGEM>';
```

3. Registrar justificativa no ticket/incidente.

## 6. Limpeza e Verificação Pós‑Ação
- [ ] Executar novamente a query de contagem:

```sql
SELECT COUNT(*) FROM outbox WHERE status = 'dead_letter';
```

- [ ] Confirmar que a contagem caiu para **zero** ou para nível aceitável (< 10).
- [ ] Verificar métricas de `outbox_dead_letter_count` no monitoramento – deve retornar ao baseline.

## 7. Registro e Encerramento
- [ ] Atualizar ticket/incidente com:
  - Quantidade de mensagens inspecionadas.
  - Quantidade re‑enfileirada vs descartada.
  - Causa raiz identificada (ex.: pico de rate‑limit, bug no payload).
  - Ações preventivas propostas (ajuste de back‑off, validação de payload antes de enfileirar).
- [ ] Fechar alerta no monitoramento.
- [ ] Comunicar resumo no canal de operações.

---

## Referências Rápidas
- **Tabela principal**: `outbox` (colunas: `id`, `correlation_id`, `payload`, `status`, `attempts`, `error_msg`, `created_at`, `updated_at`).
- **Status relevantes**: `pending`, `sending`, `sent`, `failed`, `dead_letter`, `archived`.
- **Tabela de auditoria**: `outbox_audit`.
- **Worker de dispatch**: serviço `outbox-dispatcher` (systemd / k8s deployment).
- **Monitoramento**: Grafana dashboard `Outbox / DLQ`.
- **Canal de operações**: `#ops-alertas` (Slack) / `Operações - Alertas` (Teams).