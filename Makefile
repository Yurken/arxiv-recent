.PHONY: install dev lint format test run fetch summarize send doctor scheduler clean

install:
	pip install .

dev:
	pip install -e ".[dev]"

lint:
	ruff check arxiv_recent/ tests/

format:
	ruff format arxiv_recent/ tests/
	ruff check --fix arxiv_recent/ tests/

test:
	pytest tests/ -v

run:
	python -m arxiv_recent run

fetch:
	python -m arxiv_recent fetch

summarize:
	python -m arxiv_recent summarize

send:
	python -m arxiv_recent send

doctor:
	python -m arxiv_recent doctor

scheduler:
	python -m arxiv_recent scheduler

clean:
	rm -rf data/arxiv_recent.db __pycache__ .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
