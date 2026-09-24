# Frequently Asked Questions

This page answers common questions about ZigSight.

## General

### What is ZigSight?

ZigSight is a Home Assistant custom component that provides diagnostics and optimization tools for Zigbee networks. It helps you monitor device health, analyze network performance, and optimize your Zigbee channel selection.

### Which Zigbee integrations does ZigSight support?

ZigSight currently supports:

- **Zigbee2MQTT** - MQTT-based Zigbee bridge
- **ZHA** - Zigbee Home Automation (native Home Assistant integration)

**deCONZ** support is planned for a future release.

### Is ZigSight available through HACS?

ZigSight can be installed as a custom repository through HACS. Add `https://github.com/mmornati/zigsight` as a custom repository in HACS.

## Installation

### How do I install ZigSight?

See the [Getting Started](getting_started.md) guide for detailed installation instructions. In brief:

1. Copy `custom_components/zigsight/` to your Home Assistant `custom_components/` directory
2. Restart Home Assistant
3. Add the integration via Settings > Devices & Services

### Does ZigSight require MQTT?

MQTT is required only if you use Zigbee2MQTT as your Zigbee coordinator. For ZHA, MQTT is not needed. If you're using Home Assistant's built-in MQTT integration, you can leave the MQTT Broker setting as `localhost` and ZigSight will use it automatically.

### What are the system requirements?

- Home Assistant 2025.10.0 or later
- Python 3.11 or later
- One of the supported Zigbee integrations configured

## Analytics

### How is the health score calculated?

The health score (0-100) is computed from four weighted factors:

- **Link Quality (30%)**: Signal strength normalized from 0-255 to 0-100
- **Battery (20%)**: Current battery level percentage
- **Reconnect Rate (30%)**: Inverted reconnect rate (lower is better)
- **Connectivity (20%)**: Based on how recently the device was seen

See the [Analytics](analytics.md) documentation for detailed algorithm explanations.

### Why does my device show "Unknown" for metrics?

This typically happens when:

- The device hasn't been seen recently
- There isn't enough historical data to compute metrics
- The device doesn't report the required attributes (e.g., battery level)

Wait for more data to accumulate, usually 24-48 hours after installation.

### Can I customize the health score weights?

Currently, the weights are fixed in code. Configurable weights may be added in a future release.

### What is a normal reconnect rate?

- **Excellent**: < 0.5 events/hour
- **Good**: 0.5 - 2 events/hour
- **Fair**: 2 - 5 events/hour
- **Poor**: > 5 events/hour

High reconnect rates may indicate interference, weak signal, or device issues.

## Wi-Fi Recommendations

### How do I get a channel recommendation?

Use the `zigsight.recommend_channel` service with one of three modes:

1. **Manual**: Upload Wi-Fi scan data you've collected
2. **Router API**: Query your router directly (limited router support)
3. **Host Scan**: Scan using your Home Assistant host's Wi-Fi adapter

See [Wi-Fi Recommendation](wifi_recommendation.md) for detailed instructions.

### Which Zigbee channels should I use?

ZigSight recommends from channels **11, 15, 20, and 25** because they provide the best spacing from common Wi-Fi channels (1, 6, 11).

### How often should I check for interference?

We recommend running a Wi-Fi scan periodically, especially if:

- You notice increased device disconnections
- Your neighbors have set up new Wi-Fi networks
- You've changed your own Wi-Fi configuration

### Is changing the Zigbee channel safe?

Changing channels requires all devices to rejoin the network. Most devices will rejoin automatically within 10-15 minutes, but some battery devices may take longer. Always:

1. Backup your Zigbee network configuration first
2. Schedule the change during a low-activity period
3. Monitor devices for successful rejoining

## UI and Visualization

### What's the difference between the Frontend Panel and the Topology Card?

ZigSight provides two UI components:

- **Frontend Panel**: A full-screen panel accessible from the Home Assistant sidebar. Provides comprehensive device management, topology visualization, analytics dashboard, and channel recommendations. See [Frontend Panel Documentation](frontend_panel.md).

- **Topology Card**: A Lovelace dashboard card for embedding in your dashboards. Provides a quick network overview. See [UI Documentation](ui.md).

### How do I add the topology card?

1. Register the card as a Lovelace resource (see [UI documentation](ui.md))
2. Add `type: custom:zigsight-topology-card` to your dashboard

### How do I enable the frontend panel?

1. Add the panel configuration to `configuration.yaml` (see [Frontend Panel Documentation](frontend_panel.md))
2. Restart Home Assistant
3. Access "ZigSight" from the sidebar

### The topology card shows "No data" - what's wrong?

Check that:

- ZigSight integration is properly configured and running
- Your Zigbee coordinator is connected and responding
- The API endpoint `/api/zigsight/topology` returns data (test in browser)

### Can I see a graph visualization of my network?

The current version shows devices as cards. A graph/tree visualization using D3.js or vis-network is planned for a future release.

## Automations

### How do I import the blueprints?

1. Go to **Settings** → **Automations & Scenes** → **Blueprints**
2. Click **Import Blueprint**
3. Paste the blueprint URL from the [Automations](automations.md) documentation

### Can I customize the blueprint thresholds?

Yes! When you create an automation from a blueprint, you can customize all the input values including thresholds, notification services, and cooldown periods.

### How do I get notifications on my phone?

Set the `notify_service` input to your mobile app notification service, e.g., `notify.mobile_app_your_phone`. Make sure the Home Assistant Companion app is installed and configured.

## Troubleshooting

### ZigSight isn't detecting my devices

Check that:

1. Your Zigbee coordinator (Zigbee2MQTT or ZHA) is working correctly
2. Devices are visible in your coordinator's interface
3. The ZigSight integration is configured for the correct coordinator type

### I'm getting errors in the Home Assistant logs

Enable debug logging for more details:

```yaml
logger:
  default: info
  logs:
    custom_components.zigsight: debug
```

Then check the logs for specific error messages.

### Metrics aren't updating

Metrics are computed based on device history. If metrics aren't updating:

1. Verify devices are actively sending data
2. Check coordinator connectivity
3. Restart the ZigSight integration

### How do I report a bug?

Open an issue on [GitHub](https://github.com/mmornati/zigsight/issues) with:

- Home Assistant version
- ZigSight version
- Zigbee coordinator type and version
- Steps to reproduce the issue
- Relevant log entries

## Contributing

### How can I contribute to ZigSight?

See the [Developer README](DEVELOPER_README.md) for development setup and contribution guidelines. We welcome:

- Bug reports and feature requests
- Documentation improvements
- Code contributions

### Where can I get help?

- **Documentation**: Start with this FAQ and the linked guides
- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For general questions and community support
