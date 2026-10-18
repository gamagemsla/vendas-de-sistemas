# Arquitetura v2 - Ecossistema de Prospecção B2B

## Estilo Arquitetural
Arquitetura hexagonal (ports e adapters) com casos de uso explícitos. A dependência sempre aponta para dentro.
- `interfaces` (api, dashboard, worker) chama `application` (casos de uso, queries) que depende de `domain` (entidades, políticas, ports), implementado por `infrastructure` (postgres, whatsapp, llm, etc.).
- `bootstrap` (settings, logging, container) é o único lugar que conhece tudo.

## Regras de Dependência (import-linter)
1. `domain` não importa nada de fora (nem ORM, nem HTTP, nem SDKs).
2. `application` só conhece `domain`. Nunca infrastructure ou interfaces.
3. `infrastructure` não conhece application nem interfaces.
4. `interfaces` não importam infrastructure diretamente.
5. `bootstrap` liga ports às implementações.

### Observações de composição
- As telas do dashboard acessam leitura por `application.queries` e um container de bootstrap que resolve o adaptador de infraestrutura em tempo de execução.
- Escritas de negócio continuam sendo encaminhadas para a API autenticada e para comandos de `application`, em vez de alcançar o banco diretamente na interface.