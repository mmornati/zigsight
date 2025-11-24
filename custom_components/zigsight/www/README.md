# ZigSight Lovelace Cards

This directory contains custom Lovelace cards for ZigSight.

## Included Cards

### topology-card.js

Network topology visualization card for displaying your Zigbee network structure.

## Installation

### Automatic (HACS)

If you installed ZigSight via HACS, the card files are already included in your installation.

### Manual Installation

1. Copy the card file to your Home Assistant `www` directory:

   ```bash
   mkdir -p config/www/community/zigsight
   cp custom_components/zigsight/www/topology-card.js config/www/community/zigsight/
   ```

2. Register the card as a Lovelace resource:

   **Option A: Via UI**
   - Go to **Settings** → **Dashboards** → **Resources** (three-dot menu)
   - Click **Add Resource**
   - URL: `/local/community/zigsight/topology-card.js`
   - Resource type: **JavaScript Module**

   **Option B: Via YAML**
   Add to your `configuration.yaml`:
   ```yaml
   lovelace:
     mode: yaml
     resources:
       - url: /local/community/zigsight/topology-card.js
         type: module
   ```

3. Add the card to your dashboard:

   ```yaml
   type: custom:zigsight-topology-card
   title: Zigbee Network Topology
   ```

## Usage

See [docs/ui.md](../../../docs/ui.md) for complete documentation on using the topology card.

## Features

- **Network Statistics**: Device counts by type (coordinator, routers, end devices)
- **Device Cards**: Interactive cards showing device status and metrics
- **Color Coding**: Visual indicators for device type and health
- **Link Quality**: Color-coded signal strength indicators
- **Device Details**: Click any device to see detailed information
- **Warnings**: Highlights devices with connectivity or battery issues
- **Manual Refresh**: Update topology data on demand

## Development

The card is written in vanilla JavaScript and requires no build process. To modify:

1. Edit `topology-card.js`
2. Copy updated file to your `www` directory
3. Clear browser cache
4. Refresh dashboard

See [docs/DEVELOPER_README.md](../../../docs/DEVELOPER_README.md) for more information.
