# Developer README

This document provides information for developers contributing to the ZigSight project.

## Repository Layout

```
.
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI workflow
├── custom_components/
│   └── zigsight/
│       ├── __init__.py         # Integration entry point
│       ├── manifest.json       # Home Assistant manifest
│       ├── config_flow.py      # Configuration flow handler
│       ├── options_flow.py     # Options flow handler
│       ├── coordinator.py      # Data update coordinator
│       ├── const.py            # Constants
│       ├── services.yaml       # Service definitions
│       └── sensor/
│           ├── __init__.py     # Sensor platform setup
│           └── sensor.py      # Sensor entity classes
├── docs/
│   ├── getting_started.md      # User documentation
│   └── DEVELOPER_README.md     # This file
├── tests/
│   ├── test_manifest.py        # Manifest validation tests
│   ├── test_coordinator.py     # Coordinator tests
│   └── test_sensor.py          # Sensor entity tests
├── pyproject.toml              # Project configuration
├── requirements-dev.txt        # Development dependencies
└── README.md                   # Project README
```

## Python Version

This project requires **Python 3.11** or higher.

Home Assistant compatibility: `homeassistant>=2025.5.0`

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/mmornati/zigsight.git
   cd zigsight
   ```

2. Create a virtual environment:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

## Running Tests Locally

To run the test suite:

```bash
pytest tests/
```

With coverage:

```bash
pytest --cov=custom_components --cov-report=term-missing tests/
```

To run specific tests:

```bash
pytest tests/test_coordinator.py
pytest tests/test_sensor.py -v
```

## Testing Commands

### Linting

```bash
# Check code style
ruff check custom_components/ tests/

# Format code
ruff format custom_components/ tests/

# Check only (no changes)
ruff format --check custom_components/ tests/
```

### Type Checking

```bash
mypy custom_components/
```

### Running All Checks

```bash
# Run all checks
ruff check custom_components/ tests/
ruff format --check custom_components/ tests/
mypy custom_components/
pytest tests/
```

## Code Coverage

The project aims for **85% code coverage**. Coverage reports are generated during CI runs and uploaded to Codecov.

To view coverage locally:

```bash
pytest --cov=custom_components --cov-report=html tests/
open htmlcov/index.html  # View coverage report
```

## Adding Secrets for Codecov

Codecov token is optional for public repositories. If you want to add a Codecov token:

1. Go to [Codecov](https://codecov.io) and sign in with GitHub
2. Add your repository
3. Copy the repository upload token
4. In your GitHub repository, go to **Settings > Secrets and variables > Actions**
5. Add a new secret named `CODECOV_TOKEN` with the token value

The CI workflow will automatically use this token if present.

## Project Structure Guidelines

- **Constants**: All constants should be defined in `const.py`
- **Coordinator**: Data fetching and state management in `coordinator.py`
- **Entities**: Sensor entities in `sensor/sensor.py`
- **Platform Setup**: Platform initialization in `sensor/__init__.py`
- **Config Flow**: User configuration in `config_flow.py`
- **Options**: Configuration options in `options_flow.py`

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run tests and linting locally
4. Commit your changes: `git commit -m "Add feature: description"`
5. Push to GitHub: `git push origin feature/your-feature-name`
6. Create a Pull Request

## Resources

- [Home Assistant Developer Documentation](https://developers.home-assistant.io/)
- [Home Assistant Integration Architecture](https://developers.home-assistant.io/docs/creating_integration_architecture/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)

