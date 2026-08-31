.PHONY: check fmt lint type test

check: fmt lint type test

fmt:
	uv run ruff format --check src tests

lint:
	uv run ruff check src tests

type:
	uv run mypy

test:
	uv run pytest -q
