# ZigSight Lovelace Cards

This directory contains custom Lovelace cards for ZigSight.

## Included Cards

### topology-card.js

Legacy network topology visualization card showing device cards in a grid layout.

**Features:**
- Device statistics by type
- Grid-based device cards
- Basic device information display

**Note**: This card provides a basic topology view. For advanced interactive network visualization, use the topology view in `zigsight-panel.js`.

### zigsight-panel.js

Comprehensive device management panel with two view modes:

**List View:**
- Advanced filtering, sorting, and search
- Bulk actions and data export
- Pagination for large networks

**Topology View (New!):**
- Interactive network graph visualization
- Multiple layout algorithms (hierarchical, force-directed)
- Device type filtering and problematic device highlighting
- Link quality visualization
- Click-to-view device details
- Zoom and pan controls
- Optimized for 100+ device networks

### topology-visualization.js

Standalone interactive network topology visualization component that can be used independently.

**Features:**
- Full-featured network graph visualization
- All topology view features from zigsight-panel.js
- Can be embedded separately if needed

## Installation

### Automatic (HACS)

If you installed ZigSight via HACS, the card files are already included in your installation.

### Manual Installation

1. Copy the card files to your Home Assistant `www` directory:

   ```bash
   mkdir -p config/www/community/zigsight
   cp custom_components/zigsight/www/*.js config/www/community/zigsight/
   ```

2. Register the cards as Lovelace resources:

   **Option A: Via UI**
   - Go to **Settings** → **Dashboards** → **Resources** (three-dot menu)
   - Click **Add Resource**
   - URL: `/local/community/zigsight/zigsight-panel.js` (recommended)
   - Resource type: **JavaScript Module**
   - Optionally add other cards similarly

   **Option B: Via YAML**
   Add to your `configuration.yaml`:
   ```yaml
   lovelace:
     mode: yaml
     resources:
       - url: /local/community/zigsight/zigsight-panel.js
         type: module
       - url: /local/community/zigsight/topology-card.js
         type: module
       - url: /local/community/zigsight/topology-visualization.js
         type: module
   ```

3. Add the cards to your dashboard:

   **Device Management Panel (Recommended):**
   ```yaml
   type: custom:zigsight-panel
   ```

   **Legacy Topology Card:**
   ```yaml
   type: custom:zigsight-topology-card
   title: Zigbee Network Topology
   ```

   **Standalone Topology Visualization:**
   ```yaml
   type: custom:zigsight-topology-visualization
   title: Network Topology
   ```

## Usage

See [docs/frontend_panel.md](../../../docs/frontend_panel.md) for complete device management panel documentation including topology visualization.

## Features Comparison

| Feature | topology-card.js | zigsight-panel.js | topology-visualization.js |
|---------|-----------------|-------------------|---------------------------|
| Device grid view | ✅ | ❌ | ❌ |
| Interactive graph | ❌ | ✅ | ✅ |
| List view with filters | ❌ | ✅ | ❌ |
| Multiple layouts | ❌ | ✅ | ✅ |
| Device type filtering | ❌ | ✅ | ✅ |
| Link quality viz | Basic | Advanced | Advanced |
| Zoom/pan controls | ❌ | ✅ | ✅ |
| Problem highlighting | ✅ | ✅ | ✅ |
| Bulk export | ❌ | ✅ | ❌ |
| View mode toggle | ❌ | ✅ | ❌ |

**Recommendation**: Use `zigsight-panel.js` for the best experience with both list and topology views.

## Device Management Panel Features

### List View
- **Advanced Filtering**: Filter by device type, health status, battery level, link quality, and integration source
- **Flexible Sorting**: Sort by name, health score, battery level, link quality, last seen, and reconnect count
- **Real-time Search**: Find devices by name or device ID
- **Bulk Selection**: Select multiple devices for batch operations
- **Data Export**: Export selected or all devices to JSON
- **Pagination**: Browse large device lists efficiently (20 devices per page)
- **Statistics Dashboard**: View network health at a glance

### Topology View
- **Interactive Network Graph**: Visual representation of network structure
- **Multiple Layouts**: Hierarchical tree or force-directed graph
- **Device Nodes**: Different shapes for coordinator, routers, and end devices
- **Link Quality**: Color-coded edges with optional LQI labels
- **Device Filtering**: Show/hide device types
- **Problem Highlighting**: Identify devices with issues
- **Click for Details**: View device information in side panel
- **Navigation**: Zoom, pan, and fit-to-screen controls
- **Performance**: Optimized for 100+ device networks

## Dependencies

### vis-network Library

The topology visualization features use the `vis-network` library (v9.1.9) which is automatically loaded from CDN when needed:

- **CDN**: https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js
- **License**: MIT/Apache-2.0
- **Size**: ~300KB (loaded only when using topology view)
- **Performance**: Canvas-based rendering for smooth interaction

**Note**: Requires internet connection to load the library. If you're running Home Assistant without internet access, you'll need to self-host the vis-network library.

## Development

The cards are written in vanilla JavaScript and require no build process. To modify:

1. Edit the card file (e.g., `zigsight-panel.js`)
2. Copy updated file to your `www` directory
3. Clear browser cache (Ctrl+Shift+R)
4. Refresh dashboard

For detailed development information, see the main project documentation.

## Browser Compatibility

- **Chrome/Edge**: 90+ (recommended)
- **Firefox**: 88+
- **Safari**: 14+

## Performance Tips

For optimal performance with large networks:

1. **List View**: Use pagination (default 20 items)
2. **Topology View**: 
   - Use hierarchical layout for 100+ devices
   - Hide end devices to focus on infrastructure
   - Disable link quality labels for cleaner view
3. **General**: Refresh only when needed to reduce API calls
