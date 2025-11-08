# Makefile for ZigSight integration

.PHONY: help install test lint format clean build docs setup-dev security

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "Testing:"
	@echo "  test           - Run unit tests with coverage"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-quick     - Run tests quickly (no coverage)"
	@echo "  test-coverage  - Run tests with HTML coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint           - Run Ruff (lint) + mypy"
	@echo "  format         - Format code with Ruff (entire repo)"
	@echo "  check-format   - Check code formatting (no changes)"
	@echo ""
	@echo "Development:"
	@echo "  install        - Install dependencies"
	@echo "  install-dev    - Install development dependencies"
	@echo "  setup-dev      - Create venv, install dev tools, and install pre-commit hooks"
	@echo "  clean          - Clean build artifacts"
	@echo ""
	@echo "Documentation:"
	@echo "  docs           - Serve MkDocs documentation (when ready)"

# Install dependencies (deprecated, use setup-dev)
install: install-dev

# Install development dependencies (deprecated, use setup-dev)
install-dev:
	pip install -r requirements-dev.txt

# Bootstrap local development environment
setup-dev:
	@echo "Creating virtual environment and installing development tools..."
	@test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && python3 -m pip install --upgrade pip
	. .venv/bin/activate && python3 -m pip install -r requirements-dev.txt
	. .venv/bin/activate && pre-commit install

# Run unit tests
test:
	pytest tests/ -v --cov=custom_components/zigsight --cov-report=html --cov-report=term

# Alias for unit tests
test-unit:
	pytest tests/ -v --cov=custom_components/zigsight --cov-report=html --cov-report=term

# Quick test (no coverage)
test-quick:
	pytest tests/ -v

# Test with coverage report
test-coverage:
	pytest tests/ --cov=custom_components/zigsight --cov-report=html --cov-report=term

# Run linting
lint:
	ruff check .
	mypy custom_components/zigsight/

# Security checks
security:
	bandit -r custom_components/zigsight -c tests/bandit.yaml

# Format code
format:
	ruff format .
	ruff check --fix .

# Check formatting
check-format:
	ruff format --check .
	ruff check .

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# Build package
build: clean
	python -m build

# Serve documentation (when MkDocs is ready)
docs:
	@echo "MkDocs documentation will be available here when issue #10 is completed"
	@echo "For now, see docs/ directory"

# Run all checks
check: lint test

# Pre-commit hooks
pre-commit:
	pre-commit run --all-files

# Install pre-commit hooks
install-hooks:
	pre-commit install

# Version info
version:
	@echo "ZigSight Integration"
	@python -c "import json; print('Version:', json.load(open('custom_components/zigsight/manifest.json'))['version'])"
	@echo "Python: $$(python3 --version)"
	@echo "Pytest: $$(pytest --version 2>/dev/null || echo 'Not installed')"
