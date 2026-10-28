# Runbook: Backup e Restauração (PostgreSQL + Evolution API)

## Visão Geral

Este documento descreve os procedimentos de backup e restauração para os componentes persistentes do sistema:
- **PostgreSQL**: Banco de dados principal (volume `postgres_data`)
- **Evolution API**: Sessão Baileys/WhatsApp (volume `evolution_instances`)

## 1. Backup Diário (Automatizado)

### 1.1 PostgreSQL

```bash
#!/bin/bash
# backup-postgres.sh - Executar via cron diário (ex: 03:00 UTC)

set -euo pipefail

TIMESTAMP=$(date -u +"%Y-%m-%d_%H-%M")
BACKUP_DIR="/backups/postgres"
S3_BUCKET="s3://seu-bucket/backups/vendas-db"
CONTAINER_NAME="vendas_postgres"

mkdir -p "$BACKUP_DIR"

docker exec "$CONTAINER_NAME" pg_dump \
  -U postgres \
  -d vendas_db \
  --no-owner \
  --no-privileges \
  --format=custom \
  --file="/tmp/vendas_db_${TIMESTAMP}.dump"

docker cp "${CONTAINER_NAME}:/tmp/vendas_db_${TIMESTAMP}.dump" "${BACKUP_DIR}/"

aws s3 cp "${BACKUP_DIR}/vendas_db_${TIMESTAMP}.dump" "${S3_BUCKET}/vendas_db_${TIMESTAMP}.dump"

find "$BACKUP_DIR" -name "vendas_db_*.dump" -mtime +7 -delete

docker exec "$CONTAINER_NAME" rm -f "/tmp/vendas_db_${TIMESTAMP}.dump"

echo "Backup concluído: vendas_db_${TIMESTAMP}.dump"
```

**Agendamento sugerido (cron):**
```
0 3 * * * /opt/scripts/backup-postgres.sh >> /var/log/backup-postgres.log 2>&1
```

**Retenção:**
- Diário: 30 dias
- Semanal (domingos): 12 semanas
- Mensal (dia 1): 12 meses

### 1.2 Evolution API (Sessão Baileys)

```bash
#!/bin/bash
# backup-evolution.sh - Executar via cron diário (ex: 03:30 UTC)

set -euo pipefail

TIMESTAMP=$(date -u +"%Y-%m-%d_%H-%M")
BACKUP_DIR="/backups/evolution"
S3_BUCKET="s3://seu-bucket/backups/evolution-instances"
VOLUME_NAME="vendas_evolution_instances"

mkdir -p "$BACKUP_DIR"

docker run --rm \
  -v "${VOLUME_NAME}:/data" \
  -v "${BACKUP_DIR}:/backup" \
  alpine tar czf "/backup/evolution_instances_${TIMESTAMP}.tar.gz" -C /data .

aws s3 cp "${BACKUP_DIR}/evolution_instances_${TIMESTAMP}.tar.gz" "${S3_BUCKET}/evolution_instances_${TIMESTAMP}.tar.gz"

find "$BACKUP_DIR" -name "evolution_instances_*.tar.gz" -mtime +7 -delete

echo "Backup Evolution concluído: evolution_instances_${TIMESTAMP}.tar.gz"
```

**Agendamento sugerido (cron):**
```
30 3 * * * /opt/scripts/backup-evolution.sh >> /var/log/backup-evolution.log 2>&1
```

## 2. Restauração

### 2.1 PostgreSQL

```bash
#!/bin/bash
# restore-postgres.sh <arquivo_dump>

set -euo pipefail

DUMP_FILE="${1:-}"
CONTAINER_NAME="vendas_postgres"

if [[ -z "$DUMP_FILE" ]]; then
  echo "Uso: $0 <caminho_do_arquivo.dump>"
  exit 1
fi

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "Arquivo não encontrado: $DUMP_FILE"
  exit 1
fi

echo "⚠️  ATENÇÃO: Esta operação irá SUBSTITUIR o banco de dados atual."
read -p "Confirma restauração? (digite 'SIM' para confirmar): " CONFIRM
[[ "$CONFIRM" == "SIM" ]] || exit 1

docker compose stop api worker

docker cp "$DUMP_FILE" "${CONTAINER_NAME}:/tmp/restore.dump"

docker exec "$CONTAINER_NAME" pg_restore \
  -U postgres \
  -d vendas_db \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  "/tmp/restore.dump"

docker exec "$CONTAINER_NAME" rm -f "/tmp/restore.dump"

docker compose start api worker

sleep 5
curl -sf http://localhost:8000/health || echo "⚠️ Health check falhou"

echo "Restauração concluída. Execute 'alembic upgrade head' se houver migrações pendentes."
```

### 2.2 Evolution API

```bash
#!/bin/bash
# restore-evolution.sh <arquivo_tarball>

set -euo pipefail

TARBALL="${1:-}"
VOLUME_NAME="vendas_evolution_instances"

if [[ -z "$TARBALL" ]]; then
  echo "Uso: $0 <caminho_do_arquivo.tar.gz>"
  exit 1
fi

if [[ ! -f "$TARBALL" ]]; then
  echo "Arquivo não encontrado: $TARBALL"
  exit 1
fi

echo "⚠️  ATENÇÃO: Esta operação irá SUBSTITUIR a sessão Baileys atual."
read -p "Confirma restauração? (digite 'SIM' para confirmar): " CONFIRM
[[ "$CONFIRM" == "SIM" ]] || exit 1

docker compose stop evolution-api

docker run --rm \
  -v "${VOLUME_NAME}:/data" \
  -v "$(dirname "$TARBALL"):/backup" \
  alpine sh -c "rm -rf /data/* && tar xzf /backup/$(basename "$TARBALL") -C /data"

docker compose start evolution-api

sleep 10
curl -sf http://localhost:8080/health || echo "⚠️ Evolution health check falhou"

echo "Restauração Evolution concluída. Verifique se o QR Code ainda é válido."
```

## 3. Validação Pós-Restore

Após qualquer restauração, execute:

```bash
# 1. Testes de integração (banco íntegro)
pytest tests/integration -q

# 2. Health checks
curl -sf http://localhost:8000/health
curl -sf http://localhost:8000/ready

# 3. Teste de envio WhatsApp (se Evolution restaurado)
# Verifique se a instância está conectada via dashboard ou API

# 4. Migrações Alembic (se aplicável)
alembic upgrade head
```

## 4. Testes de Restore (Mensais)

**Obrigatório:** Testar restauração completa em ambiente de staging **mensalmente**.

Checklist de validação:
- [ ] Restore PostgreSQL em staging
- [ ] Restore Evolution API em staging
- [ ] `pytest tests/integration -q` passa
- [ ] Health checks OK
- [ ] Envio de mensagem de teste via WhatsApp funciona
- [ ] Dashboard carrega dados corretamente
- [ ] Documentar tempo de restore (RTO) e ponto de recuperação (RPO)

## 5. Métricas e Alertas

- **RPO (Recovery Point Objective)**: 24h (backup diário)
- **RTO (Recovery Time Objective)**: < 30 min (PostgreSQL), < 15 min (Evolution)
- **Alerta**: Falha no backup diário → alerta PagerDuty/Slack
- **Alerta**: Espaço em disco < 20% no volume de backups

## 6. Contatos de Emergência

- DBA: [contato]
- DevOps: [contato]
- Engenheiro de Plantão: [contato]