# Getting Started with ZigSight

ZigSight is a Home Assistant custom component that provides diagnostics and optimization tools for Zigbee networks.

## Installation

To install ZigSight, copy the `custom_components/zigsight/` directory into your Home Assistant `custom_components/` folder.

1. Navigate to your Home Assistant configuration directory (usually `.homeassistant/` or `config/`)
2. Create a `custom_components/` directory if it doesn't exist
3. Copy the entire `zigsight/` folder into `custom_components/`
4. Restart Home Assistant
5. Go to **Settings > Devices & Services** and click **Add Integration**
6. Search for "ZigSight" and follow the setup wizard

Your directory structure should look like this:

```
config/
├── configuration.yaml
└── custom_components/
    └── zigsight/
        ├── __init__.py
        ├── manifest.json
        ├── config_flow.py
        └── ...
```

## Configuration

After installation, ZigSight can be configured through the Home Assistant UI via **Settings > Devices & Services**.

Currently, the integration creates a basic scaffold. Future releases will add support for:
- Zigbee2MQTT integration
- ZHA integration
- deCONZ integration
- Network topology visualization
- Analytics and health monitoring

## How to Enable CI

This project uses GitHub Actions for continuous integration. The CI pipeline runs automatically on every push and pull request to the main branch.

### CI Checks

The following checks are performed:

1. **Linting**: Ruff is used to check code style and format
2. **Type Checking**: Mypy is used for static type analysis
3. **Tests**: Pytest runs the test suite with coverage reporting
4. **Coverage**: Code coverage is uploaded to Codecov

### Opening a Pull Request

When opening a PR, ensure that:

1. All linting checks pass
2. Type checking passes (warnings are acceptable)
3. All tests pass
4. Code coverage is maintained or improved

You can run these checks locally before pushing:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run linting
ruff check custom_components/ tests/
ruff format --check custom_components/ tests/

# Run type checking
mypy custom_components/

# Run tests
pytest tests/
```

For more information, see the [Developer README](../docs/DEVELOPER_README.md).

