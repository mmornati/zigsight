# Zigbee2MQTT Integration

This guide explains how to configure ZigSight with Zigbee2MQTT.

## Overview

[Zigbee2MQTT](https://www.zigbee2mqtt.io/) is a popular open-source Zigbee bridge that uses MQTT for communication. ZigSight integrates with Zigbee2MQTT to collect device data, compute analytics, and provide network visualization.

## Prerequisites

Before configuring ZigSight with Zigbee2MQTT, ensure you have:

- **Zigbee2MQTT** installed and running
- **MQTT broker** (Mosquitto or similar) configured
- **Home Assistant** with MQTT integration enabled
- Devices paired with your Zigbee2MQTT instance

## Configuration

### Step 1: Add ZigSight Integration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "ZigSight"
4. Select **Zigbee2MQTT** as the integration type

### Step 2: Configure MQTT Connection

Enter the following details:

| Field | Description | Example |
|-------|-------------|---------|
| MQTT Broker | MQTT broker hostname or IP. Leave as `localhost` to use Home Assistant's MQTT integration | `localhost` or `192.168.1.100` or `core-mosquitto` |
| MQTT Port | MQTT broker port | `1883` |
| MQTT Username | MQTT username (optional, if broker requires authentication) | `homeassistant` |
| MQTT Password | MQTT password (optional, if broker requires authentication) | `your_password` |
| MQTT Topic Prefix | Zigbee2MQTT base topic prefix | `zigbee2mqtt` |

**Note**: If you're using Home Assistant's built-in MQTT integration, leave the MQTT Broker as `localhost`. ZigSight will automatically use Home Assistant's MQTT connection. Only specify a different broker if you're using a separate MQTT instance.

### Step 3: Configure Analytics (Optional)

Customize the analytics thresholds:

| Setting | Description | Default |
|---------|-------------|---------|
| Battery Drain Threshold | Minimum drain rate (%/hour) to trigger warning | 10.0 |
| Reconnect Rate Threshold | Maximum reconnect rate (events/hour) before warning | 5.0 |
| Reconnect Rate Window | Time window in hours for calculations | 24 |

## How It Works

### Device Discovery

ZigSight subscribes to Zigbee2MQTT MQTT topics to discover devices:

```
zigbee2mqtt/bridge/devices      # Device list
zigbee2mqtt/+                   # Device state updates
zigbee2mqtt/bridge/state        # Bridge status
```

When Zigbee2MQTT publishes device updates, ZigSight processes the data and updates metrics.

### Data Collected

For each device, ZigSight collects:

- **Device Name**: Friendly name from Zigbee2MQTT
- **Device Type**: Coordinator, Router, or EndDevice
- **IEEE Address**: Unique device identifier
- **Link Quality (LQI)**: Signal strength (0-255)
- **Battery Level**: Current battery percentage
- **Last Seen**: Timestamp of last communication
- **Network Address**: Short network address

### MQTT Topics

ZigSight listens to these topics:

| Topic | Data |
|-------|------|
| `{topic_prefix}/bridge/devices` | Full device list with details |
| `{topic_prefix}/bridge/state` | Bridge online/offline status |
| `{topic_prefix}/{friendly_name}` | Device state updates |
| `{topic_prefix}/bridge/event` | Join/leave events |

Where `{topic_prefix}` is the MQTT Topic Prefix you configured (default: `zigbee2mqtt`).

## Entities Created

ZigSight creates sensors for each Zigbee device:

### Sensors

- `sensor.{device}_health_score` - Overall health (0-100)
- `sensor.{device}_reconnect_rate` - Reconnection frequency (events/hour)
- `sensor.{device}_battery_trend` - Battery drain rate (%/hour)

### Binary Sensors

- `binary_sensor.{device}_connectivity_warning` - Connectivity issue alert
- `binary_sensor.{device}_battery_drain_warning` - Battery drain alert

## Example Configuration

Here's a complete configuration example:

```yaml
# In Home Assistant, configure via UI:
# Settings > Devices & Services > Add Integration > ZigSight

# For reference, the configuration includes:
# - Integration Type: Zigbee2MQTT
# - MQTT Host: core-mosquitto (for Home Assistant Add-on)
# - MQTT Port: 1883
# - Base Topic: zigbee2mqtt
# - Battery Drain Threshold: 10.0
# - Reconnect Rate Threshold: 5.0
```

## Troubleshooting

### Devices Not Appearing

1. **Check MQTT connection**: Verify ZigSight can connect to your MQTT broker
   - If using Home Assistant's MQTT integration, ensure it's configured and running
   - If using a separate broker, verify the host, port, and credentials are correct
2. **Verify topic prefix**: Ensure the MQTT Topic Prefix matches your Zigbee2MQTT configuration (usually `zigbee2mqtt`)
3. **Check device list**: Verify Zigbee2MQTT is publishing to `{topic_prefix}/bridge/devices`
4. **Review logs**: Enable debug logging for `custom_components.zigsight`

### Incorrect Device Data

1. **Verify Zigbee2MQTT version**: Use a recent version for best compatibility
2. **Check device reporting**: Some devices don't report all attributes
3. **Wait for updates**: Metrics require time to accumulate data

### MQTT Connection Errors

```
Error connecting to MQTT broker
```

Solutions:

- Verify MQTT broker is running
- Check host/port configuration
- Verify username/password if authentication is required
- Check firewall settings

### Missing Link Quality

Not all devices report link quality (LQI). This is normal for:

- The coordinator itself
- Some older or basic devices

## Best Practices

### MQTT Broker Configuration

For best results:

- Use a dedicated MQTT user for ZigSight
- Enable persistent sessions if using QoS > 0
- Keep the MQTT broker on the same network as Home Assistant

### Topic Organization

If you have multiple Zigbee2MQTT instances:

- Use distinct topic prefixes (e.g., `zigbee2mqtt/home`, `zigbee2mqtt/garage`)
- Configure each Zigbee2MQTT instance with a different topic prefix
- Note: ZigSight currently supports one instance per Home Assistant installation

### Monitoring

- Review device health scores weekly
- Set up automation blueprints for alerts
- Use the topology card for network visualization

## Related Documentation

- [Zigbee2MQTT Official Documentation](https://www.zigbee2mqtt.io/)
- [ZigSight Analytics](../analytics.md)
- [ZigSight Automations](../automations.md)
