# ZigSight Lovelace Cards

This directory contains custom Lovelace cards for ZigSight.

## Included Cards

### topology-card.js

Network topology visualization card for displaying your Zigbee network structure.

### zigsight-panel.js

Comprehensive device list panel with advanced filtering, sorting, search, bulk actions, and pagination for managing large Zigbee networks.

## Installation

### Automatic (HACS)

If you installed ZigSight via HACS, the card files are already included in your installation.

### Manual Installation

1. Copy the card files to your Home Assistant `www` directory:

   ```bash
   mkdir -p config/www/community/zigsight
   cp custom_components/zigsight/www/topology-card.js config/www/community/zigsight/
   cp custom_components/zigsight/www/zigsight-panel.js config/www/community/zigsight/
   ```

2. Register the card as a Lovelace resource:

   **Option A: Via UI**
   - Go to **Settings** → **Dashboards** → **Resources** (three-dot menu)
   - Click **Add Resource**
   - URL: `/local/community/zigsight/topology-card.js`
   - Resource type: **JavaScript Module**
   - Repeat for `/local/community/zigsight/zigsight-panel.js`

   **Option B: Via YAML**
   Add to your `configuration.yaml`:
   ```yaml
   lovelace:
     mode: yaml
     resources:
       - url: /local/community/zigsight/topology-card.js
         type: module
       - url: /local/community/zigsight/zigsight-panel.js
         type: module
   ```

3. Add the cards to your dashboard:

   **Topology Card:**
   ```yaml
   type: custom:zigsight-topology-card
   title: Zigbee Network Topology
   ```

   **Device List Panel:**
   ```yaml
   type: custom:zigsight-panel
   ```

## Usage

See [docs/ui.md](../../../docs/ui.md) for topology card documentation.
See [docs/frontend_panel.md](../../../docs/frontend_panel.md) for device list panel documentation.

## Features

### Topology Card

- **Network Statistics**: Device counts by type (coordinator, routers, end devices)
- **Device Cards**: Interactive cards showing device status and metrics
- **Color Coding**: Visual indicators for device type and health
- **Link Quality**: Color-coded signal strength indicators
- **Device Details**: Click any device to see detailed information
- **Warnings**: Highlights devices with connectivity or battery issues
- **Manual Refresh**: Update topology data on demand

### Device List Panel

- **Advanced Filtering**: Filter by device type, health status, battery level, link quality, and integration source
- **Flexible Sorting**: Sort by name, health score, battery level, link quality, last seen, and reconnect count
- **Real-time Search**: Find devices by name or device ID
- **Bulk Selection**: Select multiple devices for batch operations
- **Data Export**: Export selected or all devices to JSON
- **Pagination**: Browse large device lists efficiently (20 devices per page)
- **Statistics Dashboard**: View network health at a glance

## Development

The cards are written in vanilla JavaScript and require no build process. To modify:

1. Edit the card file (e.g., `topology-card.js` or `zigsight-panel.js`)
2. Copy updated file to your `www` directory
3. Clear browser cache
4. Refresh dashboard

See [docs/DEVELOPER_README.md](../../../docs/DEVELOPER_README.md) for more information.
