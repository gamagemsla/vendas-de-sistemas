# Protocolo Permanente do Agente (AGENTS.md)

1. Ler AGENTS.md e docs/architecture.md no início de toda sessão. Não alterar a arquitetura sem ADR aprovado.
2. Respeitar as camadas: import-linter deve passar; domain sem dependências externas; interfaces nunca importam infrastructure; composição só em bootstrap/container.py.
3. Testes primeiro para domínio e casos de uso, com fakes dos ports. Sem rede nos testes unitários. Hora sempre pelo port Clock.
4. Toda chamada externa passa por um port, com timeout e retry limitado. Nenhuma chamada de rede dentro de transação aberta.
5. Todo envio de mensagem passa pela outbox e pelas checagens de supressão, consentimento, janela, teto e estado do canal. Nenhum caso de uso chama a Evolution diretamente.
6. Migrations só por Alembic, reversíveis. Nunca editar migration já aplicada.
7. Segredos nunca em código, log, teste ou commit. .env.example só com nomes.
8. Dados pessoais mascarados nos logs. Fixtures só com dados sintéticos.
9. DRY_RUN=true é o padrão em todos os ambientes. Nada envia mensagem real sem AUTOMATION_ENABLED=true e DRY_RUN=false.
10. Preço e condição comercial vêm só da base de conhecimento. Nunca no prompt nem no código.
11. Tarefa pequena: passou de uns 400 linhas de diff líquido, dividir e avisar.
12. Ao terminar: make check verde (lint, tipos, import-linter, testes), docs e CHANGELOG atualizados, lista de pendências e dúvidas. Depois parar.
13. Nunca desativar teste, regra do linter ou verificação de segurança para passar. Reportar o bloqueio.
14. Nova dependência exige uma linha de justificativa no PR e versão fixada.