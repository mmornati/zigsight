# Makefile for ZigSight integration

.PHONY: help install test lint format clean build docs setup-dev security package zip test-integration start stop restart logs status check-js test-js e2e-up e2e-bootstrap e2e-check-logs e2e-down e2e

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
	@echo "  check-js       - Syntax check of the frontend JavaScript modules"
	@echo "  test-js        - Run the frontend JavaScript unit tests (Node.js)"
	@echo "  test-coverage  - Run tests with HTML coverage report"
	@echo "  test-integration - Start integration testing environment"
	@echo ""
	@echo "Integration Testing (manual, no MQTT broker):"
	@echo "  start          - Start Home Assistant for testing"
	@echo "  stop           - Stop Home Assistant"
	@echo "  restart        - Restart Home Assistant"
	@echo "  logs           - Show Home Assistant logs"
	@echo "  status         - Check Home Assistant status"
	@echo ""
	@echo "End-to-end Testing (HA + Mosquitto + Zigbee2MQTT replay, no"
	@echo "production Home Assistant needed - see docs/testing.md):"
	@echo "  e2e-up         - Start HA + mosquitto + z2m-replay"
	@echo "  e2e-bootstrap  - Onboard HA, configure MQTT/ZigSight, verify"
	@echo "  e2e-check-logs - Save stack logs, fail on ZigSight errors in HA log"
	@echo "  e2e-down       - Stop and remove the e2e stack"
	@echo "  e2e            - up + bootstrap + check-logs, always down"
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
	@echo "  clean          - Clean build artifacts and test data"
	@echo ""
	@echo "Packaging:"
	@echo "  package        - Create zip file for Home Assistant upload"
	@echo "  zip            - Alias for package"
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

# Frontend: syntax check of every ES module (vendored files included)
check-js:
	@for f in custom_components/zigsight/www/*.js custom_components/zigsight/www/lib/*.js custom_components/zigsight/www/vendor/*.js; do \
		node --check --input-type=module < "$$f" || { echo "Syntax error in $$f"; exit 1; }; \
	done
	@echo "JavaScript syntax OK"

# Frontend: unit tests of the pure JS helpers (Node.js >= 22)
test-js:
	node --test "tests/js/*.test.mjs"

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

# Integration Testing
test-integration:
	@echo "Starting integration testing environment..."
	./scripts/integration-test.sh start

start:
	./scripts/integration-test.sh start

stop:
	./scripts/integration-test.sh stop

restart:
	./scripts/integration-test.sh restart

logs:
	./scripts/integration-test.sh logs

status:
	./scripts/integration-test.sh status

# End-to-end environment: HA + Mosquitto + Zigbee2MQTT replay.
# Default credentials (local-only, override with E2E_HA_USERNAME /
# E2E_HA_PASSWORD): username "zigsight-e2e", password
# "ZigSight-e2e-local-only!2026". See docs/testing.md.
E2E_LOG_DIR := e2e-logs

e2e-up:
	docker compose --profile e2e up -d --wait home-assistant mosquitto z2m-replay

e2e-bootstrap:
	$(PYTHON) -m pip install --quiet -r requirements-e2e.txt
	$(PYTHON) scripts/e2e_bootstrap.py

# Dump the stack's logs and fail on any ZigSight error/traceback/blocking
# call in the Home Assistant log (same gate as CI).
e2e-check-logs:
	@mkdir -p $(E2E_LOG_DIR)
	docker compose --profile e2e logs --no-color --no-log-prefix home-assistant > $(E2E_LOG_DIR)/home-assistant.log 2>&1
	-docker compose --profile e2e logs --no-color z2m-replay > $(E2E_LOG_DIR)/z2m-replay.log 2>&1
	-docker compose --profile e2e logs --no-color mosquitto > $(E2E_LOG_DIR)/mosquitto.log 2>&1
	$(PYTHON) scripts/ci_check_ha_log.py $(E2E_LOG_DIR)/home-assistant.log

e2e-down:
	docker compose --profile e2e down -v

# Always tears the stack down - also when e2e-up itself fails (e.g. a
# healthcheck timeout) - but still exits non-zero when any step did.
e2e:
	@status=0; \
	$(MAKE) e2e-up && $(MAKE) e2e-bootstrap && $(MAKE) e2e-check-logs || status=$$?; \
	$(MAKE) e2e-down; \
	exit $$status

# Clean build artifacts and test data
clean:
	@echo "Cleaning build artifacts..."
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
	@echo "Cleaning test data..."
	./scripts/integration-test.sh clean 2>/dev/null || true

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

# Package for Home Assistant upload
package:
	@echo "Creating Home Assistant package..."
	@VERSION=$$($(PYTHON) -c "import json; print(json.load(open('custom_components/zigsight/manifest.json'))['version'])") && \
	ZIP_NAME="zigsight-$$VERSION.zip" && \
	rm -f $$ZIP_NAME && \
	cd custom_components && zip -r ../$$ZIP_NAME zigsight/ -x "*.pyc" -x "*__pycache__*" -x "*.pyo" -x "*.DS_Store" && \
	echo "Package created: $$ZIP_NAME"

# Alias for package
zip: package
