.PHONY: install hooks lint fmt test all

install:  ## Create the venv and install dependencies
	uv sync

hooks:  ## Install git hooks (pre-commit, commit-msg, pre-push)
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push

lint:  ## Run ruff and mypy
	uv run ruff check .
	uv run mypy

fmt:  ## Auto-format and auto-fix
	uv run ruff format .
	uv run ruff check --fix .

test:  ## Run the test suite
	uv run pytest

all: lint test  ## Lint then test
