# Runbook: Número Banido (WhatsApp / Evolution API)

**Objetivo**: Conter o impacto de um número banido pelo WhatsApp, trocar o número na configuração e colocar uma nova instância em operação com aquecimento adequado.

---

## 1. Detecção do Banimento
- [ ] Webhook da Evolution envia evento `instance.status: banned` ou `phone.banned`.
- [ ] Monitoramento alerta: métrica `evolution_banned_instances > 0`.
- [ ] Operador recebe notificação no canal de operações.

## 2. Ativação Imediata do Kill‑Switch
- [ ] Definir a variável de ambiente **`KILL_SWITCH=True`** na instância afetada (via `.env`, Kubernetes ConfigMap/Secret ou gerenciador de segredos).
- [ ] Reiniciar o serviço da aplicação para que a flag seja lida.
- [ ] Confirmar nos logs que o envio de novas mensagens foi interrompido (`[KILL_SWITCH] Envio bloqueado`).

> **Importante**: O kill‑switch deve ser ativado **antes** de qualquer tentativa de troca de número para estancar a "sangria" de mensagens que iriam para um número já banido.

## 3. Substituição do Número no Ambiente
- [ ] Obter novo número válido (com chip físico ou número virtual aprovado).
- [ ] Atualizar a variável `EVOLUTION_PHONE_NUMBER` (ou equivalente) no mesmo local onde `KILL_SWITCH` foi definido.
- [ ] Remover ou comentar a flag `KILL_SWITCH=True` **após** a nova instância estar pronta (ver passo 5).

## 4. Provisionamento de Nova Instância na Evolution
- [ ] No painel da Evolution, criar nova instância:
  - Nome sugerido: `vendas-<novo-número>-<timestamp>`.
  - Configurar webhook para `https://api.seudominio.com/webhook/evolution`.
  - Definir `auto_reconnect: true`.
- [ ] Gerar QR Code e escanear com o WhatsApp do novo número.
- [ ] Aguardar status **Conectado**.

## 5. Aquecimento (Warm‑up) da Nova Instância
- [ ] Enviar **mensagens de teste** para uma lista controlada (máx. 5 números internos) respeitando o limite de taxa (ex.: 1 msg/seg).
- [ ] Verificar entrega e leitura (ticks cinza/azul) no painel.
- [ ] Monitorar por 15 minutos para garantir ausência de erros `RATE_LIMIT` ou `BANNED`.

## 6. Reativação do Envio em Produção
- [ ] Remover `KILL_SWITCH=True` (ou definir `KILL_SWITCH=False`).
- [ ] Reiniciar o serviço da aplicação.
- [ ] Confirmar nos logs que o processamento da fila `outbox` retomou (`[WORKER] Processando mensagens pendentes`).

## 7. Atualização de Registros e Comunicação
- [ ] Atualizar a base de conhecimento / catálogo de números (planilha, CMDB ou tabela `phone_numbers`).
- [ ] Informar à equipe de vendas/suporte o novo número ativo.
- [ ] Registrar no ticket/incidente: horário do banimento, ações tomadas, novo número, tempo de indisponibilidade.

## 8. Encerramento
- [ ] Fechar alerta no monitoramento.
- [ ] Publicar resumo no canal de operações.

---

## Referências Rápidas
- **Variáveis de ambiente**: `KILL_SWITCH`, `EVOLUTION_PHONE_NUMBER`
- **Painel Evolution**: `https://evolution.seudominio.com/admin`
- **Cofre de segredos**: `vault/secrets/evolution-credentials`
- **Canal de operações**: `#ops-alertas` (Slack) / `Operações - Alertas` (Teams)