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
│       ├── coordinator.py      # Device tracking (Z2M push / ZHA poll), analytics scheduling
│       ├── z2m.py              # Zigbee2MQTT topic/payload parsing (no HA state)
│       ├── entity.py           # Base entity + dynamic per-device platform setup
│       ├── diagnostics.py      # Config entry / device diagnostics
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
│   ├── fixtures/z2m/           # Recorded-style Zigbee2MQTT session (see session.json)
│   ├── z2m_replay.py           # Fixture loader / replay helper (no HA import needed)
│   ├── test_z2m.py             # Zigbee2MQTT parser unit tests
│   ├── test_z2m_integration.py # End-to-end: fixtures -> MQTT -> devices/entities
│   ├── test_migration.py       # Config entry + entity registry migrations
│   ├── test_coordinator.py     # Coordinator unit tests
│   └── test_sensor.py          # Entity builder tests
├── pyproject.toml              # Project configuration
├── requirements-dev.txt        # Development dependencies (latest HA + lint tools)
├── requirements-test-min.txt   # Unit tests on the minimum supported HA (2025.10)
├── requirements-test-latest.txt # Unit tests on the latest HA release
├── requirements-lint.txt       # ruff, mypy, bandit, pre-commit
└── README.md                   # Project README
```

## Development Environment

- **Python**: 3.14 for the default dev environment (latest Home Assistant);
  3.13 for the minimum supported Home Assistant (`make setup-min`)
- **Home Assistant compatibility**: `>=2025.10.0` -- CI runs the unit tests
  on both 2025.10 and the latest release (see CONTRIBUTING.md, "Testing
  against the minimum and latest Home Assistant")

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
| `make setup-min`   | Create `.venv-min` with the minimum supported Home Assistant (Python 3.13)   |
| `make test-min`    | mypy + unit tests (coverage gate) on the minimum supported Home Assistant    |
| `make format`      | `ruff format .` plus `ruff check --fix .`                                    |
| `make check-format`| Verify formatting (`ruff format --check .`, `ruff check .`)                  |
| `make clean`       | Remove cached artifacts (`.mypy_cache`, `.ruff_cache`, `.pytest_cache`, …)   |

All commands assume the virtualenv created by `make setup-dev` is active.

### Manual setup (optional)

If you prefer not to use the Makefile helpers:

```bash
python3.14 -m venv .venv
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

### Data flow

- **Zigbee2MQTT**: `ZigSightCoordinator` subscribes to `<base_topic>/#` through
  Home Assistant's MQTT integration and classifies each topic with
  `z2m.classify_topic()`:
  - `bridge/devices` (retained) is the authoritative device list. Devices are
    keyed by IEEE address; the friendly name -> IEEE map resolves device
    topics (friendly names may contain `/`, the longest known name wins).
    Devices missing from a new list are purged (memory, device registry,
    entities); renames update the device registry name only.
  - `<name>` state payloads are merged into the device's last state (partial
    updates keep previous values); `<name>/availability` (JSON or legacy plain
    text) sets availability and counts offline -> online transitions as
    reconnects; `/set`, `/get`, groups and unknown topics are ignored.
  - `bridge/info`, `bridge/state` and `bridge/response/networkmap` (type
    `raw`, requested on demand with `async_request_network_map()`) are stored
    for the topology/channel features.
- **ZHA**: the periodic refresh polls `ZHACollector`.
- **Entities** are created when the coordinator sends the
  `signal_new_device` dispatcher signal (`entity.async_setup_device_platform`).
  Zigbee2MQTT devices only get entities once interviewed; the entity set comes
  from `ZigSightCoordinator.entity_keys()` and is tracked per unique id, so
  entities for newly gained capabilities are added later
  and write their state on the per-device `device_signal(ieee)`; the global
  coordinator listeners only run on the 60 s periodic refresh, which also
  recomputes time based analytics.

### Function Signatures

#### `DeviceAnalytics.__init__()`

```python
def __init__(
    reconnect_rate_window_hours: int = 24,
    battery_drain_threshold: float = 10.0,
    silent_timeout: timedelta = SILENT_DEVICE_TIMEOUT,  # 25 hours
) -> None
```

All timestamps are timezone aware (UTC, `homeassistant.util.dt`).

#### `compute_reconnect_rate()`

```python
def compute_reconnect_rate(
    reconnect_events: Iterable[datetime | str],
    window_hours: int | None = None,
    now: datetime | None = None,
) -> float
```

Counts the recorded reconnect events (Zigbee2MQTT availability transitions
offline -> online) inside the window and divides by the window length.

#### `compute_battery_trend()`

```python
def compute_battery_trend(
    history: Iterable[Mapping[str, Any]],
    window_hours: int = 24,
    now: datetime | None = None,
) -> float | None
```

**Algorithm**:
1. Extract battery readings from history within the time window (all values,
   including batteries below 20%)
2. Require at least two readings spanning at least one hour
3. Compute the least squares linear regression slope
4. Return percentage change per hour (negative = draining)

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
    device: Mapping[str, Any],
    reconnect_rate: float = 0.0,
    now: datetime | None = None,
) -> float
```

Weighted average (link quality 30%, battery 20%, reconnect rate 30%,
connectivity 20%). The battery component is skipped (weights re-normalised)
when the device reports no battery. Connectivity is 100/0 when Zigbee2MQTT
availability is known, otherwise it decays linearly over the device type
dependent timeout (`compute_connectivity_score()`).

#### `check_battery_drain_warning()`

```python
def check_battery_drain_warning(
    battery_trend: float | None,
    threshold: float | None = None,
) -> bool
```

True if `battery_trend < -threshold`.

#### `check_connectivity_warning()`

```python
def check_connectivity_warning(
    device: Mapping[str, Any],
    reconnect_rate: float = 0.0,
    reconnect_rate_threshold: float = 5.0,
    now: datetime | None = None,
) -> bool
```

True if the reconnect rate reaches the threshold, if Zigbee2MQTT reports the
device offline or, when availability is unknown, if the device has been
silent for longer than the silent device timeout (25 hours for every device
type, or Zigbee2MQTT's configured passive availability timeout). ZigSight
doesn't ping devices, so a short router timeout would flag idle routers.

### Data Retention Policy

Everything is in memory and bounded:

- History: numeric metrics only (`link_quality`, `battery`, `voltage`,
  timestamp), one sample at most every 5 minutes (1 minute when the battery
  changed), at most 400 samples per device (`collections.deque(maxlen=...)`).
- Reconnect events: at most 200 timestamps per device.
- Devices removed from Zigbee2MQTT's `bridge/devices` are purged.
- Analytics are recomputed at most every 30 seconds per device on incoming
  messages, plus once per device on each periodic refresh (60 s).

For persistent storage, use Home Assistant's built-in history features.

### Testing

- `tests/test_analytics.py`: analytics functions
- `tests/test_z2m.py`: Zigbee2MQTT parsing
- `tests/test_z2m_integration.py`: end-to-end replay of `tests/fixtures/z2m`
  with `async_fire_mqtt_message` against a real `hass`

To capture new fixtures from a production broker without touching it
(read-only subscription):

```bash
mosquitto_sub -h <broker> -u <user> -P <password> -F '%j' -t 'zigbee2mqtt/#' -C 2000 > captures/capture.jsonl
```

JSON lines (`-F '%j'`) keep friendly names containing spaces intact and
carry the retain flag. The raw file contains secrets (network key, ...):
it is git-ignored under `captures/`, see [Testing](testing.md) before using
it. Anonymise names/IEEE addresses and review the diff before turning
anything into a committed fixture.

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
scanner = ManualScanner(
    scan_data=[
        {"channel": 1, "rssi": -45, "ssid": "Network1"},
        {"channel": 6, "rssi": -60},
    ]
)
aps = await scanner.scan()
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
scanner = create_scanner(mode="manual", scan_data=[{"channel": 1, "rssi": -45}])

# Host scan mode
scanner = create_scanner(mode="host_scan", host_config={"interface": "wlan0"})
```

Only `manual` and `host_scan` are supported; both `zigsight.recommend_channel`
and `POST /api/zigsight/channel-recommendation` validate `mode` against
exactly these two values. `HostScanner` also drops any 5 GHz access point
(channel >= 36) from the result, since Zigbee only operates in the 2.4 GHz
band and such results would otherwise skew the recommendation for no reason.

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

The frontend lives in `custom_components/zigsight/www/` and is served by the
integration at `/zigsight_static/` (registered once in `async_setup`, see
`__init__.py`). The sidebar panel is registered with
`panel_custom.async_register_panel` (admin only) and removed when the last
config entry is unloaded.

```
www/
├── zigsight-panel.js           # sidebar panel (<zigsight-panel>)
├── topology-card.js            # Lovelace card: device grid
├── topology-visualization.js   # Lovelace card: interactive graph
├── lib/
│   ├── topology-graph.js       # <zigsight-topology-graph> SVG graph (pan/zoom/select)
│   ├── layout.js               # radial tree + force directed layouts (pure)
│   ├── format.js               # formatting helpers (pure)
│   └── wifi.js                 # Wi-Fi scan data validation (pure)
└── vendor/
    ├── lit-core.min.js         # Lit 3.3.3 (see vendor/README.md)
    └── LICENSE-lit
```

Rules:

- **No build step, no CDN.** Files are plain ES modules importing each other
  with relative URLs; third party code is vendored in `www/vendor/` with its
  license and provenance.
- **No HTML strings.** Device names and other API data are user controlled:
  render them with Lit templates (which escape text), never with
  `innerHTML`. `tests/test_frontend_assets.py` fails on HTML string sinks and
  remote imports.
- **Plain elements.** Only `ha-icon`, `ha-card` and `ha-menu-button` are used
  from the Home Assistant frontend (they degrade gracefully); buttons, inputs
  and alerts are plain elements styled with Home Assistant CSS variables.
- `hass.callApi(method, path)` takes a path *without* the `/api/` prefix,
  e.g. `hass.callApi("GET", "zigsight/topology")`.

Checks:

```bash
# Syntax of every module
for f in custom_components/zigsight/www/*.js custom_components/zigsight/www/lib/*.js; do
  node --check --input-type=module < "$f"; done
# Unit tests of the pure helpers (layouts, validation, formatting)
node --test "tests/js/*.test.mjs"
# Python side: API, panel registration, static guards
pytest tests/test_frontend.py tests/test_frontend_assets.py tests/test_topology.py
```

To try a change, reload the browser tab with the cache disabled (the static
path is served without long cache headers; the panel module URL carries the
integration version as a cache buster).

### REST API used by the frontend

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/api/zigsight/devices` | admin | device records |
| GET | `/api/zigsight/topology` | user | nodes (IEEE ids), edges (network map or inferred), network map status, network info. Deliberately *not* admin-gated, unlike the rest of this table: the Lovelace `topology-card.js`/`topology-visualization.js` poll it every 60s and may be on a dashboard a non-admin user can see; a rejected `@require_admin` check on every poll trips Home Assistant's login-attempt tracking (`process_wrong_login`) as if it were a failed login |
| POST | `/api/zigsight/topology/networkmap` | admin | ask Zigbee2MQTT for a raw network map (202) |
| GET | `/api/zigsight/channel-recommendation` | admin | current Zigbee channel + last recommendation |
| POST | `/api/zigsight/channel-recommendation` | admin | compute a recommendation from Wi-Fi scan data |
| GET | `/api/zigsight/recommendation-history` | admin | last 10 recommendations |
| GET | `/api/zigsight/analytics/*` | admin | overview, trends, export |

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

## Documentation Site

ZigSight documentation is built using [MkDocs](https://www.mkdocs.org/) and automatically deployed to GitHub Pages.

### Viewing the Documentation

The documentation site is available at: **https://mmornati.github.io/zigsight/**

### Building Documentation Locally

To preview documentation changes locally:

```bash
# Install documentation dependencies
pip install -r requirements-docs.txt

# Start the development server
mkdocs serve

# Or build the static site
mkdocs build
```

The development server runs at `http://127.0.0.1:8000/` with live reload.

### Documentation Structure

Documentation files are in the `docs/` directory:

```
docs/
├── index.md                    # Homepage
├── getting_started.md          # Installation guide
├── analytics.md                # Analytics engine documentation
├── wifi_recommendation.md      # Wi-Fi channel recommendation guide
├── ui.md                       # Network topology card documentation
├── automations.md              # Automation blueprints guide
├── faq.md                      # Frequently asked questions
├── DEVELOPER_README.md         # This file
└── integrations/
    ├── zigbee2mqtt.md          # Zigbee2MQTT integration guide
    ├── zha.md                  # ZHA integration guide
    └── deconz.md               # deCONZ integration guide
```

### Adding or Editing Pages

1. Create or edit markdown files in the `docs/` directory
2. Update `mkdocs.yml` navigation if adding new pages
3. Test locally with `mkdocs serve`
4. Submit a pull request

### Deployment Workflow

Documentation is automatically deployed via the `.github/workflows/deploy-docs.yaml` workflow:

- **Trigger**: Push to `main` branch that modifies `docs/**`, `mkdocs.yml`, or `requirements-docs.txt`
- **Build**: MkDocs builds the static site with `mkdocs build --strict`
- **Deploy**: The `peaceiris/actions-gh-pages` action publishes to the `gh-pages` branch
- **Hosting**: GitHub Pages serves the site from the `gh-pages` branch

The workflow can also be triggered manually via `workflow_dispatch`.

### MkDocs Configuration

The documentation configuration is in `mkdocs.yml`:

- **Theme**: ReadTheDocs theme
- **Plugins**: Search
- **Extensions**: Tables, fenced code blocks, admonitions, table of contents

### Documentation Requirements

Documentation dependencies are in `requirements-docs.txt`:

- `mkdocs>=1.5.0`

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
