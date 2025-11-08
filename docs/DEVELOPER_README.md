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
│       ├── analytics.py        # Analytics engine for metrics computation
│       ├── const.py            # Constants
│       ├── services.yaml       # Service definitions
│       ├── sensor/
│       │   ├── __init__.py     # Sensor platform setup
│       │   └── sensor.py      # Sensor entity classes
│       └── binary_sensor/
│           ├── __init__.py     # Binary sensor platform setup
│           └── binary_sensor.py # Binary sensor entity classes
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

## Development Environment

- **Python**: 3.11 – 3.13 (CI defaults to 3.13)
- **Home Assistant compatibility**: `homeassistant>=2025.10.0`

### Quick Start

```bash
git clone https://github.com/mmornati/zigsight.git
cd zigsight
make setup-dev
source .venv/bin/activate
```

`make setup-dev` creates the local virtualenv, installs every developer dependency from `requirements-dev.txt`, and registers the pre-commit hooks so linting runs before commits.

### Handy Make targets

| Command            | What it does                                                                 |
|--------------------|------------------------------------------------------------------------------|
| `make lint`        | `ruff check .` + `mypy` (mirrors the GitHub CI lint job)                     |
| `make security`    | Runs Bandit with the project configuration                                   |
| `make test`        | Unit tests with coverage HTML + terminal summary                            |
| `make test-quick`  | Unit tests without coverage                                                  |
| `make format`      | `ruff format .` plus `ruff check --fix .`                                    |
| `make check-format`| Verify formatting (`ruff format --check .`, `ruff check .`)                  |
| `make clean`       | Remove cached artifacts (`.mypy_cache`, `.ruff_cache`, `.pytest_cache`, …)   |

All commands assume the virtualenv created by `make setup-dev` is active.

### Manual setup (optional)

If you prefer not to use the Makefile helpers:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
pre-commit install
```

Run the individual tools exactly as the make targets do:

```bash
ruff check .
ruff format --check .
mypy custom_components/zigsight/
pytest tests/
bandit -r custom_components/zigsight -c tests/bandit.yaml
```

### Coverage

Project target coverage is **85%**.

```bash
pytest --cov=custom_components --cov-report=html tests/
open htmlcov/index.html
```

The CI pipeline uploads coverage to Codecov; results without a token are still published for public repositories.

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
- **Analytics**: Metrics computation engine in `analytics.py`
- **Entities**: Sensor entities in `sensor/sensor.py`, binary sensors in `binary_sensor/binary_sensor.py`
- **Platform Setup**: Platform initialization in `sensor/__init__.py` and `binary_sensor/__init__.py`
- **Config Flow**: User configuration in `config_flow.py`
- **Options**: Configuration options in `options_flow.py`

## Analytics Algorithms

The analytics engine (`analytics.py`) provides metrics computation for device health monitoring.

### Function Signatures

#### `DeviceAnalytics.__init__()`

```python
def __init__(
    reconnect_rate_window_hours: int = 24,
    battery_drain_threshold: float = 10.0,
    min_battery_for_trend: int = 20,
) -> None
```

Initializes the analytics engine with configurable thresholds.

**Parameters**:
- `reconnect_rate_window_hours`: Time window in hours for reconnect rate calculation (default: 24)
- `battery_drain_threshold`: Minimum drain rate (%/hour) to trigger warning (default: 10.0)
- `min_battery_for_trend`: Minimum battery % to compute trend (default: 20)

#### `compute_reconnect_rate()`

```python
def compute_reconnect_rate(
    device_history: list[dict[str, Any]],
    window_hours: int | None = None,
) -> float
```

**Algorithm**:
1. Filter history entries within time window
2. Sort entries by timestamp
3. Detect gaps > 5 minutes between consecutive entries (reconnection events)
4. Count reconnection events within window
5. Calculate rate as events/hour

**Returns**: Reconnect rate (events/hour) or 0.0 if insufficient data

**Time Complexity**: O(n log n) where n = number of history entries (due to sorting)

#### `compute_battery_trend()`

```python
def compute_battery_trend(
    device_history: list[dict[str, Any]],
    window_hours: int = 24,
) -> float | None
```

**Algorithm**:
1. Extract battery readings from history within time window
2. Filter readings with battery ≥ `min_battery_for_trend` (20% default)
3. Sort by timestamp
4. Compute linear regression slope using least squares method
5. Return percentage change per hour (negative = draining)

**Returns**: Battery trend (%/hour) or None if insufficient data

**Time Complexity**: O(n) where n = number of history entries

**Linear Regression Formula**:
```
slope = (n × Σ(t×b) - Σ(t) × Σ(b)) / (n × Σ(t²) - (Σ(t))²)
```
where:
- n = number of data points
- t = time in hours since first reading
- b = battery percentage

#### `compute_health_score()`

```python
def compute_health_score(
    device_data: dict[str, Any],
    device_history: list[dict[str, Any]],
) -> float
```

**Algorithm**:
1. Extract current metrics: link_quality, battery, last_seen
2. Normalize each component to 0-100 scale:
   - **Link Quality**: Normalize 0-255 → 0-100 (higher is better)
   - **Battery**: Use as-is 0-100% (higher is better)
   - **Reconnect Rate**: Invert (0/hour = 100, 10+/hour = 0)
   - **Connectivity**: Based on last_seen recency (< 5 min = 100, > 1 hour = 0, linear decay)
3. Apply weighted average using configured weights (default: link_quality 30%, battery 20%, reconnect_rate 30%, connectivity 20%)
4. Return score 0-100 where 100 is excellent

**Returns**: Health score (0-100) where 100 is excellent

**Time Complexity**: O(1) for score calculation, O(n) for reconnect rate computation

**Score Interpretation**:
- 90-100: Excellent
- 70-89: Good
- 50-69: Fair
- 0-49: Poor

#### `check_battery_drain_warning()`

```python
def check_battery_drain_warning(
    device_history: list[dict[str, Any]],
    threshold: float | None = None,
) -> bool
```

**Algorithm**:
1. Compute battery trend using `compute_battery_trend()`
2. Compare trend against threshold (default: 10%/hour)
3. Return True if trend < -threshold (negative = draining)

**Returns**: True if battery drain warning should be triggered

#### `check_connectivity_warning()`

```python
def check_connectivity_warning(
    device_data: dict[str, Any],
    reconnect_rate_threshold: float = 5.0,
) -> bool
```

**Algorithm**:
1. Extract device history from device_data
2. Compute reconnect rate using `compute_reconnect_rate()`
3. Check if reconnect_rate ≥ threshold
4. OR check if last_seen > 1 hour ago
5. Return True if either condition is met

**Returns**: True if connectivity warning should be triggered

### Data Retention Policy

- **Maximum History**: 1000 entries per device (last entries kept, FIFO)
- **Retention Period**: Configurable via `retention_days` (default: 30 days)
- **Memory Usage**: Approximately 10-50 KB per device depending on history size

History is stored in-memory in the coordinator. For persistent storage, use Home Assistant's built-in history features.

### Performance Considerations

- **Reconnect Rate Calculation**: O(n log n) due to sorting. Consider caching if called frequently.
- **Battery Trend Calculation**: O(n). Optimized by filtering entries outside window early.
- **Health Score Calculation**: O(1) after component extraction. Reconnect rate computation may be O(n log n).
- **Memory Usage**: Linear with number of devices and history size. Monitor memory usage in production.

### Testing Analytics Functions

See `tests/test_analytics.py` for comprehensive test coverage:

- Test reconnect rate with various history patterns
- Test battery trend with different drain scenarios
- Test health score computation with different metrics
- Test warning conditions with threshold variations

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
