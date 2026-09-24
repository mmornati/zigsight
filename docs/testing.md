# Testing ZigSight

ZigSight is tested in four layers, each one cheaper to run and catching a
different class of bug than the next. This page describes all four, and how
to run the top one - a full local end-to-end environment - **without ever
touching your production Home Assistant**.

## 1. Unit / integration tests (pytest)

```bash
make test          # or: pytest tests/ -v --cov=custom_components/zigsight
```

These use [`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)
with a real (in-memory) `hass` fixture, `MockConfigEntry`, and
`async_fire_mqtt_message` to exercise `async_setup_entry`, the config/options
flow, platform setup and the Zigbee2MQTT topic parsing against real Home
Assistant machinery - not a `MagicMock` hass. See
[CONTRIBUTING.md](https://github.com/mmornati/zigsight/blob/main/CONTRIBUTING.md)
for coverage requirements and test-writing conventions.

## 2. Recorded Zigbee2MQTT fixtures

`tests/fixtures/z2m/` contains a recorded-style Zigbee2MQTT 2.x session
(`session.json` plus `bridge_devices.json`, `bridge_info.json`,
`networkmap_raw.json`): retained bridge/state, bridge/info, bridge/devices,
per-device availability (including the legacy plain-text payload), device
state messages (including a partial update that must not clobber unrelated
metrics), command topics (`/set`, `/get`) and a group state that must be
*ignored*, a friendly name containing `/`, and the raw
`bridge/response/networkmap` payload.

`tests/z2m_replay.py` loads and replays these fixtures - both for pytest
(`async_fire_messages`/`async_fire`, delivering them through Home Assistant's
mocked MQTT client) and for anything else that wants the same session as a
list of `(topic, payload, retain)` tuples, without a Home Assistant
dependency. It is the single fixture/capture loader; `scripts/z2m_replay.py`
(layer 3, below) reuses it rather than re-implementing fixture parsing.

## 3. Local end-to-end environment (Docker Compose)

This is the layer that lets you validate a change **without your production
Home Assistant, without real Zigbee hardware, and without touching your real
Zigbee2MQTT broker**. It brings up:

- `home-assistant` - a real Home Assistant container with
  `custom_components/zigsight` mounted from your working tree, pinned to a
  specific version via `HA_VERSION` (default set in `docker-compose.yml`;
  override with e.g. `HA_VERSION=latest`);
- `mosquitto` - a throwaway broker, anonymous access allowed (it only ever
  listens on the compose-internal network, never published to the host -
  see `test_config/mosquitto/mosquitto.conf`);
- `z2m-replay` - `scripts/z2m_replay.py` publishing the recorded fixtures to
  that broker like a real Zigbee2MQTT bridge would: the retained
  bridge/state/info/devices/availability messages first, then a loop of
  device state messages with realistic jitter (linkquality/battery drift,
  occasional availability flaps, a rename, a new device joining with an
  interview in progress then succeeding), and it answers a
  `bridge/request/networkmap` request on `bridge/response/networkmap` with
  the raw networkmap fixture.

Home Assistant's MQTT integration can no longer be set up from YAML, and
neither can ZigSight's config entry (both are config-flow only), so
`scripts/e2e_bootstrap.py` drives Home Assistant through onboarding (creates
the owner user, obtains an API token - there is no other way to get a token
for a brand-new instance), then through the MQTT config flow (broker:
`mosquitto`) and the ZigSight config flow (type: `zigbee2mqtt`). It then
polls the running instance until:

- the ZigSight config entry state is `loaded`;
- the devices from `bridge/devices` exist in the device registry;
- their entities exist in the entity registry with a state that isn't
  `unknown`/`unavailable` (in particular a link-quality sensor, which only
  appears once a device state message has actually been processed);
- the ZigSight panel is registered (checked via the `get_panels` websocket
  command, the same way the frontend does);
- `GET /api/zigsight/topology` returns at least one node.

It exits non-zero with a clear message identifying which check failed, so it
can gate CI (see below) as well as be run locally.

### Running it

```bash
make e2e-up          # start HA + mosquitto + z2m-replay
make e2e-bootstrap    # onboard HA, configure MQTT/ZigSight, verify everything
make e2e-down          # stop and remove the stack
make e2e               # all three, always tearing the stack down at the end
```

Default credentials, **local-only** (the container is thrown away by
`e2e-down`, and nothing here is ever exposed outside the compose network):
username `zigsight-e2e`, password `ZigSight-e2e-local-only!2026`. Override
with the `E2E_HA_USERNAME` / `E2E_HA_PASSWORD` environment variables if
needed.

Once `make e2e-up` is running you can also just open <http://localhost:8123>
in a browser and click around like a real installation - it's a real Home
Assistant, just fed by the replay tool instead of your Zigbee network.

This is separate from the plain manual dev loop (`make start` /
`scripts/integration-test.sh`, no MQTT broker included) that's useful when
you just want to poke at the integration UI without a Zigbee2MQTT backend at
all; see the [Developer README](DEVELOPER_README.md).

### Replaying a capture from your own broker

`scripts/z2m_replay.py --capture-file capture.txt` replays a file recorded
with `mosquitto_sub -v` (topic-space-payload per line) instead of the
built-in fixtures - useful for testing against your own device mix. See
"Capturing real traffic" below for how to record one, **and read the
warning there before you do**.

## 4. Trying it against your real Zigbee2MQTT (read-only capture)

The environment above uses synthetic/recorded data. To validate against your
own real devices without risking your production setup, capture traffic
**read-only** from your production broker:

```bash
mosquitto_sub -h <broker> -u <user> -P <password> -v -t 'zigbee2mqtt/#' -C 2000 > capture.txt
```

`-C 2000` stops after 2000 messages so this doesn't run forever; adjust to
taste. This only *subscribes* - it never publishes anything back to your
broker, so it cannot affect your running Zigbee2MQTT/Home Assistant.

!!! warning "Never commit a raw capture"
    A raw capture's `bridge/info` message contains your Zigbee **network
    key** and the **MQTT broker credentials** Zigbee2MQTT was configured
    with. `scripts/z2m_replay.py` and `tests/z2m_replay.py` both redact
    `config.advanced.network_key` and `config.mqtt.user`/`password` from
    `bridge/info` while *loading* a capture file, so replaying one is safe -
    but the raw file on disk, before it's loaded, is not. Don't commit it,
    don't attach it to an issue or PR, and delete it once you're done. If
    you want to turn a capture into a permanent fixture for `tests/fixtures/z2m/`,
    replay it once through the loader (which redacts it) and save *that*
    output, or scrub it by hand and review the diff before committing.

Once you have a capture, either:

- replay it locally: `python scripts/z2m_replay.py --capture-file capture.txt`
  against `make e2e-up`'s mosquitto (or any local broker), or
- point a **spare** Home Assistant instance (not your production one) at
  your production broker directly, in read-only fashion, by giving it a
  Zigbee2MQTT base topic and MQTT user that only has subscribe permissions
  if your broker supports per-user ACLs. Either way, never point a test
  instance at your production broker with a Zigbee2MQTT user that can
  *publish* - ZigSight itself never publishes command topics, but this is
  about limiting blast radius from anything else running on that Home
  Assistant instance during testing.

## CI

`.github/workflows/integration-test.yaml` runs the full compose + bootstrap
flow described in layer 3 on every pull request (matrix: the minimum
supported Home Assistant version pinned in `manifest.json`/`hacs.json`, and
`latest`), and on manual dispatch with an optional `ha_version` input to test
a specific release. It fails the job if the bootstrap script's checks fail,
or if the Home Assistant log contains any `ERROR` line from
`custom_components.zigsight`, and uploads the Home Assistant/Mosquitto/replay
logs as a build artifact on failure.
