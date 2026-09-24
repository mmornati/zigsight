# Zigbee2MQTT Integration

This guide explains how to configure ZigSight with Zigbee2MQTT.

## Overview

[Zigbee2MQTT](https://www.zigbee2mqtt.io/) is a popular open-source Zigbee bridge that uses MQTT for communication. ZigSight listens to the messages Zigbee2MQTT publishes to collect device data, compute analytics, and provide network visualization.

ZigSight does **not** connect to the MQTT broker itself: it uses Home Assistant's own [MQTT integration](https://www.home-assistant.io/integrations/mqtt/). There are no broker, port, username or password settings in ZigSight.

## Prerequisites

Before configuring ZigSight with Zigbee2MQTT, ensure you have:

- **Zigbee2MQTT** installed and running
- **Home Assistant's MQTT integration** set up and connected to the same broker Zigbee2MQTT publishes to (for the Home Assistant OS add-ons this is usually the Mosquitto add-on, `core-mosquitto`)
- Devices paired with your Zigbee2MQTT instance

Recommended (see [Analytics](../analytics.md#connectivity-warning)):

- [Device availability](https://www.zigbee2mqtt.io/guide/configuration/device-availability.html) enabled in Zigbee2MQTT, so ZigSight can detect offline devices and count reconnects
- `advanced.last_seen` enabled (any format: `ISO_8601`, `ISO_8601_local` or `epoch`) so ZigSight uses the time Zigbee2MQTT last heard from a device

## Configuration

### Step 1: Add ZigSight Integration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "ZigSight"
4. Select **Zigbee2MQTT** as the integration type

If the MQTT integration is not set up, the flow stops with "The MQTT integration is not set up": set up MQTT first, then add ZigSight again.

### Step 2: Zigbee2MQTT base topic

| Field | Description | Example |
|-------|-------------|---------|
| Zigbee2MQTT base topic | `mqtt.base_topic` from the Zigbee2MQTT configuration | `zigbee2mqtt` |

### Step 3: Configure Analytics (Optional)

Customize the analytics thresholds (they can be changed later with **Configure** on the integration):

| Setting | Description | Default |
|---------|-------------|---------|
| Battery Drain Threshold | Minimum drain rate (%/hour) to trigger warning | 10.0 |
| Reconnect Rate Threshold | Maximum reconnect rate (events/hour) before warning | 5.0 |
| Reconnect Rate Window | Time window in hours for calculations | 24 |

Only one ZigSight instance can be configured.

## How It Works

### MQTT topics

ZigSight subscribes to `<base_topic>/#` and interprets:

| Topic | Use |
|-------|-----|
| `<base_topic>/bridge/devices` | Authoritative device list (retained): IEEE address, friendly name, type (Router / EndDevice), model, vendor, power source, disabled flag |
| `<base_topic>/bridge/info` | Zigbee2MQTT version, coordinator, network channel / PAN id, availability configuration. Only these fields are kept; the Zigbee2MQTT configuration it also contains (MQTT credentials, network key) is ignored |
| `<base_topic>/bridge/state` | Bridge online/offline (JSON or legacy plain text) |
| `<base_topic>/bridge/response/networkmap` | Raw network map (only when requested; not requested periodically because a network scan creates a lot of Zigbee traffic) |
| `<base_topic>/<friendly_name>` | Device state (link quality, battery, voltage, last seen). Partial updates are merged with the previous values |
| `<base_topic>/<friendly_name>/availability` | Device availability (`{"state":"online"}` or legacy `online`) |

Friendly names containing `/` (e.g. `Kitchen/Motion Sensor`) are supported. Command topics (`/set`, `/get`), groups and any other topics are ignored.

### Devices and entities

- Every enabled, non-coordinator device from `bridge/devices` becomes a device in Home Assistant, identified by its **IEEE address**, named after its Zigbee2MQTT friendly name, with model and manufacturer from Zigbee2MQTT. All devices are linked to a "Zigbee2MQTT bridge" service device.
- Devices paired later get their entities automatically once Zigbee2MQTT has finished interviewing them (before that their power source and features are unknown). Devices whose interview FAILED still get the base entities (link quality, reconnect rate, health score, connectivity warning). If a device later gains a feature (e.g. a battery or voltage expose after a Zigbee2MQTT update), the missing entities are added; if it loses one (e.g. re-interviewed as mains powered), the corresponding entities are removed.
- Devices removed from Zigbee2MQTT are removed from Home Assistant, including devices removed while Home Assistant was not running (checked against the first device list after start-up). A device list without any device (e.g. a stale retained `[]`) is ignored rather than deleting everything.
- Renaming a device in Zigbee2MQTT renames the Home Assistant device (entity ids are kept).
- Devices disabled in Zigbee2MQTT get no entities (existing ones become unavailable).
- Stale ZigSight devices can be deleted from the device page.

These are separate from the devices Zigbee2MQTT itself creates through MQTT discovery.

## Entities Created

Entity ids are derived from the friendly name, e.g. `sensor.kitchen_motion_sensor_health_score` for `Kitchen/Motion Sensor`. Unique ids are `<ieee_address>_<key>`.

### Sensors

| Entity | Created for | Unit |
|--------|-------------|------|
| `sensor.<device>_link_quality` | all devices | LQI (0-255) |
| `sensor.<device>_reconnect_rate` | all devices | events/h |
| `sensor.<device>_health_score` | all devices | 0-100 |
| `sensor.<device>_battery` | battery powered devices | % |
| `sensor.<device>_battery_trend` | battery powered devices | %/h |
| `sensor.<device>_voltage` | devices exposing `voltage` | mV (or V, as declared by the device definition) |

### Binary Sensors

| Entity | Created for |
|--------|-------------|
| `binary_sensor.<device>_connectivity_warning` | all devices |
| `binary_sensor.<device>_battery_drain_warning` | battery powered devices |

### Event

`zigsight_device_update` is fired when a device's availability changes, or when its battery / voltage changed and at least 60 seconds passed since the previous event for that device. Link quality changes alone (nearly every report) don't fire it, but the current link quality is included. Event data:

```yaml
device_id: "0x00158d0001a2b3c4"   # IEEE address
friendly_name: "Bedroom Climate"
source: zigbee2mqtt
available: true                   # null when availability is not enabled
metrics:
  link_quality: 72
  battery: 87
  voltage: 2985
  last_seen: "2026-09-24T08:15:32+00:00"
```

## Troubleshooting

### The integration can't be set up / "Retrying setup"

ZigSight waits for Home Assistant's MQTT integration. Check **Settings > Devices & Services > MQTT** is set up and connected; ZigSight retries automatically.

### Devices Not Appearing

1. **Verify the base topic**: it must match `mqtt.base_topic` in Zigbee2MQTT (usually `zigbee2mqtt`).
2. **Check the device list**: in **Settings > Devices & Services > MQTT > Configure**, listen to `zigbee2mqtt/bridge/devices`; Zigbee2MQTT publishes it retained.
3. **Review logs**: enable debug logging:

   ```yaml
   logger:
     logs:
       custom_components.zigsight: debug
   ```

4. **Diagnostics**: download the ZigSight diagnostics from the integration page.

### No reconnect rate / late connectivity warnings

Enable availability in Zigbee2MQTT. Without it ZigSight can't see reconnects, and only flags a device after it has been silent for 25 hours (ZigSight doesn't ping devices, so idle routers such as bulbs can't be distinguished from dead ones sooner).

### Missing Link Quality

Not all devices report link quality (LQI). This is normal for:

- The coordinator itself
- Some older or basic devices

## Capturing Zigbee2MQTT traffic for bug reports

A read-only capture of what Zigbee2MQTT publishes helps a lot:

```bash
mosquitto_sub -h <broker> -u <user> -P <password> -v -t 'zigbee2mqtt/#'
```

Remove anything you consider private before sharing it.

## Related Documentation

- [Zigbee2MQTT Official Documentation](https://www.zigbee2mqtt.io/)
- [ZigSight Analytics](../analytics.md)
- [ZigSight Automations](../automations.md)
