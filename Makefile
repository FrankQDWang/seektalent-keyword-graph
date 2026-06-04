sync:
	uv sync --extra dev --extra builder

test:
	uv run pytest

lint:
	uv run ruff check .

build-wheel:
	uv run python -m build --wheel

check: lint test build-wheel
