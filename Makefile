.PHONY: install sync lint format typecheck test test-cov clean db-init discover

install:
	uv sync

sync:
	uv sync --dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src/

test:
	uv run pytest -m "not live_api"

test-cov:
	uv run pytest --cov=src --cov-report=term-missing --cov-report=html -m "not live_api"

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

db-init:
	uv run rpat db-init

discover:
	uv run rpat discover --profile dtp-pmsm --days 14

pre-commit-install:
	uv run pre-commit install

pre-commit-run:
	uv run pre-commit run --all-files

check-all: lint typecheck test
	@echo "✅ All checks passed!"
