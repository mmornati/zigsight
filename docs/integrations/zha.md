# ZHA Integration

This guide explains how to configure ZigSight with Zigbee Home Automation (ZHA).

## Overview

[ZHA](https://www.home-assistant.io/integrations/zha/) is Home Assistant's native Zigbee integration. It provides direct communication with Zigbee devices without requiring external bridges. ZigSight integrates with ZHA to provide enhanced analytics and monitoring capabilities.

## Prerequisites

Before configuring ZigSight with ZHA, ensure you have:

- **ZHA integration** configured and running in Home Assistant (the
  ZigSight config flow aborts with a clear error if no ZHA config entry
  exists yet; if ZHA is configured but not loaded yet when Home Assistant
  starts, ZigSight retries its own setup automatically until ZHA is ready)
- **Zigbee coordinator** connected (e.g., Sonoff Zigbee 3.0 USB, ConBee II, CC2652)
- Devices paired with your ZHA network
- Home Assistant 2025.10.0 or later

## Configuration

### Step 1: Add ZigSight Integration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "ZigSight"
4. Select **ZHA** as the integration type

### Step 2: Configure Analytics (Optional)

Customize the analytics thresholds:

| Setting | Description | Default |
|---------|-------------|---------|
| Battery Drain Threshold | Minimum drain rate (%/hour) to trigger warning | 10.0 |
| Reconnect Rate Threshold | Maximum reconnect rate (events/hour) before warning | 5.0 |
| Reconnect Rate Window | Time window in hours for calculations | 24 |
| Reconnect Threshold | Number of reconnections to track | 5 |
| Data Retention | Number of days to keep device history | 30 |

## How It Works

### Device Discovery

ZigSight never reads ZHA's internal runtime data (it used to, and that
broke every time ZHA changed its internals). Instead it only uses Home
Assistant's public device and entity registries:

- **Devices**: every Home Assistant device with a `("zha", <ieee>)`
  identifier that belongs to a *loaded* ZHA config entry. Name
  (`name_by_user` if set, otherwise `name`), manufacturer and model come
  straight from the device registry entry.
- **Diagnostic entities**: for each device, ZigSight looks up its LQI
  (link quality) and RSSI sensors (`sensor` entities with `translation_key`
  `lqi` / `rssi`) and its battery sensor (`device_class` `battery`).

### Data Collected

For each device, ZigSight collects:

- **Device Name / Manufacturer / Model**: from the device registry.
- **Link Quality (LQI)**: read from ZHA's LQI diagnostic sensor, when enabled.
- **RSSI**: read from ZHA's RSSI diagnostic sensor, when enabled.
- **Battery Level**: read from ZHA's battery sensor, when the device has one.
- **Availability**: a device is considered available as soon as any one of
  its tracked diagnostic entities reports a value, and unavailable once
  *all* of them report Home Assistant's `unavailable` state (which is what
  happens when the underlying Zigbee device drops off the network).
  Reconnects are only counted on the unavailable -> available transition,
  never once per update. A state marked `restored` (the stub Home
  Assistant writes for an entity that is briefly unloaded, e.g. while ZHA
  reloads) is ignored entirely -- it never counts as unavailable, so a ZHA
  reload never looks like a device dropping offline and reconnecting.

**Not currently collected**: ZHA does not expose a "last seen" sensor
entity, and neither the device registry nor its entities expose the Zigbee
power source / device type (router vs. end device) -- those only exist on
ZHA's private runtime objects, which ZigSight does not read. `last_seen` is
therefore approximated from a tracked entity's own `last_reported` /
`last_updated` timestamp, and only ever advances from a live state-change
push -- never from the periodic registry re-discovery -- so a device that
truly stops reporting still goes stale and can trigger the connectivity
warning. Device type is reported as `unknown` for ZHA devices. Both may be
revisited in a future release if a registry-exposed source for that
information becomes available.

### Live updates

Home Assistant reload (start-up) and the coordinator's periodic refresh
re-discover devices and entities from the registries as a safety net (only
resubscribing if the tracked entity set actually changed, so this doesn't
churn on every refresh); device/entity registry update events (debounced)
trigger the same re-discovery immediately, so newly joined/removed ZHA
devices and newly enabled diagnostic entities are picked up without
waiting for the next periodic refresh. In between, state changes of the
tracked LQI/RSSI/battery entities are delivered live (event driven, via
`async_track_state_change_event`) instead of being polled on a fixed
interval. A ZHA device no longer present in a refresh (unpaired/removed
from ZHA) is dropped from ZigSight too, and can then be deleted from the
Home Assistant UI.

### LQI/RSSI sensors are disabled by default

ZHA creates the LQI and RSSI sensors for every device, but disables them by
default (they are diagnostic entities). ZigSight can still collect a
device's link quality/RSSI once they are enabled. Two ways to enable them:

1. **Manually**: open the entity in **Settings > Devices & Services >
   Entities**, and enable it.
2. **ZigSight's service**: call `zigsight.enable_zha_diagnostic_entities`
   (Developer Tools > Actions) to enable every LQI/RSSI sensor that is
   still disabled by its default across all ZHA devices in one call. It
   never re-enables an entity a user explicitly disabled themselves, and
   returns the number and ids of the entities it enabled. Home Assistant
   reloads the ZHA config entry ~30 seconds afterwards
   (`homeassistant.config_entries.RELOAD_AFTER_UPDATE_DELAY`) to create the
   newly enabled entities.

While any LQI/RSSI sensor is still disabled by default, ZigSight raises a
repair issue ("ZHA LQI/RSSI sensors are disabled", **Settings > System >
Repairs**) pointing at the service above; the issue clears automatically
once every such sensor is enabled.

## Entities Created

ZigSight creates sensors for each Zigbee device:

### Sensors

- `sensor.{device}_health_score` - Overall health (0-100)
- `sensor.{device}_reconnect_rate` - Reconnection frequency (events/hour)
- `sensor.{device}_battery_trend` - Battery drain rate (%/hour)

### Binary Sensors

- `binary_sensor.{device}_connectivity_warning` - Connectivity issue alert
- `binary_sensor.{device}_battery_drain_warning` - Battery drain alert

## Channel Recommendation

ZHA supports channel changes directly in Home Assistant. To optimize your channel:

1. Run the ZigSight Wi-Fi scan service
2. Get the recommended channel
3. In Home Assistant, go to **Settings** > **Devices & Services** > **ZHA**
4. Click **Configure** > **Change channel**
5. Enter the recommended channel

See [Wi-Fi Recommendation](../wifi_recommendation.md) for detailed instructions.

## Troubleshooting

### Devices Not Appearing

1. **Verify ZHA is running**: Check the ZHA integration status
2. **Check device pairing**: Ensure devices are paired in ZHA
3. **Restart integration**: Try removing and re-adding ZigSight
4. **Review logs**: Enable debug logging for `custom_components.zigsight`

### Missing Device Attributes

Some devices don't report all attributes:

- **Battery**: Some mains-powered devices don't have a battery sensor
- **LQI / RSSI**: still disabled by default -- see
  [LQI/RSSI sensors are disabled by default](#lqirssi-sensors-are-disabled-by-default)
- **Last Seen**: approximated from the last tracked-entity state change (see
  [Data Collected](#data-collected)); not a live ZHA "last seen" value

### Device Shows Offline

1. Check if the device is within range of a router
2. Verify the device has battery (if applicable)
3. Try pressing a button on the device to wake it
4. Check ZHA logs for communication errors

### Health Score Seems Wrong

The health score uses multiple factors. Check individual components:

- View `sensor.{device}_reconnect_rate` for connectivity issues
- Check battery level directly
- Review link quality in ZHA device info

## Best Practices

### Coordinator Placement

- Place the coordinator centrally in your home
- Keep it away from USB 3.0 devices (interference)
- Elevate it if possible for better coverage

### Router Distribution

- Add mains-powered devices (routers) throughout your space
- Routers extend the network and improve reliability
- Good router coverage reduces reconnection issues

### Regular Maintenance

- Check device health scores weekly
- Replace batteries in devices with drain warnings
- Re-interview devices that show persistent issues

## ZHA-Specific Features

### Device Interview

If a device is misbehaving:

1. Go to **Settings** > **Devices & Services** > **ZHA**
2. Click on the problematic device
3. Select **Reconfigure Device** to re-interview

### Network Visualization

ZHA provides its own network visualization:

1. Go to **Settings** > **Devices & Services** > **ZHA**
2. Click **Configure**
3. Select **Visualize** to see the network graph

This complements ZigSight's topology card with additional route information.

## Related Documentation

- [ZHA Official Documentation](https://www.home-assistant.io/integrations/zha/)
- [ZigSight Analytics](../analytics.md)
- [ZigSight Wi-Fi Recommendation](../wifi_recommendation.md)
- [ZigSight Automations](../automations.md)
