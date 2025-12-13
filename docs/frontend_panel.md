# ZigSight Frontend Panel

The ZigSight frontend panel provides a comprehensive full-screen interface for managing and visualizing your Zigbee network. It appears in the Home Assistant sidebar and gives you access to all ZigSight functionalities through an intuitive tab-based interface.

## Overview

The ZigSight Frontend Panel provides a comprehensive interface for managing large Zigbee networks with four powerful view modes:

### List View
- **Advanced Filtering**: Filter devices by type, health status, battery level, link quality, and integration source
- **Flexible Sorting**: Sort devices by name, health score, battery level, link quality, last seen timestamp, and reconnect count
- **Real-time Search**: Find devices quickly by name or device ID
- **Bulk Actions**: Select multiple devices and export their data
- **Pagination**: Efficiently browse through large device lists with 20 devices per page

### Topology View
- **Interactive Network Graph**: Visual representation of your Zigbee network topology
- **Device Nodes**: Different shapes and colors for coordinators, routers, and end devices
- **Link Quality Visualization**: Color-coded edges showing connection quality
- **Multiple Layouts**: Hierarchical tree or force-directed graph layouts
- **Interactive Controls**: Click nodes for details, zoom, pan, filter by device type
- **Performance Optimized**: Handles networks with 100+ devices efficiently
- **Problem Highlighting**: Quickly identify devices with connectivity or health issues

### Analytics View
- **Network Overview Dashboard**: Key metrics including total devices, average health score, and warning counts
- **Distribution Charts**: Battery level and link quality distribution visualizations
- **Historical Trends**: Time-series charts showing health score, battery, link quality, and reconnect rate trends
- **Device Comparison**: Side-by-side comparison of multiple devices
- **Alert Insights**: Devices requiring immediate attention with predictive warnings
- **Data Export**: Export analytics data in CSV or JSON format for external analysis

### Channel Recommendation View (New!)
- **Wi-Fi Scan Integration**: Scan your Wi-Fi environment to detect interference
- **Channel Visualization**: Visual spectrum showing Wi-Fi and Zigbee channels
- **Interference Heatmap**: Color-coded display of channel interference levels
- **Channel Scores**: Bar chart ranking channels by interference (lower is better)
- **Step-by-Step Guidance**: Detailed instructions for changing Zigbee channels
- **Safety Warnings**: Alerts about downtime and device reconnection requirements
- **Recommendation History**: Track past recommendations and channel changes

## Installation

### Step 1: Ensure Panel File is Available

The panel file (`zigsight-panel.js`) is included with ZigSight. For HACS installations, it's automatically available. For manual installations, ensure the file exists at:

```
custom_components/zigsight/www/zigsight-panel.js
```

### Step 2: Register the Panel

Add the following to your `configuration.yaml`:

```yaml
panel_custom:
  - name: zigsight
    sidebar_title: ZigSight
    sidebar_icon: mdi:zigbee
    url_path: zigsight
    module_url: /hacsfiles/zigsight/zigsight-panel.js
    require_admin: false
```

**Note**: If you installed ZigSight manually (not via HACS), use:

```yaml
panel_custom:
  - name: zigsight
    sidebar_title: ZigSight
    sidebar_icon: mdi:zigbee
    url_path: zigsight
    module_url: /local/zigsight/zigsight-panel.js
    require_admin: false
```

For manual installations, you'll need to copy the panel file to your `www` directory:

```bash
mkdir -p config/www/zigsight
cp custom_components/zigsight/www/zigsight-panel.js config/www/zigsight/
```

### Step 3: Restart Home Assistant

After adding the panel configuration, restart Home Assistant to apply the changes.

## Usage

Once installed, you'll see "ZigSight" in your Home Assistant sidebar. Click on it to access the full-screen panel interface.

### Panel Interface

The panel features a tab-based navigation system with four main sections:

1. **Devices** - Device management and monitoring
2. **Topology** - Network structure visualization
3. **Analytics** - Network health insights
4. **Channel Recommendation** - Wi-Fi interference analysis

Each tab provides specialized functionality for managing different aspects of your Zigbee network.

## Switching Between Views

The panel supports four view modes that you can switch between using the tabs:

- **📋 Devices Tab**: Device list with filtering, sorting, and bulk actions
- **🔗 Topology Tab**: Interactive network graph visualization
- **📊 Analytics Tab**: Comprehensive analytics dashboard with charts and insights
- **📡 Channel Recommendation Tab**: Channel recommendation with Wi-Fi interference analysis

Simply click the corresponding tab to switch between views. Your filter settings and selections are preserved when switching views.

## Features

### Common Features (Both Views)

#### View Toggle
- Located in the panel header
- Switch instantly between list and topology views
- Refresh button to reload device data from the API

#### Device Statistics

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

## Topology View Features

The Topology View provides an interactive network graph visualization that helps you understand your Zigbee network structure, identify connectivity issues, and optimize device placement.

### 1. Network Graph Visualization

The main canvas displays your Zigbee network as an interactive graph:

- **Nodes**: Represent individual devices with different shapes:
  - 💎 **Diamond**: Coordinator (root of the network)
  - ⬛ **Square**: Router devices (can relay messages)
  - ⚫ **Circle**: End devices (sensors, battery-powered devices)

- **Edges**: Show parent-child relationships (connections) between devices
  - **Direction**: Arrows point from parent to child device
  - **Color**: Indicates link quality (see legend)
  - **Width**: Thicker lines indicate better link quality

### 2. Layout Options

Choose between different layout algorithms to visualize your network:

#### Hierarchical Tree Layout (Default)
- **Use Case**: Best for understanding network structure and hierarchy
- **Visualization**: Coordinator at top, routers in middle, end devices at bottom
- **Benefits**: Clear parent-child relationships, easy to spot network depth
- **Physics**: Disabled for stable, predictable layout

#### Force-Directed Graph Layout
- **Use Case**: Best for dense networks or identifying clusters
- **Visualization**: Nodes arranged by connections, related devices group together
- **Benefits**: Natural clustering, reveals network patterns
- **Physics**: Enabled with stabilization for optimal positioning

**How to Switch**: Use the "Layout" dropdown in the toolbar

### 3. Interactive Controls

#### Zoom and Pan
- **Mouse Wheel**: Zoom in/out on the graph
- **Click and Drag**: Pan around the network
- **Fit to Screen**: Button to reset view and show entire network
- **Navigation Buttons**: Built-in controls for zoom and navigation

#### Click to View Device Details
- **Click any node** to display a detailed information panel showing:
  - Device name and type
  - Link quality to parent device
  - Battery level (if applicable)
  - Health score and status
  - Reconnect rate statistics
  - Last seen timestamp
  - Warning indicators for devices with issues

- **Click anywhere else** to close the details panel
- **Close button (×)** in the details panel to dismiss

### 4. Device Type Filtering

Toggle visibility of device types using the toolbar buttons:

- **Coordinator**: Show/hide the coordinator node
- **Routers**: Show/hide all router devices
- **End Devices**: Show/hide all end devices

**Use Cases**:
- Hide end devices to focus on backbone infrastructure
- Show only routers to analyze message routing paths
- Isolate coordinator to check direct connections

### 5. Link Quality Visualization

#### Color-Coded Connections

Edges (connections) are color-coded based on Link Quality Indicator (LQI):

- 🟢 **Green (Excellent)**: LQI 200-255 - Strong, reliable connection
- 🟡 **Yellow-Green (Good)**: LQI 150-199 - Good connection quality
- 🟠 **Orange (Fair)**: LQI 100-149 - Acceptable but could be improved
- 🔴 **Red (Poor)**: LQI 0-99 - Weak connection, may cause issues

#### Link Quality Labels

Toggle the display of LQI values on edges:

- **Link Quality Button**: Click to show/hide numeric LQI values
- **When Enabled**: Each connection displays its LQI value
- **When Disabled**: Cleaner view with only color coding

**Benefits**:
- Quickly identify weak connections
- Plan router placement for better coverage
- Troubleshoot communication issues

### 6. Highlight Problematic Devices

The "Highlight Issues" feature helps you quickly identify devices that need attention:

**How It Works**:
1. Click the "Highlight Issues" button in the toolbar
2. Devices with problems are highlighted in red
3. Normal devices retain their type-based colors

**Devices Flagged as Problematic**:
- Health score below 50 (critical)
- Connectivity warnings from analytics
- Battery drain warnings
- Frequent reconnections

**Use Cases**:
- Daily network health check
- Identify devices needing battery replacement
- Find devices in poor locations
- Prioritize maintenance tasks

### 7. Performance Optimization

The topology view is optimized for large networks (100+ devices):

- **Canvas Rendering**: Uses HTML5 canvas for smooth performance
- **Physics Stabilization**: Automatically disables after initial layout
- **Lazy Loading**: vis-network library loaded on-demand from CDN
- **Responsive**: Adapts to different screen sizes

**Performance Tips**:
- Use Hierarchical layout for very large networks (faster rendering)
- Hide device types you don't need to reduce visual complexity
- Use "Fit to Screen" to quickly navigate large networks

### 8. Topology Legend

A legend at the bottom explains the visualization:

- **Node Colors**: Device types (Coordinator, Router, End Device, Problematic)
- **Edge Colors**: Link quality ranges
- **Visual Reference**: Quick reminder of what each color means

## Usage Examples

### Topology View Examples

#### Example 1: Identify Network Coverage Gaps

1. Switch to **Topology View**
2. Select **Hierarchical Layout**
3. Enable **Highlight Issues**
4. Look for red (problematic) nodes
5. Check their link quality to parent devices
6. Plan router placement to improve coverage

#### Example 2: Optimize Router Placement

1. Switch to **Topology View**
2. Enable **Link Quality** labels
3. Hide **End Devices** to focus on backbone
4. Identify routers with many red/orange connections
5. Consider relocating routers for better mesh coverage

#### Example 3: Analyze Network Structure

1. Switch to **Topology View**
2. Select **Force-Directed Layout**
3. Observe natural clustering of devices
4. Identify isolated or poorly connected groups
5. Plan network expansion accordingly

#### Example 4: Daily Health Check

1. Switch to **Topology View**
2. Click **Highlight Issues**
3. Check for red nodes (problematic devices)
4. Click each red node to view details
5. Address warnings and connectivity issues

### List View Examples

#### Example 1: Find All Critical Devices

1. Set **Health Status** filter to **Critical**
2. Sort by **Health** column (ascending)
3. Review devices with lowest health scores
4. Export the list for troubleshooting

#### Example 2: Monitor Low Battery Devices

1. Set **Battery Level** range to 0% - 20%
2. Sort by **Battery** column (ascending)
3. Identify devices needing battery replacement
4. Export for maintenance planning

#### Example 3: Identify Poor Signal Quality

1. Set **Link Quality** range to 0 - 100
2. Sort by **Link Quality** column (ascending)
3. Review devices with poor connectivity
4. Plan repeater placement or device relocation

#### Example 4: Filter by Room

1. Use **Search** with room name (e.g., "bedroom")
2. Review all devices in that room
3. Check health and connectivity status
4. Export room-specific device data

#### Example 5: Compare Integration Sources

1. Set **Integration Source** to **ZHA**
2. Note the device count and health
3. Change to **Zigbee2MQTT**
4. Compare performance metrics

## Combined Workflow Example

### Weekly Network Maintenance Routine

1. **Start in List View**:
   - Sort by **Health** (ascending)
   - Identify devices with scores < 80
   - Note device names/IDs

2. **Switch to Topology View**:
   - Enable **Highlight Issues**
   - Locate the problematic devices visually
   - Check their link quality and position in the network

3. **Analyze Connectivity**:
   - Enable **Link Quality** labels
   - Identify poor connections (red/orange)
   - Plan router placement improvements

4. **Back to List View**:
   - Filter by **Battery Range** (0-20%)
   - Export list of devices needing battery replacement
   - Schedule maintenance

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

### Topology View Not Loading

1. **Check Internet Connection**: The vis-network library is loaded from CDN
2. **Check Browser Console**: Look for script loading errors
3. **Try Refresh**: Click the Refresh button to reload
4. **Check Firewall**: Ensure access to unpkg.com CDN is allowed
5. **Switch to List View**: Use list view if topology is unavailable

### Network Graph Not Displaying Properly

1. **Resize Window**: Try resizing browser window to trigger redraw
2. **Click Fit to Screen**: Use the fit button to reset the view
3. **Switch Layout**: Try changing between hierarchical and force-directed
4. **Clear Physics**: If using force-directed, wait for stabilization
5. **Check Device Count**: Very large networks (200+) may take longer to render

### Devices Not Showing in Topology

1. **Check Device Type Filters**: Ensure device types are not hidden
2. **Check Topology Data**: Verify devices have parent relationships
3. **Refresh Data**: Click refresh to reload from API
4. **Check API Response**: Verify `/api/zigsight/topology` returns nodes and edges

## Analytics View Features

The Analytics View provides a comprehensive dashboard for monitoring network health, analyzing trends, and identifying issues across your Zigbee network.

### 1. Network Overview Dashboard

At the top of the analytics view, you'll see key network metrics:

- **Total Devices**: Complete count of devices in your network
- **Average Health Score**: Network-wide average health score (0-100)
- **Devices with Warnings**: Number of devices with battery drain or connectivity warnings

These metrics provide a quick snapshot of overall network health.

### 2. Distribution Analysis

Visual representation of device metrics across your network:

#### Battery Level Distribution Chart
- Displays how many devices fall into each battery range:
  - 0-20%: Critical battery level
  - 21-40%: Low battery
  - 41-60%: Medium battery
  - 61-80%: Good battery
  - 81-100%: Excellent battery
- Helps identify how many devices need attention
- Only includes battery-powered devices

#### Link Quality Distribution Chart
- Shows distribution of link quality (LQI) across devices:
  - Poor (0-99): Weak connections needing attention
  - Fair (100-149): Acceptable but could be improved
  - Good (150-199): Solid connections
  - Excellent (200-255): Strong, reliable connections
- Helps assess overall network connectivity health

### 3. Historical Trends

Time-series charts showing how metrics change over time:

#### Controls
- **Select Device**: Choose a specific device or view network-wide average
- **Time Range**: Select from 6 hours to 1 week of historical data
- **Load Trends Button**: Click to load and display trend data

#### Available Trend Charts
1. **Health Score Trend**: Track device or network health over time
2. **Battery Level Trend**: Monitor battery drain patterns
3. **Link Quality Trend**: Observe connection stability
4. **Reconnect Rate Trend**: Identify connectivity issues

**Use Cases**:
- Identify devices with declining health scores
- Predict when batteries need replacement
- Spot connectivity degradation before it causes problems
- Validate improvements after network changes

### 4. Alerts & Insights

Real-time alerts for devices requiring attention:

#### Alert Types
- **Low Battery**: Devices below 20% battery
- **Rapid Battery Drain**: Devices with abnormal battery consumption patterns
- **Connectivity Issues**: Devices with frequent reconnections
- **Critical Health Score**: Devices with health scores below 50

#### Healthy Status
- When no issues are detected, you'll see a green "All Systems Healthy" indicator
- Provides confidence that your network is operating optimally

#### Alert Actions
- Each alert shows the device name and specific warnings
- Click on device names (in future versions) to jump to device details
- Use alerts to prioritize maintenance tasks

### 5. Device Comparison

Compare multiple devices side-by-side to identify best and worst performers:

#### How to Use
1. **Select Devices**: Check boxes next to devices you want to compare (up to 20 shown)
2. **View Comparison Table**: See all selected devices in a comparison table

#### Comparison Metrics
- **Health Score**: Color-coded (green = healthy, yellow = warning, red = critical)
- **Battery Level**: Current battery percentage
- **Link Quality**: Current LQI value with color coding
- **Reconnect Rate**: Events per hour
- **Last Seen**: Most recent communication timestamp

**Use Cases**:
- Compare similar devices to identify problematic ones
- Find the best-performing devices for reference
- Validate that similar devices have similar metrics
- Identify outliers that may need attention or repositioning

### 6. Export Analytics

Download analytics data for external analysis, reporting, or archival:

#### Export Formats

**JSON Export**
- Complete device analytics in JSON format
- Includes all metrics and computed analytics
- Easy to process programmatically
- Filename: `zigsight-analytics-YYYY-MM-DD.json`

**CSV Export**
- Spreadsheet-compatible format
- Opens directly in Excel, Google Sheets, etc.
- Includes key metrics in columns
- Filename: `zigsight-analytics-YYYY-MM-DD.csv`

#### Exported Data Fields
- Device ID and friendly name
- Last update timestamp
- Link quality, battery level
- Health score
- Reconnect rate and battery trend
- Warning flags (battery drain, connectivity)
- Reconnect count

**Use Cases**:
- Create custom reports for network documentation
- Track historical network health over months
- Share data with support teams
- Analyze trends in external tools (Python, R, Tableau, etc.)
- Backup device state for comparison after changes

### 7. Performance Tips

The Analytics View is optimized for real-time insights:

- **Auto-refresh**: Click the Refresh button to reload latest data
- **Lazy Loading**: Charts load only when switching to Analytics view
- **CDN Resources**: Chart.js loaded from CDN for fast initial load
- **Client-side Processing**: All filtering and calculations happen in your browser
- **Responsive Charts**: Charts adapt to screen size automatically

## Channel Recommendation View Features

The Channel Recommendation View helps you optimize your Zigbee network by analyzing Wi-Fi interference and recommending the best Zigbee channel to minimize conflicts.

### 1. Wi-Fi Network Scan

Before getting a recommendation, you need to scan your Wi-Fi environment:

#### Scan Modes

**Manual Scan Data (Recommended)**
- Paste Wi-Fi scan data in JSON format
- Obtain scan data from your router's admin interface
- Format: Array of objects with `channel`, `rssi`, and optional `ssid`
- Example:
  ```json
  [
    {"channel": 1, "rssi": -45, "ssid": "MyNetwork"},
    {"channel": 6, "rssi": -60, "ssid": "NeighborWiFi"},
    {"channel": 11, "rssi": -75, "ssid": "AnotherNetwork"}
  ]
  ```

**Host System Scan**
- Uses the Home Assistant host's Wi-Fi adapter
- Requires `iwlist` or `nmcli` tools
- May require elevated permissions
- Automatically scans for nearby access points

**Router API (Future)**
- Direct integration with router APIs (UniFi, OpenWrt, Fritz!Box)
- Planned for future releases
- Will enable automated periodic scans

#### How to Perform a Scan

1. **Select Scan Mode**: Choose between Manual, Host System, or Router API
2. **Enter Scan Data** (Manual mode): Paste your Wi-Fi scan JSON data
3. **Click "Scan and Recommend"**: Triggers the analysis
4. **Review Results**: See the recommended channel and explanation

### 2. Channel Visualization

After scanning, the view displays a visual spectrum showing:

#### Spectrum Diagram
- **Wi-Fi Channels**: Orange markers showing detected Wi-Fi networks
- **Zigbee Channels**: Blue markers for Zigbee channels (11, 15, 20, 25, 26)
- **Interference Bars**: Height indicates interference level on each Zigbee channel
- **Recommended Channel**: Highlighted with a star ⭐ and green color

#### Interference Levels
- **Green (Low)**: Interference score < 20 - Excellent choice
- **Orange (Medium)**: Interference score 20-50 - Acceptable
- **Red (High)**: Interference score > 50 - Avoid if possible

### 3. Channel Scores

A bar chart displays interference scores for all recommended Zigbee channels:

- **Lower scores are better** (less interference)
- Channels are sorted from best to worst
- Color-coded bars:
  - **Green**: Excellent (score < 20)
  - **Orange**: Good (score 20-50)
  - **Red**: Poor (score > 50)

#### Understanding Scores

Scores are calculated based on:
- Frequency overlap between Wi-Fi and Zigbee channels
- Signal strength (RSSI) of nearby Wi-Fi access points
- Number of Wi-Fi networks on overlapping frequencies

### 4. Recommendation Explanation

The system provides a detailed explanation including:

- Number of Wi-Fi access points detected
- Wi-Fi channels in use
- Recommended Zigbee channel
- Interference score of the recommended channel
- Severity assessment (minimal, moderate, or significant interference)

### 5. Channel Change Instructions

The view provides step-by-step guidance for changing your Zigbee channel:

#### Important Warnings

⚠️ **Before changing channels, be aware:**
- Network will be temporarily unavailable (15-30 minutes)
- All devices must reconnect
- Automations using Zigbee devices will be paused
- Battery-powered devices may take longer to rejoin

#### Step-by-Step Process

**Step 1: Backup Your Network**
- Create a backup of your Zigbee configuration
- Document current device list
- Note any custom settings
- (Automated backup coming soon)

**Step 2: Plan for Downtime**
- Choose a time when automation downtime is acceptable
- Ensure 15-30 minutes for the full process
- Inform household members of the maintenance window

**Step 3: Change the Channel**

**For ZHA:**
1. Go to **Settings** → **Devices & Services** → **ZHA**
2. Click **Configure**
3. Select **Change Channel**
4. Choose the recommended channel
5. Confirm the change

**For Zigbee2MQTT:**
1. Edit `configuration.yaml` in Zigbee2MQTT
2. Set `advanced.channel` to the recommended channel
3. Restart Zigbee2MQTT
4. Wait for coordinator to restart on new channel

**For deCONZ:**
1. Open deCONZ GUI (Phoscon app)
2. Go to **Settings** → **Gateway**
3. Select the recommended channel
4. Apply and wait for restart

**Step 4: Monitor Reconnection**
- Switch to the Topology View
- Watch devices rejoin the network
- Battery devices may take longer (up to next wake cycle)
- Expect 5-15 minutes for most devices

**Step 5: Verify Network Health**
- Check all devices are online in List View
- Review link quality in Topology View
- Test critical automations
- Monitor for 24 hours for stability

### 6. Recommendation History

The view maintains a history of your channel recommendations:

#### What's Tracked
- Timestamp of each scan
- Recommended channel
- Interference score
- Number of Wi-Fi access points detected

#### Using History
- Compare recommendations over time
- Track changes in Wi-Fi environment
- Identify trends in interference
- Document when channel changes were made

History is stored in Home Assistant memory and retains the last 10 recommendations.

### 7. Best Practices

#### When to Change Channels

Consider changing your Zigbee channel if:
- Current interference score is > 50
- New channel score is at least 20 points lower
- Experiencing frequent device disconnections
- Added new Wi-Fi access points nearby
- Network performance has degraded

#### When NOT to Change

Avoid changing channels if:
- Current channel score < 20 (already excellent)
- Improvement would be < 10 points
- Network is stable and performing well
- Recent changes haven't stabilized yet (wait 1 week)

#### Periodic Monitoring

- **Monthly**: Check for new Wi-Fi networks
- **Quarterly**: Run a fresh scan and compare
- **After Changes**: Re-scan if you add/remove Wi-Fi APs
- **Performance Issues**: Scan when experiencing problems

### 8. Troubleshooting

#### No Recommendation Available

If you see "No channel recommendation available":
1. Perform a Wi-Fi scan first
2. Ensure scan data is in correct JSON format
3. Check that scan data includes `channel` and `rssi` fields
4. Verify API is responding (check browser console)

#### All Channels Show High Interference

If all channels have high scores (> 50):
- This indicates a very congested 2.4 GHz environment
- Choose the channel with the lowest score anyway
- Consider upgrading to Zigbee devices that support 5 GHz (rare)
- Reduce Wi-Fi power levels if possible
- Add more Zigbee routers to improve mesh resilience

#### Devices Not Reconnecting After Channel Change

If devices don't rejoin:
1. **Wait longer**: Some devices need 30+ minutes
2. **Power cycle routers**: Unplug for 10 seconds, plug back in
3. **Rejoin manually**: Some devices need manual rejoining
4. **Battery devices**: Replace batteries or trigger wake cycle
5. **Factory reset**: Last resort for problematic devices

#### Invalid Scan Data Error

If you get validation errors:
- Ensure JSON format is correct (use a validator)
- Check that `channel` values are 1-14
- Verify `rssi` values are negative numbers (-30 to -90)
- Remove any invalid or incomplete entries

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

The panel uses the ZigSight API endpoints:

### Topology API
```
GET /api/zigsight/topology
```

Returns device and network data including:
- **nodes**: Array of device objects with metrics and analytics
- **edges**: Array of connection objects with link quality
- **device_count**: Total number of devices
- **coordinator_count**, **router_count**, **end_device_count**: Device type counts

### Analytics APIs (New!)

#### Analytics Overview
```
GET /api/zigsight/analytics/overview
```

Returns network-wide analytics including:
- Total devices and average health score
- Devices with warnings count
- Battery level distribution
- Link quality distribution
- Device counts by type

#### Analytics Trends
```
GET /api/zigsight/analytics/trends?device_id=xxx&metric=health_score&hours=24
```

Query Parameters:
- `device_id` (optional): Specific device ID or omit for network-wide
- `metric`: One of `health_score`, `battery`, `link_quality`, `reconnect_rate`
- `hours`: Time window (6, 12, 24, 48, 168)

Returns time-series data for the specified metric.

#### Analytics Export
```
GET /api/zigsight/analytics/export?format=csv&devices=device1,device2
```

Query Parameters:
- `format`: `json` or `csv`
- `devices` (optional): Comma-separated device IDs or omit for all

Returns analytics data in the specified format.

### Channel Recommendation APIs (New!)

#### Get Current Recommendation
```
GET /api/zigsight/channel-recommendation
```

Returns the most recent channel recommendation including:
- `has_recommendation`: Boolean indicating if recommendation exists
- `recommended_channel`: Best Zigbee channel (11, 15, 20, or 25)
- `current_channel`: Current Zigbee channel (if available)
- `scores`: Object with interference scores for each channel
- `explanation`: Human-readable recommendation explanation
- `timestamp`: When the recommendation was generated

#### Trigger New Scan and Recommendation
```
POST /api/zigsight/channel-recommendation
Content-Type: application/json

{
  "mode": "manual",
  "wifi_scan_data": [
    {"channel": 1, "rssi": -45, "ssid": "MyNetwork"},
    {"channel": 6, "rssi": -60}
  ]
}
```

Request Parameters:
- `mode`: Scan mode (`manual`, `host_scan`, or `router_api`)
- `wifi_scan_data`: Array of Wi-Fi APs (required for manual mode)
  - Each AP should have `channel` (1-14) and `rssi` (dBm)
  - Optional `ssid` field for network name

Returns new recommendation with Wi-Fi AP data.

#### Get Recommendation History
```
GET /api/zigsight/recommendation-history
```

Returns:
- `history`: Array of past recommendations (up to 10)
- `count`: Number of history entries

Each history entry includes:
- Timestamp
- Recommended channel
- Channel scores
- Number of Wi-Fi APs detected

The panel processes this data client-side for all four views.

## Technology Stack

### List View
- Native Web Components (Custom Elements)
- Shadow DOM for style encapsulation
- Event delegation for performance
- Client-side filtering and sorting

### Topology View
- **vis-network v9.1.9**: Graph visualization library
- Canvas-based rendering for performance
- Physics engine for force-directed layout
- Dynamic script loading from CDN

### Analytics View
- **Chart.js v4.4.0**: Chart visualization library
- Doughnut charts for distribution analysis
- Line charts for time-series trends
- Dynamic script loading from CDN
- Client-side data processing and aggregation

### Channel Recommendation View
- Native Web Components
- Interactive spectrum visualization
- Bar chart for channel scores
- JSON-based Wi-Fi scan data input
- RESTful API integration for recommendations

## Future Enhancements

Planned features for future releases:

### List View
- [ ] Virtual scrolling for 1000+ device networks
- [ ] Custom column visibility settings
- [ ] Device grouping by room/area
- [ ] Bulk device operations (remove, rename)
- [ ] Export to CSV format
- [ ] Saved filter presets
- [ ] Auto-refresh option
- [ ] Keyboard navigation

### Topology View
- [x] Interactive network graph visualization ✅
- [x] Multiple layout algorithms ✅
- [x] Device type filtering ✅
- [x] Link quality visualization ✅
- [x] Click for device details ✅
- [x] Zoom and pan controls ✅
- [x] Highlight problematic devices ✅
- [ ] Manual node positioning (drag and drop)
- [ ] Save custom layout arrangements
- [ ] Network path highlighting (show route to coordinator)
- [ ] Subnet grouping for large networks
- [ ] Historical link quality overlay
- [ ] Mesh quality heatmap
- [ ] Export topology as image (PNG/SVG)
- [ ] Web Workers for layout calculations (very large networks)

### Analytics View
- [x] Network overview dashboard ✅
- [x] Battery and link quality distribution charts ✅
- [x] Time-series trend charts ✅
- [x] Device comparison functionality ✅
- [x] Alert insights with predictive warnings ✅
- [x] Export to JSON and CSV ✅
- [ ] Custom date range selection for trends
- [ ] Downloadable PDF reports
- [ ] Trend anomaly detection
- [ ] Performance benchmarking against network averages
- [ ] Historical comparison (compare current vs. past periods)
- [ ] Custom alert thresholds
- [ ] Scheduled email reports
- [ ] Integration with Home Assistant notifications

### Channel Recommendation View
- [x] Wi-Fi scan integration (manual mode) ✅
- [x] Channel visualization with spectrum diagram ✅
- [x] Interference heatmap display ✅
- [x] Channel scores visualization (bar chart) ✅
- [x] Step-by-step channel change guidance ✅
- [x] Safety warnings and best practices ✅
- [x] Recommendation history tracking ✅
- [ ] Automated Wi-Fi scanning (host system)
- [ ] Router API integration (UniFi, OpenWrt, Fritz!Box)
- [ ] Automated channel change service integration
- [ ] Real-time interference monitoring
- [ ] Periodic scan scheduling
- [ ] Channel change rollback capability
- [ ] Backup/restore integration
- [ ] Email/notification alerts for high interference
- [ ] 5 GHz Zigbee support (future hardware)

### General
- [ ] Dark mode optimization
- [ ] Mobile-responsive improvements
- [ ] Accessibility (ARIA labels, keyboard shortcuts)
- [ ] Internationalization (i18n)

## Performance Considerations

### List View
- **Pagination**: Default 20 items per page prevents rendering thousands of DOM nodes
- **Event Delegation**: Single listener per table/section instead of per row
- **Client-side Processing**: Filtering and sorting happen in memory
- **Recommended**: Up to 500 devices perform smoothly

### Topology View
- **Canvas Rendering**: More efficient than SVG for large graphs
- **Physics Stabilization**: Automatically disabled after initial layout
- **Hierarchical Layout**: Recommended for 100+ devices (faster than force-directed)
- **Device Type Hiding**: Reduces visual complexity and improves performance
- **Recommended**: Up to 200 devices with force-directed, 500+ with hierarchical

**Tip**: For networks with 500+ devices, use hierarchical layout and hide end devices to focus on the backbone infrastructure.

## Related Documentation

- [Getting Started Guide](getting_started.md)
- [Network Topology Visualization](ui.md)
- [Analytics Documentation](analytics.md)
- [Automations](automations.md)

## Feedback and Support

If you encounter issues or have suggestions for the Frontend Panel:

1. Check the [FAQ](faq.md)
2. Review existing [GitHub Issues](https://github.com/mmornati/zigsight/issues)
3. Open a new issue with:
   - Panel version
   - Browser and version
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots if applicable

## Related Documentation

- [Getting Started Guide](getting_started.md) - Initial setup and configuration
- [UI Documentation](ui.md) - Network topology card (separate from panel)
- [Analytics Documentation](analytics.md) - Understanding device metrics
- [Wi-Fi Recommendation](wifi_recommendation.md) - Channel optimization guide
