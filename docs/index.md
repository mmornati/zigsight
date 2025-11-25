# ZigSight

Welcome to **ZigSight**, a Home Assistant custom component that provides diagnostics and optimization tools for Zigbee networks.

## What is ZigSight?

ZigSight helps you monitor, analyze, and optimize your Zigbee network by providing:

- **Device Health Monitoring**: Track battery levels, connectivity, and link quality for all your Zigbee devices
- **Analytics Engine**: Compute metrics like reconnect rates, battery trends, and health scores
- **Wi-Fi Interference Analysis**: Get recommendations for the optimal Zigbee channel based on your Wi-Fi environment
- **Network Topology Visualization**: See your entire Zigbee network in an interactive dashboard card
- **Automation Blueprints**: Pre-built automations for common monitoring scenarios

## Features

### Device Analytics

ZigSight tracks key metrics for each device in your network:

- **Reconnect Rate**: How often devices disconnect and reconnect
- **Battery Trend**: Rate of battery drain over time
- **Health Score**: An aggregated health metric (0-100) combining multiple factors
- **Connectivity Warnings**: Alerts when devices have connectivity issues
- **Battery Drain Warnings**: Alerts when battery drain exceeds normal rates

### Wi-Fi Channel Recommendation

Zigbee and Wi-Fi both operate in the 2.4 GHz spectrum, which can cause interference. ZigSight can analyze your Wi-Fi environment and recommend the best Zigbee channel (11, 15, 20, or 25) to minimize interference.

### Network Topology Card

A custom Lovelace card displays your Zigbee network with:

- Device type indicators (coordinator, router, end device)
- Link quality visualization
- Health status indicators
- Interactive device details

### Automation Blueprints

Ready-to-use automation blueprints for:

- **Battery Drain Alerts**: Notify when device batteries are low
- **Reconnect Flap Alerts**: Detect devices with frequent disconnections
- **Daily Network Health Reports**: Get a daily summary of your network status

## Supported Integrations

ZigSight works with these Zigbee coordination solutions:

- [Zigbee2MQTT](integrations/zigbee2mqtt.md) - MQTT-based Zigbee bridge
- [ZHA](integrations/zha.md) - Zigbee Home Automation (native Home Assistant)
- [deCONZ](integrations/deconz.md) - Dresden Elektronik's Phoscon gateway

## Quick Start

1. **Install ZigSight** - Copy the integration to your `custom_components/` folder
2. **Configure** - Add the integration via Settings > Devices & Services
3. **Monitor** - View device health metrics and network topology
4. **Optimize** - Use Wi-Fi analysis to find the best Zigbee channel
5. **Automate** - Import blueprints for automatic monitoring

For detailed installation instructions, see the [Getting Started](getting_started.md) guide.

## Documentation

| Section | Description |
|---------|-------------|
| [Getting Started](getting_started.md) | Installation and initial setup |
| [Integrations](integrations/zigbee2mqtt.md) | Setting up Zigbee2MQTT, ZHA, or deCONZ |
| [Analytics](analytics.md) | Understanding device metrics and health scores |
| [Wi-Fi Recommendation](wifi_recommendation.md) | Channel optimization for minimal interference |
| [UI](ui.md) | Network topology visualization card |
| [Automations](automations.md) | Using the automation blueprints |
| [FAQ](faq.md) | Frequently asked questions |

## Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/mmornati/zigsight/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/mmornati/zigsight/discussions)

## License

ZigSight is licensed under the Apache 2.0 License. See the [LICENSE](https://github.com/mmornati/zigsight/blob/main/LICENSE) file for details.
