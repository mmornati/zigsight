# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
  instead of "any gap > 5 minutes"; connectivity warnings use device-type
  timeouts (routers 10 minutes, end devices 25 hours, or Zigbee2MQTT's own
  availability timeouts) instead of "not seen for 1 hour", which flagged every
  sleepy battery device.
- Battery trend no longer ignores readings below 20% and needs readings
  spanning at least one hour.
- Voltage sensors use the unit declared by the device (Zigbee2MQTT battery
  voltage is mV, it was reported as V).
- Devices no longer reference themselves as `via_device`.
- Device diagnostics accept the `DeviceEntry` Home Assistant passes.
- MQTT subscriptions are released when setup fails after subscribing.

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
  history; devices removed from Zigbee2MQTT are removed from Home Assistant;
  stale devices can be deleted from the UI.
- Battery / battery trend / battery drain warning entities are only created
  for battery powered devices, voltage only for devices exposing a voltage.
- The connectivity warning uses the `problem` device class ("on" means there
  is a problem).
- Entities only update when their own device changes (plus the 60 s periodic
  analytics refresh); analytics are throttled; the volatile `last_update`
  attribute was removed.
- `zigsight_device_update` event: slim payload (no full MQTT message) and
  rate limited (availability changes, or metric changes at most once a minute
  per device).
- History is bounded (numeric metrics only, at most 400 samples per device)
  and purged for removed devices.
- `single_config_entry` is declared in the manifest.

### Added
- `bridge/info` (channel, PAN id, versions), `bridge/state` and raw
  `bridge/response/networkmap` data on the coordinator (network map requested
  on demand).
- Recorded-style Zigbee2MQTT fixtures (`tests/fixtures/z2m/`) with a replay
  helper, and end-to-end tests against a real Home Assistant test instance.

### Removed
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
