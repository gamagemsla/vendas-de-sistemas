---
name: verify-quality-gates
description: Use esta skill sempre que precisar rodar testes, verificar tipos com mypy, rodar ruff ou validar a conformidade com o make check antes de finalizar uma tarefa.
---

## Procedimento de Verificação de Qualidade (make check)

Sempre execute a verificação nesta sequência exata:
1. `ruff check src tests` -> Se houver erros, corrija sem suprimir regras.
2. `mypy src` -> Deve ter 0 erros em modo strict. NUNCA use `# type: ignore` sem autorização prévia.
3. `lint-imports` -> As 4 regras devem passar legitimamente (sem truques de importação dinâmica como `importlib`).
4. `pytest tests` -> Todos os testes devem passar (128+ testes). Proibido usar `@pytest.mark.skip`.

Critério de Aceite:
A tarefa só é considerada concluída se todas as 4 etapas acima retornarem código de saída 0 (sucesso).