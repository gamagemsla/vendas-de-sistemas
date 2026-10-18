---
name: hexagonal-boundary-guard
description: Use esta skill ao refatorar dependências, criar portas, injetar dependências ou quando houver violação entre as camadas domain, application, interfaces e infrastructure.
---

# Diretrizes de Refatoração Hexagonal

Ao conectar componentes entre camadas:
1. Interfaces (API/CLI/Streamlit) NUNCA importam de `src/vendas/infrastructure`.
   - Injeções em rotas FastAPI devem usar `Annotated[Port, Depends(get_port_provider)]`.
2. Application (Commands/Queries/Use Cases) NUNCA importa `infrastructure` nem SQLAlchemy `Session`.
   - Defina uma interface abstrata (Port) em `domain/ports` ou dentro de `application`.
   - Receba a porta via `__init__` do caso de uso.
3. Bootstrap (`src/vendas/bootstrap/container.py`):
   - É o ÚNICO local permitido para instanciar repositórios concretos da infraestrutura e passá-los para os casos de uso.
4. NUNCA use `importlib` ou reflexão para contornar o linter. A dependência deve ser explicitamente injetada.