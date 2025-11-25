# ZHA Integration

This guide explains how to configure ZigSight with Zigbee Home Automation (ZHA).

## Overview

[ZHA](https://www.home-assistant.io/integrations/zha/) is Home Assistant's native Zigbee integration. It provides direct communication with Zigbee devices without requiring external bridges. ZigSight integrates with ZHA to provide enhanced analytics and monitoring capabilities.

## Prerequisites

Before configuring ZigSight with ZHA, ensure you have:

- **ZHA integration** configured and running in Home Assistant
- **Zigbee coordinator** connected (e.g., Sonoff Zigbee 3.0 USB, ConBee II, CC2652)
- Devices paired with your ZHA network
- Home Assistant 2025.10.0 or later

## Configuration

### Step 1: Add ZigSight Integration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "ZigSight"
4. Select **ZHA** as the integration type

### Step 2: Select ZHA Instance

If you have multiple ZHA instances (rare), select the one you want to monitor.

### Step 3: Configure Analytics (Optional)

Customize the analytics thresholds:

| Setting | Description | Default |
|---------|-------------|---------|
| Battery Drain Threshold | Minimum drain rate (%/hour) to trigger warning | 10.0 |
| Reconnect Rate Threshold | Maximum reconnect rate (events/hour) before warning | 5.0 |
| Reconnect Rate Window | Time window in hours for calculations | 24 |

## How It Works

### Device Discovery

ZigSight uses the ZHA device registry to discover devices. It accesses:

- Device entities from Home Assistant
- ZHA device attributes
- Device state changes via events

### Data Collected

For each device, ZigSight collects:

- **Device Name**: Friendly name from ZHA
- **Device Type**: Coordinator, Router, or EndDevice
- **IEEE Address**: Unique 64-bit device identifier
- **Link Quality (LQI)**: Signal strength (0-255) when available
- **Battery Level**: Current battery percentage
- **Last Seen**: Timestamp of last communication
- **Manufacturer**: Device manufacturer name
- **Model**: Device model identifier

### ZHA Events

ZigSight listens to ZHA events for real-time updates:

| Event | Usage |
|-------|-------|
| `zha_event` | Device interactions and updates |
| `device_registry_updated` | New/removed devices |
| `state_changed` | Entity state updates |

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

- **Battery**: Some mains-powered devices don't report battery
- **LQI**: Not all devices include link quality in updates
- **Last Seen**: May not update for sleeping devices

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
