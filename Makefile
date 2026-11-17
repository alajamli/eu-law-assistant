.PHONY: help install test lint fmt up down logs ingest eval clean

help:
	@echo "install  pip install -e .[dev]"
	@echo "up       start Postgres + API (docker compose)"
	@echo "down     stop the stack"
	@echo "ingest   download, parse and index the corpus (needs .[ml])"
	@echo "eval     run the retrieval evaluation"
	@echo "test     ruff + pytest"
	@echo "fmt      ruff format + ruff check --fix"
	@echo "clean    remove caches and generated artifacts"

install:
	python -m pip install -e ".[dev]"

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api

ingest:
	python -m ingest.cli download
	python -m ingest.cli parse
	python -m ingest.cli index

eval:
	python -m evals.run --config $$(git rev-parse --short HEAD)

lint:
	ruff check .

fmt:
	ruff check --fix .
	ruff format .

test: lint
	pytest -q

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
