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
python3.11 -m venv venv
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

## 🧪 Writing Tests

- Write tests for all new functionality
- Aim for 85%+ code coverage
- Use pytest fixtures from `conftest.py`
- Follow the existing test structure

Example test:

```python
"""Test module."""
import pytest

from custom_components.zigsight.coordinator import ZigSightCoordinator


def test_coordinator_construction(mock_hass):
    """Test coordinator can be constructed."""
    coordinator = ZigSightCoordinator(mock_hass)
    assert coordinator is not None
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
