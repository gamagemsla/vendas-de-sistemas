.PHONY: install check test up migrate clean

install:
	pip install --upgrade pip
	pip install -e ".[dev]"

check:
	python -m compileall -q src tests
	ruff check src tests
	ruff format --check src tests
	mypy src
	lint-imports
	pytest

test:
	pytest --cov=src/vendas --cov-report=term-missing

up:
	docker compose up -d

migrate:
	alembic upgrade head

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".mypy_cache" -delete