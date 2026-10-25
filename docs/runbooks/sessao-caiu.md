# Runbook: Sessão Caída (Evolution API)

**Objetivo**: Restaurar a sessão WhatsApp da Evolution API quando a conexão cair, garantindo que o envio de mensagens volte a funcionar o mais rápido possível.

---

## 1. Detecção do Incidente
- [ ] Alerta de monitoramento (ex.: Prometheus/Grafana) indica *health‑check* falhando para a instância Evolution.
- [ ] Logs da aplicação mostram erros de `QR_CODE_EXPIRED` ou `CONNECTION_LOST`.
- [ ] Equipe de suporte relata falha no envio de mensagens.

## 2. Notificação Imediata
- [ ] Postar aviso no canal de operações (Slack/Teams) com tag `@oncall`.
- [ ] Incluir: nome da instância, horário do alerta, link para o painel da Evolution.

## 3. Acesso ao Painel da Evolution
- [ ] Abrir URL do painel administrativo da Evolution (ex.: `https://evolution.seudominio.com/admin`).
- [ ] Autenticar com credenciais de operador (armazenadas no cofre de segredos).

## 4. Releitura do QR Code
- [ ] No painel, localizar a instância afetada.
- [ ] Clicar em **"Reconectar"** ou **"Gerar QR Code"**.
- [ ] Escanear o QR Code com o WhatsApp do número vinculado (celular do operador ou dispositivo dedicado).
- [ ] Confirmar que o status muda para **Conectado**.

## 5. Validação da Reconexão
- [ ] Enviar uma mensagem de teste para um número de controle (ex.: `+55 11 99999-9999`).
- [ ] Verificar no painel se a mensagem aparece como **Enviada/Entregue**.
- [ ] Confirmar nos logs da aplicação que o webhook de status (`message.sent`) foi recebido.

## 6. Registro e Encerramento
- [ ] Atualizar o ticket/incidente com: horário de início, horário de resolução, ações tomadas.
- [ ] Fechar alerta no monitoramento.
- [ ] Comunicar no canal de operações que a sessão foi restaurada.

---

## Referências Rápidas
- **Painel Evolution**: `https://evolution.seudominio.com/admin`
- **Cofre de segredos**: `vault/secrets/evolution-credentials`
- **Canal de operações**: `#ops-alertas` (Slack) / `Operações - Alertas` (Teams)