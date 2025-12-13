# Getting Started with ZigSight

ZigSight is a Home Assistant custom component that provides diagnostics and optimization tools for Zigbee networks.

## Installation

To install ZigSight, copy the `custom_components/zigsight/` directory into your Home Assistant `custom_components/` folder.

1. Navigate to your Home Assistant configuration directory (usually `.homeassistant/` or `config/`)
2. Create a `custom_components/` directory if it doesn't exist
3. Copy the entire `zigsight/` folder into `custom_components/`
4. Restart Home Assistant
5. Go to **Settings > Devices & Services** and click **Add Integration**
6. Search for "ZigSight" and follow the setup wizard

Your directory structure should look like this:

```text
config/
├── configuration.yaml
└── custom_components/
    └── zigsight/
        ├── __init__.py
        ├── manifest.json
        ├── config_flow.py
        └── ...
```

## Configuration

After installation, ZigSight can be configured through the Home Assistant UI via **Settings > Devices & Services**.

### Step 1: Select Integration Type

When adding the integration, you'll first choose your Zigbee coordinator:

- **Zigbee2MQTT**: If you use Zigbee2MQTT as your Zigbee bridge
- **ZHA**: If you use Home Assistant's native ZHA integration

### Step 2: Configure Integration-Specific Settings

**For Zigbee2MQTT:**

- **MQTT Broker**: Hostname or IP of your MQTT broker (leave as `localhost` to use Home Assistant's MQTT integration)
- **MQTT Port**: Port number (default: 1883)
- **MQTT Username/Password**: Optional, if your broker requires authentication
- **MQTT Topic Prefix**: Base topic for Zigbee2MQTT (default: `zigbee2mqtt`)

**For ZHA:**

- No additional configuration needed - ZigSight automatically detects your ZHA devices

### Step 3: Configure Analytics Settings (Optional)

Customize the analytics thresholds:

- **Battery Drain Threshold**: Minimum drain rate (%/hour) to trigger warning (default: 10.0)
- **Reconnect Rate Threshold**: Maximum reconnect rate (events/hour) before warning (default: 5.0)
- **Reconnect Rate Window**: Time window in hours for calculations (default: 24)
- **Reconnect Threshold**: Number of reconnections to track (default: 5)
- **Data Retention**: Number of days to keep device history (default: 30)

## Frontend Panel

ZigSight includes a comprehensive frontend panel accessible from the Home Assistant sidebar. The panel provides:

- **Device List**: View all discovered devices with key metrics
- **Device Details**: Detailed information and analytics for each device
- **Network Topology**: Visual representation of your Zigbee network
- **Analytics Dashboard**: Network health overview and insights
- **Channel Recommendation**: Wi-Fi interference analysis and channel recommendations

### Quick Setup

**Important**: In Home Assistant 2025+, panels must be registered manually. Follow these steps:

1. **Copy the panel file** to your `www` directory:

   **For HACS installations:**
   ```bash
   mkdir -p config/www/community/zigsight
   cp config/custom_components/zigsight/www/zigsight-panel.js config/www/community/zigsight/
   ```

   **For manual installations:**
   ```bash
   mkdir -p config/www/zigsight
   cp custom_components/zigsight/www/zigsight-panel.js config/www/zigsight/
   ```

2. **Add the panel configuration** to your `configuration.yaml`:

   **For HACS installations:**
   ```yaml
   panel_custom:
     - name: zigsight
       sidebar_title: ZigSight
       sidebar_icon: mdi:zigbee
       url_path: zigsight
       module_url: /local/community/zigsight/zigsight-panel.js
       require_admin: false
   ```

   **For manual installations:**
   ```yaml
   panel_custom:
     - name: zigsight
       sidebar_title: ZigSight
       sidebar_icon: mdi:zigbee
       url_path: zigsight
       module_url: /local/zigsight/zigsight-panel.js
       require_admin: false
   ```

3. **Restart Home Assistant**. The panel will appear in the sidebar.

**Note**: HACS doesn't automatically serve files from `custom_components/zigsight/www/`. You must copy the panel file to the `www` directory manually.

For complete setup instructions and troubleshooting, see [Frontend Panel Documentation](frontend_panel.md).

## What's Next?

After configuration, ZigSight will:

1. **Discover your devices** - Automatically detect all Zigbee devices from your coordinator
2. **Create sensors** - Generate health scores, reconnect rates, and battery trends for each device
3. **Monitor your network** - Track device connectivity and battery health
4. **Provide recommendations** - Use the Wi-Fi channel recommendation service to optimize your Zigbee channel

See the [Integrations](integrations/zigbee2mqtt.md) guides for detailed setup instructions for your specific coordinator.
