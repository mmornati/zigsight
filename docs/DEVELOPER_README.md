# Developer README

This document provides information for developers contributing to the ZigSight project.

## Repository Layout

```
.
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI workflow
├── automations/
│   ├── README.md               # Blueprint overview and import instructions
│   ├── battery_drain.yaml      # Battery low alert blueprint
│   ├── reconnect_flap.yaml     # Device flapping alert blueprint
│   └── network_health_daily_report.yaml  # Daily health report blueprint
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
│   ├── automations.md          # Automation blueprints guide
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

## Wi-Fi Scanner Adapters

ZigSight includes a Wi-Fi scanning system for channel recommendation. The system uses an adapter pattern to support multiple input methods.

### Scanner Architecture

All scanners implement the `WiFiScanner` abstract base class:

```python
class WiFiScanner(ABC):
    @abstractmethod
    async def scan(self) -> list[dict[str, Any]]:
        """Return list of APs with keys: channel, rssi, ssid (optional)"""
```

### Available Adapters

#### ManualScanner
Accepts pre-scanned data from user input.

**Usage:**
```python
scanner = ManualScanner(scan_data=[
    {"channel": 1, "rssi": -45, "ssid": "Network1"},
    {"channel": 6, "rssi": -60}
])
aps = await scanner.scan()
```

#### RouterAPIScanner
Queries router APIs for scan data. Currently a placeholder for future router-specific implementations.

**Supported Router Types:**
- UniFi (planned)
- OpenWrt (planned)
- Fritz!Box (planned)

**Adding Router Support:**
Extend `RouterAPIScanner.scan()` to add router-specific API calls:

```python
async def scan(self) -> list[dict[str, Any]]:
    if self.router_type == "unifi":
        return await self._scan_unifi()
    elif self.router_type == "openwrt":
        return await self._scan_openwrt()
    # ...
```

#### HostScanner
Scans Wi-Fi using host system tools (iwlist or nmcli).

**Requirements:**
- Linux host with Wi-Fi adapter
- `iwlist` (wireless-tools) or `nmcli` (NetworkManager) installed
- Appropriate permissions (may require privileged add-on)

**Permissions:**
- **iwlist**: Typically requires root or CAP_NET_ADMIN capability
- **nmcli**: Usually works without elevated permissions if NetworkManager is running

### Factory Function

Use `create_scanner()` to instantiate the appropriate scanner:

```python
from custom_components.zigsight.wifi_scanner import create_scanner

# Manual mode
scanner = create_scanner(
    mode="manual",
    scan_data=[{"channel": 1, "rssi": -45}]
)

# Router API mode
scanner = create_scanner(
    mode="router_api",
    router_config={
        "router_type": "unifi",
        "host": "192.168.1.1",
        "username": "admin",
        "password": "secret"
    }
)

# Host scan mode
scanner = create_scanner(
    mode="host_scan",
    host_config={"interface": "wlan0"}
)
```

### Adding a New Router Adapter

1. **Identify the API endpoint** for Wi-Fi scanning in your router
2. **Add authentication logic** in `RouterAPIScanner.__init__()`
3. **Implement the scan method** for your router type:

```python
async def _scan_your_router(self) -> list[dict[str, Any]]:
    """Scan using YourRouter API."""
    async with aiohttp.ClientSession() as session:
        # Authenticate
        auth_data = await self._authenticate_your_router(session)
        
        # Query scan endpoint
        async with session.get(
            f"http://{self.host}/api/wifi/scan",
            headers={"Authorization": f"Bearer {auth_data['token']}"}
        ) as response:
            data = await response.json()
        
        # Parse response into standard format
        return [
            {
                "channel": ap["chan"],
                "rssi": ap["signal"],
                "ssid": ap.get("name")
            }
            for ap in data["access_points"]
        ]
```

4. **Add router type** to `RouterAPIScanner.scan()` dispatch logic
5. **Add tests** in `tests/test_wifi_scanner.py`
6. **Document** in `docs/wifi_recommendation.md`

### Testing Scanner Adapters

See `tests/test_wifi_scanner.py` for comprehensive test coverage:

```python
@pytest.mark.asyncio
async def test_your_scanner() -> None:
    scanner = YourScanner(config)
    result = await scanner.scan()
    
    assert isinstance(result, list)
    for ap in result:
        assert "channel" in ap
        assert "rssi" in ap
```

## Channel Recommender Algorithm

The channel recommender in `recommender.py` uses frequency overlap analysis to score Zigbee channels.

### Algorithm Overview

1. **Calculate Overlap Factor** for each Wi-Fi AP and Zigbee channel pair:
   - Compute frequency distance between channels
   - Apply overlap percentage based on bandwidth (Wi-Fi ~22 MHz, Zigbee ~2 MHz)
   - Factor in signal strength (RSSI)
   
2. **Score Each Zigbee Channel** (11, 15, 20, 25):
   - Sum overlap factors from all Wi-Fi APs
   - Lower score = less interference
   
3. **Select Best Channel**:
   - Choose channel with lowest score
   - Generate human-readable explanation

### Key Functions

#### `calculate_overlap_factor(wifi_channel, zigbee_channel, rssi)`
Returns interference factor (0-100) for a single Wi-Fi AP and Zigbee channel pair.

**Formula:**
```python
freq_distance = abs(wifi_freq - zigbee_freq)
overlap_percentage = max(0, 1 - (freq_distance / 22))
normalized_rssi = (rssi + 90) * 100 / 60  # -30 to -90 dBm range
interference_factor = overlap_percentage * normalized_rssi
```

#### `score_zigbee_channel(zigbee_channel, wifi_aps)`
Returns total interference score (0-100) for a Zigbee channel considering all Wi-Fi APs.

#### `recommend_zigbee_channel(wifi_aps)`
Returns dict with `recommended_channel`, `scores`, and `explanation`.

### Frequency Mappings

**Wi-Fi (2.4 GHz):**
- Channel 1: 2412 MHz
- Channel 6: 2437 MHz (most common)
- Channel 11: 2462 MHz
- Channels 1-13 supported (14 in Japan)

**Zigbee (2.4 GHz):**
- Channel 11: 2405 MHz (recommended)
- Channel 15: 2425 MHz (recommended)
- Channel 20: 2450 MHz (recommended)
- Channel 25: 2475 MHz (recommended)
- Channels 12-24, 26 available but not recommended

## Frontend Development

ZigSight includes a custom Lovelace card for network topology visualization.

### Card Location

The topology card is located at:
```
custom_components/zigsight/www/topology-card.js
```

### No Build Process Required

The topology card is written in vanilla JavaScript and requires no build process. It can be directly loaded by Home Assistant as a Lovelace resource.

### Card Registration

The card is automatically registered when loaded. Users need to:

1. Copy the card to their `www/` directory:
   ```bash
   mkdir -p config/www/community/zigsight
   cp custom_components/zigsight/www/topology-card.js config/www/community/zigsight/
   ```

2. Register as a Lovelace resource in `configuration.yaml`:
   ```yaml
   lovelace:
     mode: yaml
     resources:
       - url: /local/community/zigsight/topology-card.js
         type: module
   ```

   Or via UI: Settings → Dashboards → Resources → Add Resource

### Card Usage

Add to any dashboard:
```yaml
type: custom:zigsight-topology-card
title: Zigbee Network Topology
```

### Card Development

To modify the card:

1. Edit `custom_components/zigsight/www/topology-card.js`
2. Copy updated file to Home Assistant's `www/` directory
3. Clear browser cache or use incognito mode
4. Refresh the dashboard

### Card Features

- **Network Statistics**: Shows device counts by type
- **Device Cards**: Interactive cards for each device with metrics
- **Color Coding**: Visual indicators for device type and health
- **Device Details**: Click any device to see detailed information
- **Link Quality**: Color-coded signal strength indicators
- **Warnings**: Highlights devices with connectivity or battery issues

### API Endpoint

The card fetches data from `/api/zigsight/topology` which returns:
- Node list with device information
- Edge list with parent-child relationships
- Network statistics

See `docs/ui.md` for complete API documentation.

### Testing Frontend Changes

Since there's no build process, testing is straightforward:

1. Copy the updated card to Home Assistant
2. Reload the dashboard
3. Check browser console for errors
4. Test all interactive features

### Future Enhancements

Potential improvements for the topology card:

- Interactive graph visualization (D3.js, vis-network)
- Device filtering and search
- Automatic refresh intervals
- Export topology as image
- Historical topology comparison
- Custom color schemes

## Automation Blueprints

ZigSight includes pre-built Home Assistant automation blueprints in the `automations/` directory.

### Blueprint Location

Blueprints are stored in:
```
automations/
├── README.md                        # Overview and import instructions
├── battery_drain.yaml               # Battery low alert blueprint
├── reconnect_flap.yaml              # Device flapping detection blueprint
└── network_health_daily_report.yaml # Daily network health report blueprint
```

### Blueprint Structure

Each blueprint follows the Home Assistant blueprint schema:

```yaml
blueprint:
  name: Blueprint Name
  description: Description of what the blueprint does
  domain: automation
  author: ZigSight
  source_url: https://github.com/mmornati/zigsight/blob/main/automations/blueprint.yaml
  input:
    input_name:
      name: Human Readable Name
      description: What this input controls
      default: default_value
      selector:
        # Input selector type

trigger:
  # Trigger configuration

condition:
  # Optional conditions

action:
  # Actions to perform
```

### Creating a New Blueprint

1. **Create the blueprint file** in `automations/`:
   ```bash
   touch automations/my_new_blueprint.yaml
   ```

2. **Define the blueprint metadata**:
   - `name`: Short, descriptive name
   - `description`: What the blueprint does
   - `domain`: Always `automation` for automation blueprints
   - `author`: "ZigSight"
   - `source_url`: Link to the file on GitHub

3. **Define inputs** with appropriate selectors:
   - `entity`: Entity picker
   - `number`: Numeric input with min/max/step
   - `text`: Free text input
   - `boolean`: Toggle switch
   - `time`: Time picker
   - `select`: Dropdown selection

4. **Add triggers, conditions, and actions** using the inputs:
   ```yaml
   trigger:
     - platform: state
       entity_id: !input my_entity_input
   ```

5. **Test the blueprint**:
   - Import into Home Assistant
   - Create an automation from it
   - Verify all inputs work correctly

6. **Add tests** in `tests/test_blueprints.yaml`:
   ```python
   def test_my_blueprint_yaml_valid():
       """Test that my_blueprint.yaml is valid YAML."""
       blueprint_path = Path("automations/my_new_blueprint.yaml")
       with blueprint_path.open() as f:
           data = yaml.safe_load(f)
       assert "blueprint" in data
       assert "trigger" in data
       assert "action" in data
   ```

7. **Update documentation**:
   - Add to `automations/README.md`
   - Add configuration reference to `docs/automations.md`

### Blueprint Testing

Blueprint YAML files are validated in CI:

```bash
# Run blueprint validation tests
pytest tests/test_blueprints.py -v
```

Tests verify:
- YAML syntax is valid
- Required blueprint keys are present
- Input definitions are properly formatted
- Triggers and actions are defined

### User Documentation

User-facing documentation is in `docs/automations.md`, which covers:
- How to import blueprints
- How to create automations from blueprints
- Configuration reference for each blueprint
- Customization examples

## ZHA Integration Support

ZigSight supports collecting device diagnostics from the Zigbee Home Automation (ZHA) integration alongside Zigbee2MQTT.

### Architecture

The ZHA collector (`zha_collector.py`) implements a polling-based approach to gather device metrics:

```
┌─────────────┐
│ Coordinator │
└──────┬──────┘
       │
       ├─────────────┐
       │             │
       v             v
┌──────────┐   ┌─────────────┐
│   MQTT   │   │ ZHA         │
│ Collector│   │ Collector   │
└──────────┘   └─────────────┘
       │             │
       v             v
┌──────────────────────┐
│  Device Metrics      │
│  (Normalized Format) │
└──────────────────────┘
```

### ZHA Collector Implementation

The `ZHACollector` class provides:

#### Key Methods

**`is_available() -> bool`**

Checks if ZHA integration is loaded by testing `"zha" in hass.data`.

**`collect_devices() -> dict[str, dict[str, Any]]`**

Collects all ZHA devices and their metrics:
1. Access `hass.data["zha"]["gateway"]`
2. Iterate through `gateway.devices`
3. For each device, collect metrics from:
   - Device attributes (`lqi`, `rssi`, `last_seen`)
   - Diagnostic entities (`sensor.<device>_rssi`, etc.)
4. Normalize metrics to coordinator format

**`_collect_device_metrics(zha_device) -> dict[str, Any]`**

Extracts metrics from ZHA device attributes:
- `lqi` → `link_quality`
- `rssi` → `rssi`
- `last_seen` → ISO 8601 timestamp

**`_collect_entity_metrics(ieee: str) -> dict[str, Any]`**

Reads diagnostic entities from device/entity registries:
1. Find device by IEEE address in device registry
2. Get entities for device from entity registry
3. Read entity states for RSSI, LQI, battery

### Metric Normalization

ZHA metrics are normalized to match Zigbee2MQTT format for consistency:

| ZHA Source | Normalized Name | Type |
|------------|-----------------|------|
| `zha_device.lqi` | `link_quality` | int (0-255) |
| `zha_device.rssi` | `rssi` | int (dBm) |
| `zha_device.last_seen` | `last_seen` | ISO 8601 string |
| `sensor.<device>_battery` | `battery` | float (%) |

### Coordinator Integration

The coordinator integrates ZHA collection through:

**Configuration**
```python
coordinator = ZigSightCoordinator(
    hass,
    enable_zha=True,  # Enable ZHA collection
    ...
)
```

**Update Cycle**
```python
async def _async_update_data(self) -> dict[str, Any]:
    # Collect ZHA devices if enabled
    if self._enable_zha and self._zha_collector:
        await self._collect_zha_devices()
    # ... continue with MQTT and analytics
```

**Device Processing**
```python
def _process_zha_device_update(self, device_id: str, device_data: dict):
    # Process ZHA device similar to MQTT devices
    # - Track reconnections
    # - Store metrics
    # - Update history
    # - Fire events
```

### ZHA API Usage

ZigSight uses the following Home Assistant APIs for ZHA:

**Stable APIs (Public)**
- `device_registry.async_get(hass)` - Get device registry
- `entity_registry.async_get(hass)` - Get entity registry
- `device_registry.async_get_device(identifiers)` - Find device by ID
- `entity_registry.async_entries_for_device(device_id)` - Get device entities
- `hass.states.get(entity_id)` - Read entity state

**Internal APIs (May Change)**
- `hass.data["zha"]` - Access ZHA integration data
- `hass.data["zha"]["gateway"]` - Access ZHA gateway
- `gateway.devices` - Iterate ZHA devices
- `zha_device.lqi`, `zha_device.rssi` - Device attributes

### Handling ZHA Changes

If ZHA internals change in future Home Assistant versions:

1. **Check ZHA integration release notes** for API changes
2. **Update `ZHACollector` methods** to match new APIs
3. **Add version checks** if supporting multiple HA versions:
   ```python
   from homeassistant.const import __version__
   if __version__ >= "2025.1.0":
       # New API
   else:
       # Legacy API
   ```
4. **Update tests** to cover new behavior
5. **Document changes** in `docs/integrations/zha.md`

### Testing ZHA Collector

Tests use mocks to simulate ZHA integration:

```python
# Mock ZHA gateway
mock_gateway = MagicMock()
mock_gateway.devices = {ieee: mock_device}
mock_hass.data["zha"] = {"gateway": mock_gateway}

# Mock device attributes
mock_device.lqi = 200
mock_device.rssi = -50
mock_device.last_seen = datetime.now()

# Test collection
collector = ZHACollector(mock_hass)
devices = await collector.collect_devices()
```

See `tests/test_zha_collector.py` for comprehensive test coverage.

### Performance Considerations

- **Polling interval**: ZHA collection runs on coordinator update cycle (60s default)
- **Device count**: Tested with up to 50 devices; larger networks may need tuning
- **Registry access**: Device/entity registry lookups are cached by Home Assistant
- **Entity state reads**: Minimal overhead, reads from state machine

### Future Enhancements

Potential improvements for ZHA support:

- **Network topology**: Extract parent-child relationships from ZHA
- **Route table**: Access ZHA routing information
- **Device statistics**: Collect packet loss, retry counts
- **Event-based updates**: Subscribe to ZHA device events instead of polling
- **Deeper integration**: Use ZHA's internal state tracking

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
- [Wi-Fi/Zigbee Coexistence](https://www.metageek.com/training/resources/zigbee-wifi-coexistence/)
