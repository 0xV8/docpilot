.PHONY: help install dev-install test lint format type-check security clean build

help:
	@echo "Available commands:"
	@echo "  make install      - Install package"
	@echo "  make dev-install  - Install package with dev dependencies"
	@echo "  make test         - Run tests"
	@echo "  make test-cov     - Run tests with coverage"
	@echo "  make lint         - Run linters"
	@echo "  make format       - Format code"
	@echo "  make type-check   - Run type checker"
	@echo "  make security     - Run security scans"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make build        - Build package"
	@echo "  make pre-commit   - Run pre-commit on all files"

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"
	pre-commit install

test:
	pytest -v

test-cov:
	pytest -v --cov --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/
	black --check src/ tests/

format:
	ruff check --fix src/ tests/
	black src/ tests/

type-check:
	mypy src/docpilot --strict

security:
	bandit -r src/docpilot -f screen
	safety check --json || true
	pip-audit || true

pre-commit:
	pre-commit run --all-files

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

publish-test: build
	twine upload --repository-testpypi dist/*

publish: build
	twine upload dist/*
