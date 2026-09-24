# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security / Fixed (API hardening and cleanups)
- All GET data endpoints (`devices`, `topology`, `analytics/overview`,
  `analytics/trends`, `analytics/export`, `channel-recommendation`,
  `recommendation-history`) now require an admin user, matching the
  admin-only panel that is their only intended caller (previously any
  authenticated, non-admin user could read them). **This is a breaking
  change if you scripted against these endpoints with a non-admin token.**
- `analytics/export` CSV: cell values starting with `=`, `+`, `-`, `@`, a
  tab or a carriage return are now prefixed with `'` to prevent CSV formula
  injection when the file is opened in a spreadsheet application.
- `analytics/trends` and `analytics/export` now validate the `hours`,
  `metric`, `format` and `devices` query parameters and return a clear 400
  instead of silently substituting a default (`hours`) or exporting nothing
  (`devices`).
- `zigsight.recommend_channel` service: now admin-only (`host_scan` mode
  runs `iwlist`/`nmcli` subprocesses on the Home Assistant host), supports
  `SupportsResponse` (returns the recommendation instead of only logging
  it), validates `mode` against the two actually supported values
  (`manual`, `host_scan` -- `router_api` was a non-functional placeholder)
  and reuses the API's Wi-Fi scan data schema. `services.yaml` no longer
  declares an unused `input_select` entity target.
- `wifi_scanner`: a Wi-Fi scan subprocess (`iwlist`/`nmcli`) that times out
  is now killed instead of left running in the background; `nmcli -t`
  output is parsed with an escape-aware splitter so an SSID containing a
  (nmcli-escaped) `:` no longer gets cut into the wrong fields.
- `tests/bandit.yaml` no longer skips B601 (`paramiko_calls`, unrelated to
  this integration -- the comment describing it as a subprocess/shell skip
  was misleading); removed the duplicate, stale `[bandit]` section in
  `setup.cfg` in favour of `tests/bandit.yaml` (the one `make security`
  actually uses).
- `.github/workflows/docs-preview.yaml`: was permanently disabled
  (`if: false`) behind an outdated "documentation not yet available"
  comment even though `docs/` and `mkdocs.yml` exist; it now runs
  `mkdocs build --strict` on PRs touching the docs and uploads the built
  site as a downloadable preview artifact.
- Removed `setup.cfg`; `pyproject.toml` already carries the same package
  metadata and is the file the dev tooling (ruff/mypy/pytest) reads.

### Fixed (Zigbee2MQTT)
- Devices and entities are now actually created with Zigbee2MQTT: devices come
  from the retained `<base_topic>/bridge/devices` list and entities are added
  dynamically whenever a device appears (previously entities were only built
  from the (empty) device list at setup, so nothing was ever created).
- Topic parsing: friendly names containing `/` are resolved (longest known
  name), `/set`, `/get`, groups and unknown topics are ignored,
  `<name>/availability` is handled separately (JSON and legacy plain text),
  partial state payloads are merged, payload `friendly_name` is no longer
  trusted, non-JSON payloads no longer log errors.
- Payload `last_seen` (ISO 8601 / ISO 8601 local / epoch ms) is used; all
  timestamps are timezone aware.
- Reconnects are Zigbee2MQTT availability transitions offline -> online
  instead of "any gap > 5 minutes"; connectivity warnings use Zigbee2MQTT
  availability, or, when availability doesn't track a device, a 25 hour
  silence timeout for every device type (or Zigbee2MQTT's passive
  availability timeout) instead of "not seen for 1 hour", which flagged every
  sleepy battery device. While Zigbee2MQTT is offline, device availability
  is unknown and (stale, retained) availability messages are ignored: no
  stale warnings, no reconnects counted on its restart.
- Battery trend no longer ignores readings below 20% and needs readings
  spanning at least one hour.
- Voltage sensors use the unit declared by the device (Zigbee2MQTT battery
  voltage is mV, it was reported as V).
- Devices no longer reference themselves as `via_device`.
- Device diagnostics accept the `DeviceEntry` Home Assistant passes.
- MQTT subscriptions are released when setup fails after subscribing.

### Fixed (frontend panel and cards)
- The sidebar panel is registered automatically (`panel_custom`, admin only)
  and the frontend files are served by the integration at
  `/zigsight_static/`: no more copying `zigsight-panel.js` to `www/` or
  `panel_custom:` YAML. The panel is removed when the integration is unloaded.
  A leftover `panel_custom` YAML entry for `/zigsight` (or any other panel
  loading a copied `zigsight-panel` element) is kept, and a repair issue asks
  to remove it, the copied files and old `/local/...` dashboard resources.
- Works offline: Lit is vendored (`www/vendor/lit-core.min.js`, 3.3.3,
  BSD-3-Clause); the topology graph is drawn with a small built-in SVG
  renderer instead of vis-network loaded from unpkg.
- Stored XSS: device names, IEEE addresses, models and the recommendation
  explanation were inserted with `innerHTML` (and vis-network HTML
  tooltips). Every file now renders through Lit templates; a test forbids
  HTML string sinks and remote imports.
- API calls from the panel and cards used `/api/api/...` URLs
  (`hass.callApi` already prefixes `/api/`).
- Channel tab: Wi-Fi scan data can be entered (table or pasted JSON) and the
  result comes from the API response (it read a non-existent
  `hass.data` in the browser and called the service without scan data). The
  current Zigbee channel comes from Zigbee2MQTT `bridge/info`.
- Topology: nodes are keyed by IEEE address with friendly-name labels and
  real types from `bridge/devices`; links come from the Zigbee2MQTT raw
  network map (deduplicated, best LQI, parent -> child) or, without one, an
  explicitly *inferred* star to the coordinator. Admins can request a new
  network map from the panel (`POST /api/zigsight/topology/networkmap`;
  a pending request younger than 2 minutes is not re-published).
- Removed HA frontend elements (`mwc-button`, `ha-circular-progress`) are no
  longer used.

### Fixed (ZHA)
- ZHA device collection no longer reaches into `hass.data["zha"]` (an
  undocumented, unstable structure that changed shape across ZHA releases
  and made every poll fail with an `AttributeError`). Devices and their LQI
  / RSSI / battery diagnostic sensors are now discovered from Home
  Assistant's device and entity registries instead, matching the same
  IEEE-keyed device-record / entity model Zigbee2MQTT uses (same platforms,
  same analytics).
- Values are pushed live (`async_track_state_change_event` on the tracked
  diagnostic entities) instead of being polled every 60 seconds; the
  periodic refresh now only re-discovers devices/entities (to pick up
  devices ZHA adds later).
- Reconnects are counted on availability transitions (unavailable ->
  available across a device's tracked entities), never once per
  poll/update, mirroring the Zigbee2MQTT availability based reconnect
  counting.
- `zha` moved to `after_dependencies`; setup is retried
  (`ConfigEntryNotReady`) until a ZHA config entry is loaded, and the config
  flow aborts with a clear message when ZHA isn't configured yet.

### Added (ZHA)
- New service `zigsight.enable_zha_diagnostic_entities`: enables every LQI
  and RSSI sensor still disabled by its ZHA default across all ZHA devices
  in one call (never re-enables an entity a user disabled themselves).
  Returns the number and ids of the entities it enabled; Home Assistant
  reloads the ZHA config entry afterwards to create them.
- A repair issue is raised while any LQI/RSSI sensor is still disabled by
  default in ZHA mode, pointing at the new service, and clears once every
  such sensor is enabled.

### Changed
- Zigbee2MQTT messages are received only through Home Assistant's MQTT
  integration; setup is retried (`ConfigEntryNotReady`) until MQTT is
  available and the config flow aborts with a clear message when MQTT is not
  set up. `mqtt` moved to `after_dependencies`, so ZHA-only installations no
  longer need MQTT.
- Unique ids are IEEE based (`<ieee>_<key>`) with `has_entity_name` and
  translated entity names; devices are identified by IEEE address, carry model
  / manufacturer from Zigbee2MQTT and hang off a "Zigbee2MQTT bridge" device.
  Existing friendly-name based entities and devices are migrated
  automatically (entity ids are kept).
- Renamed Zigbee2MQTT devices keep their Home Assistant device, entities and
  history; devices removed from Zigbee2MQTT (also while Home Assistant was
  down) are removed from Home Assistant; an empty device list is ignored;
  stale devices can be deleted from the UI.
- Entities are created once a device's interview is complete (base entities
  for FAILED interviews); missing entities are added when a device gains
  capabilities and removed when it loses them.
- Legacy battery / voltage entities of devices that no longer get them (e.g.
  mains powered devices) are removed during the migration. Devices disabled
  in Zigbee2MQTT are migrated too (areas, names and user settings kept).
- Battery / battery trend / battery drain warning entities are only created
  for battery powered devices, voltage only for devices exposing a voltage.
- The connectivity warning uses the `problem` device class ("on" means there
  is a problem).
- Entities only update when their own device changes (plus the 60 s periodic
  analytics refresh); analytics are throttled; the volatile `last_update`
  attribute was removed.
- `zigsight_device_update` event: slim payload (no full MQTT message) and
  rate limited (availability changes, or battery / voltage changes at most
  once a minute per device; link quality changes alone don't fire it).
- History is bounded (numeric metrics only, at most 400 samples per device)
  and purged for removed devices.
- `single_config_entry` is declared in the manifest.

### Added
- `bridge/info` (channel, PAN id, versions), `bridge/state` and raw
  `bridge/response/networkmap` data on the coordinator (network map requested
  on demand).
- Recorded-style Zigbee2MQTT fixtures (`tests/fixtures/z2m/`) with a replay
  helper, and end-to-end tests against a real Home Assistant test instance.

### Changed (API)
- `POST /api/zigsight/channel-recommendation` requires an admin user (it can
  run a Wi-Fi scan on the host), validates the scan data (400 on invalid
  input) and no longer returns exception text; `GET` always returns the
  current Zigbee channel.
- `GET /api/zigsight/topology` adds `links_source`, `coordinator_id`,
  `network_map` and `network`; edges have `inferred`; devices without a known
  Zigbee type are `unknown` (was `end_device`).
- API views are registered once per Home Assistant run (not on every reload).

### Removed
- `FRONTEND_PANEL_IMPLEMENTATION.md` (obsolete).
- Direct MQTT client mode (`aiomqtt` requirement) and the MQTT broker, port,
  username and password configuration fields (removed from existing entries
  by the config entry migration to version 1.2).

### Added (scaffold)
- Project scaffold with basic structure
- Home Assistant custom component skeleton
- Coordinator with async support
- Sensor platform with base classes
- Configuration flow handler
- Options flow handler
- Unit tests for manifest, coordinator, and sensors
- CI workflow with ruff, mypy, and pytest
- Code coverage reporting to Codecov
- Development tools (Makefile, pre-commit hooks)
- HACS support
- Localization support (strings.json)
- Documentation structure

## [0.1.0] - 2024-01-XX

### Added
- Initial release
- Project scaffold and CI setup
- Basic coordinator and sensor structure
- Development documentation
- User documentation
