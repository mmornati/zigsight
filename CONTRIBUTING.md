# Contributing to ZigSight

Thank you for your interest in contributing to ZigSight! This document provides guidelines and instructions for contributing to the project.

## 🎯 Ways to Contribute

- 🐛 Report bugs
- 💡 Suggest new features
- 📖 Improve documentation
- 🔧 Submit code changes
- ✅ Write tests
- 🎨 Improve UI/UX

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/zigsight.git
cd zigsight
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## 🧪 Development Workflow

### Running Tests

```bash
# Run all tests
make test

# Run tests quickly (no coverage)
make test-quick

# Run tests with coverage report
make test-coverage
```

### Code Quality

```bash
# Run linting
make lint

# Format code
make format

# Check formatting (without changes)
make check-format

# Run all checks
make check
```

### Pre-commit Hooks

Pre-commit hooks will run automatically on commit. To run manually:

```bash
# Run all hooks
make pre-commit

# Or directly
pre-commit run --all-files
```

## 📝 Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use [ruff](https://github.com/astral-sh/ruff) for formatting and linting
- Use type hints throughout
- Document functions and classes with docstrings
- Follow Home Assistant integration patterns

### Type Hints

Always use type hints:

```python
from typing import Any
from homeassistant.core import HomeAssistant


def my_function(hass: HomeAssistant, value: str) -> bool:
    """Function description."""
    return True
```

### Async/Await

Use async/await for asynchronous operations:

```python
async def async_setup(hass: HomeAssistant) -> bool:
    """Async setup function."""
    await some_async_operation()
    return True
```

See [docs/testing.md](docs/testing.md) for the full picture: unit/integration
tests (below), recorded Zigbee2MQTT fixtures, the local end-to-end
environment (`make e2e`), and how to capture real traffic read-only from
your own production broker to build new fixtures.

## 🧪 Writing Tests

### Test Requirements

- Write tests for all new functionality
- **Minimum 85% code coverage is enforced by CI** - PRs failing this check will be rejected
- Use pytest fixtures from `conftest.py`
- Follow the existing test structure
- Prefer the real `hass` fixture (from `pytest-homeassistant-custom-component`)
  and `MockConfigEntry` for anything that exercises `async_setup_entry`, the
  config/options flow, or platform setup - reserve `MagicMock` hass objects
  for tests of pure logic (analytics, recommender, etc.)
- Note: `requirements-dev.txt` pins `pytest-homeassistant-custom-component`,
  which pulls in a specific `homeassistant` core release (currently
  `2026.2.3`) as a transitive dependency. That's newer than ZigSight's
  documented minimum supported Home Assistant version (`2025.10.0` in
  `manifest.json`/`hacs.json`) - the pin tracks a recent release that still
  resolves cleanly on Python 3.13 so CI stays close to what HACS users
  actually run, not the oldest supported version. If you need to validate
  against the minimum supported version specifically, install
  `homeassistant==2025.10.0` separately in a scratch environment.

### Running Tests

```bash
# Run all tests with coverage
make test

# Run tests without coverage (faster)
make test-quick

# Run tests with HTML coverage report
make test-coverage

# Run specific test file
pytest tests/test_analytics.py -v

# Run tests matching a pattern
pytest -k "test_coordinator" -v
```

### Test Markers

Tests can be marked for categorization:

```python
import pytest


@pytest.mark.slow
def test_long_running_operation():
    """Test that takes a long time."""
    pass


@pytest.mark.integration
def test_integration_with_mqtt():
    """Test that requires external services."""
    pass


@pytest.mark.unit
def test_pure_function():
    """Unit test for pure function."""
    pass
```

Run tests by marker:

```bash
# Skip slow tests
pytest -m "not slow"

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Coverage Reports

After running tests with coverage, you can view the report:

```bash
# Terminal report (shown automatically)
pytest tests/ --cov=custom_components/zigsight --cov-report=term

# HTML report (open htmlcov/index.html in browser)
pytest tests/ --cov=custom_components/zigsight --cov-report=html

# XML report (for CI tools like codecov)
pytest tests/ --cov=custom_components/zigsight --cov-report=xml
```

### Example Test

```python
"""Test module."""

import pytest
from unittest.mock import MagicMock

from custom_components.zigsight.coordinator import ZigSightCoordinator


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.mark.asyncio
async def test_coordinator_construction(mock_hass):
    """Test coordinator can be constructed."""
    coordinator = ZigSightCoordinator(mock_hass)
    assert coordinator is not None
    assert coordinator.name == "zigsight"


@pytest.mark.unit
def test_analytics_compute():
    """Test analytics computation."""
    from custom_components.zigsight.analytics import DeviceAnalytics

    analytics = DeviceAnalytics()
    result = analytics.compute_reconnect_rate([])
    assert result == 0.0
```

### Async Tests

For testing async code, use `pytest-asyncio`:

```python
import pytest


@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await some_async_function()
    assert result is not None
```

## 📋 Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `style:` for formatting changes
- `refactor:` for code refactoring
- `test:` for test changes
- `chore:` for maintenance tasks

Examples:

```
feat: add MQTT collector for Zigbee2MQTT
fix: correct coordinator async_start method
docs: update installation instructions
```

## 🔄 Pull Request Process

1. Ensure all tests pass: `make test`
2. Ensure linting passes: `make lint`
3. Update CHANGELOG.md with your changes
4. Update documentation if needed
5. Create a pull request with a clear description
6. Link to any related issues

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] All checks pass
- [ ] Type hints added
- [ ] Docstrings added

## 📚 Documentation

- Update `README.md` for user-facing changes
- Update `docs/` directory for feature documentation
- Update `DEVELOPER_README.md` for developer-facing changes
- Add examples when adding new features

## 🔍 Code Review

- Be responsive to feedback
- Make requested changes promptly
- Ask questions if something is unclear
- Be respectful and constructive

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project (Apache-2.0).

Thank you for contributing to ZigSight! 🎉
