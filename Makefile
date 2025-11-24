# Makefile for ZigSight integration

.PHONY: help install test lint format clean build docs setup-dev security

# Virtual environment detection and binary paths
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_PYTEST := $(VENV)/bin/pytest
VENV_RUFF := $(VENV)/bin/ruff
VENV_MYPY := $(VENV)/bin/mypy
VENV_BANDIT := $(VENV)/bin/bandit
VENV_PRE_COMMIT := $(VENV)/bin/pre-commit

# Use venv binaries if venv exists, otherwise fall back to system binaries
PYTHON := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)
PIP := $(if $(wildcard $(VENV_PIP)),$(VENV_PIP),pip)
PYTEST := $(if $(wildcard $(VENV_PYTEST)),$(VENV_PYTEST),pytest)
RUFF := $(if $(wildcard $(VENV_RUFF)),$(VENV_RUFF),ruff)
MYPY := $(if $(wildcard $(VENV_MYPY)),$(VENV_MYPY),mypy)
BANDIT := $(if $(wildcard $(VENV_BANDIT)),$(VENV_BANDIT),bandit)
PRE_COMMIT := $(if $(wildcard $(VENV_PRE_COMMIT)),$(VENV_PRE_COMMIT),pre-commit)

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
	@if [ ! -d "$(VENV)" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup-dev' first."; \
		exit 1; \
	fi
	$(PIP) install -r requirements-dev.txt

# Bootstrap local development environment
setup-dev:
	@echo "Creating virtual environment and installing development tools..."
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements-dev.txt
	$(VENV_PRE_COMMIT) install

# Run unit tests
test:
	$(PYTEST) tests/ -v --cov=custom_components/zigsight --cov-report=html --cov-report=term

# Alias for unit tests
test-unit:
	$(PYTEST) tests/ -v --cov=custom_components/zigsight --cov-report=html --cov-report=term

# Quick test (no coverage)
test-quick:
	$(PYTEST) tests/ -v

# Test with coverage report
test-coverage:
	$(PYTEST) tests/ --cov=custom_components/zigsight --cov-report=html --cov-report=term

# Run linting
lint:
	$(RUFF) check .
	$(MYPY) custom_components/zigsight/

# Security checks
security:
	$(BANDIT) -r custom_components/zigsight -c tests/bandit.yaml

# Format code
format:
	$(RUFF) format .
	$(RUFF) check --fix .

# Check formatting
check-format:
	$(RUFF) format --check .
	$(RUFF) check .

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
	$(PYTHON) -m build

# Serve documentation (when MkDocs is ready)
docs:
	@echo "MkDocs documentation will be available here when issue #10 is completed"
	@echo "For now, see docs/ directory"

# Run all checks
check: lint test

# Pre-commit hooks
pre-commit:
	$(PRE_COMMIT) run --all-files

# Install pre-commit hooks
install-hooks:
	$(PRE_COMMIT) install

# Version info
version:
	@echo "ZigSight Integration"
	@$(PYTHON) -c "import json; print('Version:', json.load(open('custom_components/zigsight/manifest.json'))['version'])"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Pytest: $$($(PYTEST) --version 2>/dev/null || echo 'Not installed')"
