# ZigSight Device List Panel

This document describes how to use the ZigSight Device List Panel to manage and monitor your Zigbee devices with advanced filtering, sorting, and search capabilities.

## Overview

The ZigSight Device List Panel provides a comprehensive interface for managing large Zigbee networks with:

- **Advanced Filtering**: Filter devices by type, health status, battery level, link quality, and integration source
- **Flexible Sorting**: Sort devices by name, health score, battery level, link quality, last seen timestamp, and reconnect count
- **Real-time Search**: Find devices quickly by name or device ID
- **Bulk Actions**: Select multiple devices and export their data
- **Pagination**: Efficiently browse through large device lists with 20 devices per page

## Installation

### Step 1: Add the Panel Resource

The device list panel is automatically included with ZigSight. To use it, you need to register it as a Lovelace resource.

#### Option A: Using the UI (Recommended)

1. Navigate to **Settings** → **Dashboards** → **Resources** (click the three-dot menu in the top right)
2. Click **Add Resource**
3. Enter the URL: `/local/community/zigsight/zigsight-panel.js`
4. Set Resource type to **JavaScript Module**
5. Click **Create**

#### Option B: Using YAML Configuration

Add the following to your `configuration.yaml`:

```yaml
lovelace:
  mode: yaml
  resources:
    - url: /local/community/zigsight/zigsight-panel.js
      type: module
```

**Note**: You'll need to copy the `zigsight-panel.js` file from `custom_components/zigsight/www/` to your `www/community/zigsight/` directory:

```bash
mkdir -p config/www/community/zigsight
cp custom_components/zigsight/www/zigsight-panel.js config/www/community/zigsight/
```

### Step 2: Add the Panel to Your Dashboard

#### Using the UI

1. Open the dashboard where you want to add the panel
2. Click **Edit Dashboard** (three-dot menu → **Edit Dashboard**)
3. Click **Add Card**
4. Search for "ZigSight Device List Panel"
5. Click to add the card

#### Using YAML

Add the following to your dashboard configuration:

```yaml
type: custom:zigsight-panel
```

## Features

### 1. Device Statistics

At the top of the panel, you'll see real-time statistics:

- **Total Devices**: All devices in your network
- **Filtered**: Number of devices matching current filters
- **Selected**: Number of devices currently selected for bulk actions
- **Healthy**: Devices with health scores ≥ 80

### 2. Filtering

The panel provides multiple filter options to help you find specific devices:

#### Search

- **Function**: Real-time search across device names and IDs
- **Usage**: Type in the search box to instantly filter the device list
- **Example**: Search "living room" to find all devices with that in their name

#### Device Type Filter

Filter devices by their Zigbee role:

- **All Types**: Show all devices (default)
- **Coordinator**: Show only the Zigbee coordinator
- **Router**: Show only router devices (typically powered devices)
- **End Device**: Show only end devices (typically battery-powered sensors)

#### Health Status Filter

Filter devices by their health score category:

- **All Status**: Show all devices (default)
- **Healthy**: Devices with health score ≥ 80
- **Warning**: Devices with health score between 50-79
- **Critical**: Devices with health score < 50

#### Battery Level Range

- **Function**: Filter devices by battery percentage
- **Usage**: Use the two sliders to set minimum and maximum battery levels
- **Range**: 0% to 100%
- **Note**: Devices without battery information will always be shown

#### Link Quality Range

- **Function**: Filter devices by link quality (LQI)
- **Usage**: Use the two sliders to set minimum and maximum LQI values
- **Range**: 0 to 255
- **Note**: Higher values indicate better signal quality

#### Integration Source Filter

Filter devices by the Zigbee integration that provides their data:

- **All Sources**: Show all devices (default)
- **ZHA**: Show only devices from ZHA integration
- **Zigbee2MQTT**: Show only devices from Zigbee2MQTT
- **deCONZ**: Show only devices from deCONZ

### 3. Sorting

Click on any column header to sort the device list. Click again to reverse the sort order.

Available sort columns:

- **Device**: Sort alphabetically by device name
- **Health**: Sort by health score (higher = healthier)
- **Battery**: Sort by battery level (higher = more charge)
- **Link Quality**: Sort by LQI (higher = better signal)
- **Last Seen**: Sort by last communication timestamp (recent first)
- **Reconnects**: Sort by reconnection rate (lower = more stable)

Visual indicators:

- ⇅ Unsorted column (click to sort ascending)
- ↑ Sorted ascending (click to sort descending)
- ↓ Sorted descending (click to sort ascending)

### 4. Bulk Selection

Select devices for bulk operations:

1. **Select Individual Devices**: Click checkboxes in the first column
2. **Select All on Page**: Click the checkbox in the table header
3. **View Selected Count**: The statistics bar shows how many devices are selected

### 5. Bulk Actions

#### Export Selected Devices

1. Select one or more devices using checkboxes
2. Click **Export Selected (X)** button
3. A JSON file with the selected devices' data will be downloaded
4. Filename format: `zigsight-devices-YYYY-MM-DD.json`

#### Export All Devices

1. Click **Export All** button
2. A JSON file with all filtered devices will be downloaded
3. Filename format: `zigsight-all-devices-YYYY-MM-DD.json`
4. This exports only devices matching current filters

### 6. Pagination

For networks with many devices, the panel uses pagination:

- **Items Per Page**: 20 devices
- **Navigation**: Use First, Previous, Next, Last buttons
- **Page Indicator**: Shows current page and total pages
- **Note**: Pagination resets to page 1 when filters change

### 7. Device Information Display

Each device row shows:

- **Device Name**: Friendly name of the device
- **Device ID**: Unique identifier (shown below name in gray)
- **Health Score**: Visual badge with color coding:
  - 🟢 Green (Healthy): Score ≥ 80
  - 🟡 Orange (Warning): Score 50-79
  - 🔴 Red (Critical): Score < 50
  - ⚪ Gray (Unknown): No health data
- **Type**: Color-coded badge:
  - 🔵 Blue: Coordinator
  - 🟢 Green: Router
  - 🟠 Orange: End Device
- **Battery**: Percentage with battery icon (if applicable)
- **Link Quality**: LQI value with color-coded dot:
  - 🟢 Green (Excellent): LQI ≥ 200
  - 🟡 Yellow-Green (Good): LQI 150-199
  - 🟠 Orange (Fair): LQI 100-149
  - 🔴 Red (Poor): LQI < 100
- **Last Seen**: Timestamp of last communication
- **Reconnects**: Reconnection rate per hour

## Usage Examples

### Example 1: Find All Critical Devices

1. Set **Health Status** filter to **Critical**
2. Sort by **Health** column (ascending)
3. Review devices with lowest health scores
4. Export the list for troubleshooting

### Example 2: Monitor Low Battery Devices

1. Set **Battery Level** range to 0% - 20%
2. Sort by **Battery** column (ascending)
3. Identify devices needing battery replacement
4. Export for maintenance planning

### Example 3: Identify Poor Signal Quality

1. Set **Link Quality** range to 0 - 100
2. Sort by **Link Quality** column (ascending)
3. Review devices with poor connectivity
4. Plan repeater placement or device relocation

### Example 4: Filter by Room

1. Use **Search** with room name (e.g., "bedroom")
2. Review all devices in that room
3. Check health and connectivity status
4. Export room-specific device data

### Example 5: Compare Integration Sources

1. Set **Integration Source** to **ZHA**
2. Note the device count and health
3. Change to **Zigbee2MQTT**
4. Compare performance metrics

## Data Export Format

Exported JSON files contain device data in the following format:

```json
[
  {
    "id": "device_id_123",
    "label": "Living Room Motion Sensor",
    "type": "end_device",
    "link_quality": 185,
    "battery": 85,
    "last_seen": "2024-01-15T14:30:00Z",
    "health_score": 92.5,
    "analytics": {
      "reconnect_rate": 0.2,
      "battery_trend": -0.05,
      "battery_drain_warning": false,
      "connectivity_warning": false
    }
  }
]
```

You can use this data for:

- External analysis and reporting
- Backup and documentation
- Integration with other tools
- Historical tracking

## Keyboard Shortcuts

Currently, the panel does not support keyboard shortcuts. This may be added in future versions.

## Performance Considerations

### Large Networks

For networks with 100+ devices:

- **Pagination**: Automatically limits display to 20 devices per page
- **Client-side Filtering**: Filters are applied instantly without server requests
- **Efficient Rendering**: Only visible devices are rendered
- **Optimized Sorting**: Uses native JavaScript sort for fast operations

### Browser Compatibility

The panel works best with modern browsers:

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Troubleshooting

### Panel Not Loading

1. **Check Resource Registration**: Verify the panel is registered in Lovelace resources
2. **Check File Location**: Ensure `zigsight-panel.js` is in the correct directory
3. **Clear Browser Cache**: Try hard refresh (Ctrl+Shift+R) or incognito mode
4. **Check Browser Console**: Open developer tools (F12) and check for errors

### No Devices Displayed

1. **Check ZigSight Integration**: Verify ZigSight is properly configured
2. **Check API Connection**: Ensure `/api/zigsight/topology` endpoint is accessible
3. **Check Filters**: Reset all filters to defaults
4. **Refresh Data**: Click the Refresh button in the panel header

### Filters Not Working

1. **Check Filter Values**: Ensure range sliders are set correctly
2. **Clear Search**: Remove any search query that might be too restrictive
3. **Reset Filters**: Reload the page to reset all filters
4. **Check Browser Console**: Look for JavaScript errors

### Export Not Working

1. **Check Browser Permissions**: Allow downloads from your Home Assistant instance
2. **Disable Pop-up Blockers**: Temporarily disable if downloads are blocked
3. **Select Devices**: Ensure at least one device is selected for "Export Selected"
4. **Try Export All**: Use "Export All" as an alternative

## Advanced Usage

### Combining Filters

You can combine multiple filters for precise device selection:

```
Example: Find all battery-powered end devices in the bedroom with low battery

1. Search: "bedroom"
2. Device Type: End Device
3. Battery Range: 0% - 30%
```

### Regular Monitoring Workflows

#### Daily Health Check

1. Sort by **Health** (ascending)
2. Review devices with scores < 80
3. Check for new warnings or issues

#### Weekly Maintenance

1. Filter by **Battery Range**: 0% - 20%
2. Export list of devices needing battery replacement
3. Filter by **Link Quality**: 0 - 100
4. Export list of devices with connectivity issues

#### Monthly Network Audit

1. Export **All Devices**
2. Compare with previous month's export
3. Identify trends in device health
4. Plan network improvements

## API Integration

The panel uses the ZigSight topology API:

```
GET /api/zigsight/topology
```

This returns device data that the panel processes client-side. Future versions may include additional endpoints for:

- Server-side filtering (for very large networks)
- Historical device data
- Custom sorting algorithms

## Future Enhancements

Planned features for future releases:

- [ ] Virtual scrolling for 1000+ device networks
- [ ] Custom column visibility settings
- [ ] Device grouping by room/area
- [ ] Bulk device operations (remove, rename)
- [ ] Export to CSV format
- [ ] Saved filter presets
- [ ] Auto-refresh option
- [ ] Keyboard navigation
- [ ] Dark mode optimization
- [ ] Mobile-responsive improvements

## Related Documentation

- [Getting Started Guide](getting_started.md)
- [Network Topology Visualization](ui.md)
- [Analytics Documentation](analytics.md)
- [Automations](automations.md)

## Feedback and Support

If you encounter issues or have suggestions for the Device List Panel:

1. Check the [FAQ](faq.md)
2. Review existing [GitHub Issues](https://github.com/mmornati/zigsight/issues)
3. Open a new issue with:
   - Panel version
   - Browser and version
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots if applicable
