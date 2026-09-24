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
  specific version via `HA_VERSION` (the default in `docker-compose.yml` is
  the single source of the pinned version, CI reads it from there; override
  with e.g. `HA_VERSION=latest`). Port 8123 is published on **127.0.0.1
  only**, so the well-known e2e credentials below are never reachable from
  your LAN;
- `mosquitto` - a throwaway broker, anonymous access allowed. It has no
  published ports at all: only the other compose containers can reach it
  (see `test_config/mosquitto/mosquitto.conf`);
- `z2m-replay` - `scripts/z2m_replay.py` acting like a Zigbee2MQTT bridge on
  that broker:
    - the retained `bridge/state`, `bridge/info`, `bridge/devices`,
      `bridge/groups` and per-device availability messages are published on
      every (re)connect; `bridge/state` has a retained `offline` last will;
    - device states are re-sent every round (a round is 5 s x `--speed`; the
      compose service uses `Z2M_REPLAY_SPEED`, default `0.4` = 2 s) with
      linkquality/battery jitter and short availability flaps - states sent
      before Home Assistant subscribed are simply lost, like with a real
      bridge, so re-sending them is what makes the entities get values;
    - a *scenario*, run once when asked (see below): `Kitchen/Motion Sensor`
      is renamed to `Hallway/Motion Sensor` (old retained topics cleared,
      `bridge/response/device/rename`, `bridge/devices` republished), then a
      new device, `New Sensor`, joins (`bridge/event` `device_joined` and
      `device_interview` started/successful, `bridge/devices` republished
      after each step);
    - it answers `bridge/request/networkmap` on `bridge/response/networkmap`
      with the raw networkmap fixture;
    - command topics (`/set`, `/get`) are never replayed.

Home Assistant's MQTT integration can no longer be set up from YAML, and
neither can ZigSight's config entry (both are config-flow only), so
`scripts/e2e_bootstrap.py` drives Home Assistant through onboarding (creates
the owner user, obtains an API token - there is no other way to get a token
for a brand-new instance), then through the MQTT config flow (broker:
`mosquitto`) and the ZigSight config flow (type: `zigbee2mqtt`). A required
form field it has no value for (no serialized default, no override) makes it
fail naming that field, rather than guessing. It then verifies, each phase
polling with a bounded timeout (HTTP and websocket errors are retried):

1. **Initial state** - the ZigSight config entry is `loaded`; the device
   registry holds *exactly* the expected devices (the `Zigbee2MQTT bridge`
   service device plus every enabled device of `bridge/devices` - no device
   for the `Living Room Lights` group, none for a `<name>/set` topic, none
   for the disabled `Old Door Sensor`); every device that sent a state has a
   link-quality sensor whose state is not `unknown`/`unavailable`; the
   ZigSight panel is registered (`get_panels`, like the frontend); `GET
   /api/zigsight/topology` returns nodes.
2. **Dynamic path** - it asks the replay to run its scenario (publishing on
   `zigsight-e2e/replay/scenario` through Home Assistant's `mqtt.publish`
   service, so it only happens after Home Assistant has seen the original
   names) and waits until the rename is reflected - the *same* registry
   device, with the *same* entity unique ids, now called `Hallway/Motion
   Sensor` - and `New Sensor` exists with its entities and a usable
   link-quality state.
3. **Network map** - `POST /api/zigsight/topology/networkmap` (admin) and
   waits until the topology's links come from the replay's network map.
4. **Soak** - keeps the stack running until 90 s after the entry loaded
   (`--soak` / `E2E_SOAK_SECONDS`) so more rounds and availability flaps
   reach Home Assistant, then re-checks the device set.

Finally, `scripts/ci_check_ha_log.py` fails the run on any evidence of a
ZigSight bug in the Home Assistant log: ERROR/CRITICAL records mentioning
zigsight (including MQTT callback exceptions whose only zigsight mention is
the `custom_components/zigsight/...` path in the traceback, and "Error
adding entity ... with platform zigsight"), any traceback through
`custom_components/zigsight`, and any "Detected ... zigsight" report
(blocking calls in the event loop). A missing or empty log fails too.

### Running it

```bash
make e2e-up          # start HA + mosquitto + z2m-replay
make e2e-bootstrap   # onboard HA, configure MQTT/ZigSight, verify everything
make e2e-check-logs  # save logs to e2e-logs/, fail on ZigSight errors in HA's log
make e2e-down        # stop and remove the stack
make e2e             # all of the above; always tears the stack down (also
                     # when e2e-up fails) and exits non-zero if any step did
```

Default credentials, **local-only** (the container is thrown away by
`e2e-down`, and port 8123 is bound to 127.0.0.1): username `zigsight-e2e`,
password `ZigSight-e2e-local-only!2026`. Override with the
`E2E_HA_USERNAME` / `E2E_HA_PASSWORD` environment variables if needed.

Once `make e2e-up` is running you can also just open <http://localhost:8123>
in a browser and click around like a real installation - it's a real Home
Assistant, just fed by the replay tool instead of your Zigbee network. (The
rename/join scenario only runs when the bootstrap asks for it; publish
anything on `zigsight-e2e/replay/scenario` from Developer tools -> Actions
-> `mqtt.publish` to trigger it by hand.)

This is separate from the plain manual dev loop (`make start` /
`scripts/integration-test.sh`, no MQTT broker included) that's useful when
you just want to poke at the integration UI without a Zigbee2MQTT backend at
all; see the [Developer README](DEVELOPER_README.md).

### Replaying a capture from your own broker

Put a capture (see "Capturing real traffic" below - **read the warning
there first**) in `captures/` (git-ignored; mounted read-only at
`/work/captures` in the replay container), stop the default replay and run
the capture instead, on the same disposable broker:

```bash
make e2e-up
docker compose stop z2m-replay
docker compose run --rm z2m-replay \
  python scripts/z2m_replay.py --host mosquitto --capture-file /work/captures/capture.jsonl
```

Each run uses a unique MQTT client id. `bridge/state` gets the stopped
replay's retained `offline`, so the capture replay is allowed to take over
(see the safety check below). Without a `bridge/devices` message in the
capture there is nothing to rename; the scenario renames the first device
that sent a state to `<name> (renamed)` otherwise.

### Safety checks in the replay tool

`scripts/z2m_replay.py` publishes, so it guards against being pointed at the
wrong broker:

- `--host` is mandatory - there is no default (not even localhost, not even
  from the environment);
- before publishing anything it listens ~2 s on `<prefix>/bridge/state` and
  **refuses to start** if a retained `online` is there - a live
  Zigbee2MQTT (or another replay) owns that base topic on this broker. It
  never overwrites it (the probe connection has no last will). Use a
  disposable broker such as the compose one.

## 4. Trying it against your real Zigbee2MQTT (read-only capture)

The environment above uses synthetic/recorded data. To validate against your
own real devices without risking your production setup, capture traffic
**read-only** from your production broker, as JSON lines:

```bash
mkdir -p captures
mosquitto_sub -h <broker> -u <user> -P <password> -F '%j' -t 'zigbee2mqtt/#' -C 2000 > captures/capture.jsonl
```

`-C 2000` stops after 2000 messages so this doesn't run forever; adjust to
taste. This only *subscribes* - it never publishes anything back to your
broker, so it cannot affect your running Zigbee2MQTT/Home Assistant.

Supported capture formats (auto-detected from the first line):

- **JSON lines** (`-F '%j'`, recommended): one JSON object per message
  with `topic`, `payload` and `retain`. Friendly names with spaces (e.g.
  `Living Room Lamp`) survive, and the real retain flag is kept.
- **Tab-separated** (`-F '%t\t%p'`): also safe with spaces in names; the
  retain flag is guessed from the topic (`bridge/state|info|devices|groups|
  extensions`, `*/availability`).
- **Legacy verbose** (`-v`, `<topic> <payload>`): ambiguous as soon as a
  name contains a space. Parsed with a heuristic - split before the payload
  when it is JSON (`{`/`[`), otherwise at the last space - which is wrong
  for a plain-text payload that itself contains a space. Only for old
  captures.

While loading a capture, `tests/z2m_replay.py`:

- redacts, recursively and by key name (case-insensitive), `network_key`,
  `password`, `auth_token`, `install_code`, `ext_pan_id`,
  `extended_pan_id`, `pan_id`, `user` and `username` in **every** `bridge/*` JSON payload;
- drops `bridge/request/*` and every `bridge/response/*` except
  `bridge/response/networkmap`, and all `/set` and `/get` command topics.

!!! warning "Never commit a raw capture"
    The raw capture file on disk is **not** redacted: its `bridge/info`
    message contains your Zigbee **network key** and the **MQTT
    credentials** Zigbee2MQTT was configured with. Keep it in `captures/`
    (git-ignored, as are `capture*.txt|jsonl|tsv` anywhere), don't attach it
    to an issue or PR, and delete it once you're done. There is no tool
    that writes a redacted copy: if you want to turn parts of a capture into
    a fixture for `tests/fixtures/z2m/`, write the fixture by hand,
    anonymise names/IEEE addresses, and review the diff before committing.

Once you have a capture, either:

- replay it locally on the compose broker, as shown in "Replaying a capture
  from your own broker" above; or
- point a **spare** Home Assistant instance (not your production one) at
  your production broker directly, in read-only fashion, by giving it a
  Zigbee2MQTT base topic and MQTT user that only has subscribe permissions
  if your broker supports per-user ACLs. Either way, never point a test
  instance at your production broker with a Zigbee2MQTT user that can
  *publish* - ZigSight itself only publishes the network map request, but
  this is about limiting blast radius from anything else running on that
  Home Assistant instance during testing. And never run the replay tool
  against your production broker.

## CI

`.github/workflows/integration-test.yaml` runs the full compose + bootstrap
+ log-gate flow described in layer 3 on every pull request, against the
pinned minimum Home Assistant version (read from `docker-compose.yml`) and
`latest`. The `latest` leg is `continue-on-error`: a failure there is still
reported as a red job, but doesn't block the PR (a new Home Assistant
release can break things unrelated to the change). Manual dispatch takes an
optional `ha_version` input (validated, passed via the environment) to test
one specific release. Home Assistant/Mosquitto/replay logs are uploaded as a
build artifact on failure.
