# ZHA Integration Support

ZigSight can collect device diagnostics and metrics from the Zigbee Home Automation (ZHA) integration in Home Assistant.

## Overview

When ZHA support is enabled, ZigSight automatically discovers ZHA devices and collects the following metrics:

- **Link Quality (LQI)**: Signal quality indicator (0-255)
- **RSSI**: Received Signal Strength Indicator (in dBm)
- **Last Seen**: Timestamp of last communication
- **Battery Level**: Battery percentage for battery-powered devices

These metrics are normalized to match the Zigbee2MQTT format, ensuring consistent monitoring regardless of your Zigbee integration.

## Enabling ZHA Support

### During Initial Setup

1. Go to **Settings > Devices & Services** in Home Assistant
2. Click **Add Integration** and search for "ZigSight"
3. In the configuration form, check the **Enable ZHA** option
4. Complete the rest of the configuration

### For Existing Installations

1. Go to **Settings > Devices & Services**
2. Find your ZigSight integration
3. Click **Configure**
4. Check the **Enable ZHA** option
5. Click **Submit**

## How It Works

### Device Discovery

ZigSight discovers ZHA devices through the following process:

1. **Integration Detection**: Checks if ZHA integration is loaded (`hass.data.get("zha")`)
2. **Gateway Access**: Accesses the ZHA gateway to retrieve device list
3. **Device Iteration**: Iterates through all paired ZHA devices
4. **Metric Collection**: Collects metrics from both device attributes and diagnostic entities

### Metric Sources

ZigSight collects metrics from two sources:

#### 1. Device Attributes

Metrics are read directly from ZHA device objects:
- `zha_device.lqi` → `link_quality`
- `zha_device.rssi` → `rssi`
- `zha_device.last_seen` → `last_seen`

#### 2. Diagnostic Entities

ZHA creates diagnostic entities for some devices:
- `sensor.<device>_rssi` → RSSI value
- `sensor.<device>_lqi` → Link quality value
- `sensor.<device>_battery` → Battery percentage

ZigSight reads these entities when available to supplement device attributes.

### Metric Normalization

ZHA metrics are normalized to match Zigbee2MQTT format:

| ZHA Metric | ZigSight Metric | Notes |
|------------|-----------------|-------|
| `lqi` (0-255) | `link_quality` | Direct mapping |
| `rssi` (dBm) | `rssi` | Direct mapping |
| `last_seen` | `last_seen` | ISO 8601 timestamp |
| Battery % | `battery` | Direct mapping |

## Fallback Behavior

If diagnostic entities are not available, ZigSight falls back to:

1. Reading device attributes directly
2. Using `datetime.now()` for `last_seen` if not available
3. Omitting metrics that cannot be determined

This ensures ZigSight works even when:
- ZHA hasn't created diagnostic entities
- Devices don't report all metrics
- Network connectivity is intermittent

## Permissions

ZigSight requires the following permissions to access ZHA:

- **Read access** to `hass.data["zha"]`
- **Read access** to Home Assistant device registry
- **Read access** to Home Assistant entity registry
- **Read access** to entity states

No special permissions or API keys are required. ZigSight uses standard Home Assistant APIs.

## Troubleshooting

### ZHA Devices Not Showing Up

1. **Verify ZHA is loaded**: Check that ZHA integration is configured and running
2. **Check ZigSight logs**: Look for ZHA-related errors in Home Assistant logs
3. **Enable debug logging**:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.zigsight.zha_collector: debug
   ```

### Missing Metrics

If some metrics are missing:

1. **Check device capabilities**: Not all devices report all metrics
2. **Verify diagnostic entities**: Some ZHA devices may not have diagnostic entities
3. **Check entity states**: Entities may be `unavailable` or `unknown`

### Performance Issues

If ZHA data collection impacts performance:

1. **Reduce update frequency**: Adjust the coordinator update interval
2. **Disable ZHA support**: If you only use Zigbee2MQTT, disable ZHA collection
3. **Check device count**: Large networks (100+ devices) may require tuning

## Limitations

### Current Limitations

- **No device commands**: ZigSight is read-only, it cannot control ZHA devices
- **No network map**: ZHA network topology is not currently collected
- **No routing table**: Routing information is not available through ZHA APIs

### ZHA API Stability

ZigSight uses public ZHA APIs where possible:
- Device registry API (stable)
- Entity registry API (stable)
- Entity state API (stable)
- ZHA gateway access (internal, may change)

If ZHA internals change in future Home Assistant releases, the collector may need updates.

## Comparison with Zigbee2MQTT

| Feature | Zigbee2MQTT | ZHA |
|---------|-------------|-----|
| Real-time updates | ✅ MQTT | ⏱️ Polling |
| Link quality | ✅ | ✅ |
| RSSI | ✅ | ✅ |
| Last seen | ✅ | ✅ |
| Battery | ✅ | ✅ |
| Network map | ✅ | ❌ |
| Routing table | ✅ | ❌ |

ZHA support in ZigSight provides core metrics but does not include all features available with Zigbee2MQTT.

## Examples

### Configuration Example

```yaml
# In Home Assistant UI configuration:
- Enable ZHA: true
- MQTT Broker: localhost (optional, for Zigbee2MQTT)
- MQTT Port: 1883 (optional)
```

### Using Both ZHA and Zigbee2MQTT

ZigSight can collect from both integrations simultaneously:

1. Enable ZHA support in ZigSight configuration
2. Configure MQTT settings for Zigbee2MQTT
3. ZigSight will merge devices from both sources

Devices are identified by IEEE address to avoid duplicates.

## Further Reading

- [ZHA Integration Documentation](https://www.home-assistant.io/integrations/zha/)
- [Home Assistant Device Registry](https://developers.home-assistant.io/docs/device_registry_index/)
- [ZigSight Developer README](../DEVELOPER_README.md)
