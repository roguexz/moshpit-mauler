.PHONY: install format lint test clean

install:
	uv sync

format:
	uv run black moshpit tests
	uv run ruff check moshpit tests --fix

lint:
	uv run ruff check moshpit tests
	uv run mypy moshpit

test:
	uv run pytest tests --cov=moshpit --cov-report=term-missing

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -f failure_manifest.json moshpit.log
