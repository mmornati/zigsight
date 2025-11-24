# ZigSight UI - Network Topology Visualization

This document describes how to use the ZigSight Network Topology card to visualize your Zigbee network.

## Overview

The ZigSight Network Topology card provides an interactive visualization of your Zigbee network, showing:

- **Coordinator**: The Zigbee coordinator (typically your Zigbee2MQTT bridge)
- **Routers**: Devices that can route messages (typically powered devices)
- **End Devices**: Battery-powered devices that don't route messages
- **Link Quality**: Visual indicators for signal strength between devices
- **Device Health**: Health scores and warnings for problematic devices

## Installation

### Step 1: Add the Custom Card Resource

The topology card is automatically included with ZigSight. To use it, you need to register it as a Lovelace resource.

#### Option A: Using the UI (Recommended)

1. Navigate to **Settings** → **Dashboards** → **Resources** (click the three-dot menu in the top right)
2. Click **Add Resource**
3. Enter the URL: `/local/community/zigsight/topology-card.js`
4. Set Resource type to **JavaScript Module**
5. Click **Create**

#### Option B: Using YAML Configuration

Add the following to your `configuration.yaml`:

```yaml
lovelace:
  mode: yaml
  resources:
    - url: /local/community/zigsight/topology-card.js
      type: module
```

**Note**: You'll need to copy the `topology-card.js` file from `custom_components/zigsight/www/` to your `www/community/zigsight/` directory:

```bash
mkdir -p config/www/community/zigsight
cp custom_components/zigsight/www/topology-card.js config/www/community/zigsight/
```

### Step 2: Add the Card to Your Dashboard

#### Using the UI

1. Open the dashboard where you want to add the card
2. Click **Edit Dashboard** (three-dot menu → **Edit Dashboard**)
3. Click **Add Card**
4. Search for "ZigSight Network Topology"
5. Click to add the card

#### Using YAML

Add the following to your dashboard configuration:

```yaml
type: custom:zigsight-topology-card
title: Zigbee Network Topology
```

## Configuration Options

The topology card supports the following configuration options:

```yaml
type: custom:zigsight-topology-card
title: My Zigbee Network        # Optional: Custom title (default: "Zigbee Network Topology")
```

### Available Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `title` | string | "Zigbee Network Topology" | Card title displayed in the header |

## Understanding the Visualization

### Network Statistics

At the top of the card, you'll see statistics about your network:

- **Total Devices**: Total number of devices in your network
- **Coordinator**: Number of coordinators (typically 1)
- **Routers**: Number of router devices
- **End Devices**: Number of battery-powered end devices

### Device Cards

Each device is displayed as a card with the following information:

- **Device Name**: Friendly name of the device
- **Device Type**: Coordinator, Router, or End Device
- **Link Quality (LQI)**: Signal strength indicator (0-255)
  - 🟢 Green (200-255): Excellent
  - 🟡 Yellow-Green (150-199): Good
  - 🟠 Orange (100-149): Fair
  - 🔴 Red (0-99): Poor
- **Battery**: Battery percentage (if applicable)
- **Health Score**: Overall device health (0-100)

### Color Legend

- **Blue border**: Coordinator
- **Green border**: Router
- **Orange border**: End Device
- **Red border**: Device with warnings (connectivity or battery issues)

### Device Details Dialog

Click on any device card to open a detailed dialog showing:

- Device type and friendly name
- Link quality
- Battery level (if applicable)
- Health score
- Reconnect rate
- Last seen timestamp
- Active warnings

## API Endpoint

The card fetches topology data from the following API endpoint:

```
GET /api/zigsight/topology
```

This endpoint returns JSON data with the following structure:

```json
{
  "nodes": [
    {
      "id": "device_id",
      "label": "Friendly Name",
      "type": "coordinator|router|end_device",
      "link_quality": 255,
      "battery": 80,
      "last_seen": "2024-01-01T12:00:00Z",
      "health_score": 85.0,
      "analytics": {
        "reconnect_rate": 0.5,
        "battery_trend": -0.1,
        "battery_drain_warning": false,
        "connectivity_warning": false
      }
    }
  ],
  "edges": [
    {
      "from": "parent_device_id",
      "to": "child_device_id",
      "link_quality": 150
    }
  ],
  "device_count": 10,
  "coordinator_count": 1,
  "router_count": 3,
  "end_device_count": 6
}
```

## Troubleshooting

### Card Not Loading

1. **Check Resource Registration**: Ensure the card is properly registered in Lovelace resources
2. **Check File Location**: Verify `topology-card.js` is in the correct location
3. **Clear Browser Cache**: Try clearing your browser cache or opening in incognito mode
4. **Check Browser Console**: Open browser developer tools (F12) and check for JavaScript errors

### No Data Displayed

1. **Check ZigSight Integration**: Ensure ZigSight integration is properly configured
2. **Check MQTT Connection**: Verify Zigbee2MQTT is running and connected
3. **Check API Endpoint**: Try accessing `/api/zigsight/topology` directly in your browser
4. **Check Logs**: Review Home Assistant logs for any ZigSight errors

### Incorrect Device Information

1. **Refresh the Card**: Click the "Refresh" button in the card header
2. **Restart Integration**: Restart the ZigSight integration from Settings → Devices & Services
3. **Check Zigbee2MQTT**: Ensure your Zigbee2MQTT instance is providing correct device data

## Advanced Usage

### Multiple Networks

If you have multiple Zigbee networks (multiple coordinators), the API endpoint will return data from the first configured ZigSight instance. To visualize multiple networks, you can:

1. Add multiple instances of the card
2. Configure each ZigSight integration with a unique identifier
3. (Future feature) Use a `coordinator_id` configuration option to specify which network to display

### Custom Styling

The card uses Home Assistant's theme variables for styling. You can customize the appearance by:

1. Using a custom Home Assistant theme
2. Adding custom CSS using `card-mod` (community plugin)

Example with `card-mod`:

```yaml
type: custom:zigsight-topology-card
title: My Network
card_mod:
  style: |
    .card {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
```

## Examples

### Basic Configuration

```yaml
type: custom:zigsight-topology-card
```

### Custom Title

```yaml
type: custom:zigsight-topology-card
title: Living Room Zigbee Network
```

### In a Vertical Stack

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      ## Network Overview
      Monitor your Zigbee network health and topology.
  
  - type: custom:zigsight-topology-card
    title: Zigbee Network
  
  - type: entities
    entities:
      - sensor.zigsight_network_health
      - sensor.zigsight_device_count
```

## Integration with Other Cards

The topology card works well alongside other ZigSight sensors and cards:

```yaml
type: horizontal-stack
cards:
  - type: custom:zigsight-topology-card
    title: Network Topology
  
  - type: vertical-stack
    cards:
      - type: gauge
        entity: sensor.zigsight_network_health
        name: Network Health
        min: 0
        max: 100
      
      - type: entities
        entities:
          - sensor.zigsight_coordinator
          - sensor.zigsight_routers
          - sensor.zigsight_end_devices
```

## Frequently Asked Questions

### Q: Can I see the actual network graph/tree visualization?

A: The current version displays devices as cards for better readability on mobile devices. A future version may include an interactive graph visualization using libraries like vis-network or D3.js.

### Q: Can I filter devices by type?

A: This feature is planned for a future release. For now, device cards are color-coded by type.

### Q: How often is the topology data refreshed?

A: The topology data is loaded when the card is first displayed. Click the "Refresh" button to manually update. Automatic refresh every 60 seconds can be added if needed.

### Q: Can I export the topology data?

A: You can access the raw JSON data by visiting `/api/zigsight/topology` in your browser. Copy and save the JSON response for analysis or backup.

## See Also

- [Getting Started Guide](getting_started.md)
- [Analytics Documentation](analytics.md)
- [Wi-Fi Recommendations](wifi_recommendation.md)
- [Developer README](DEVELOPER_README.md)
