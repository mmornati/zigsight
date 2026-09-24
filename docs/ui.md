# ZigSight UI - Dashboard Cards

ZigSight ships two Lovelace cards. They are served by the integration itself
from `/zigsight_static/` (nothing to copy into `www/`) and work without
internet access.

| Card | Type | What it shows |
|------|------|---------------|
| Network Topology | `custom:zigsight-topology-card` | Device counts by type and a grid of devices (type, LQI, battery, health), with a details popup |
| Interactive Network Topology | `custom:zigsight-topology-visualization` | The network as a graph (same view as the panel's Topology tab): pan, zoom, filters, LQI labels |

> ZigSight also adds a full-screen [panel](frontend_panel.md) to the sidebar
> (devices, topology, analytics, channel recommendation). The cards are for
> embedding a view in your own dashboards.

## Installation

### Step 1: Register the card resource

The card files are already served by ZigSight; you only need to tell the
dashboards to load them.

#### Using the UI (recommended)

1. Go to **Settings** → **Dashboards** → three-dot menu → **Resources**
   (enable *Advanced mode* in your user profile if the menu entry is missing).
2. Click **Add resource**.
3. URL: `/zigsight_static/topology-card.js` (or
   `/zigsight_static/topology-visualization.js`, or add both).
4. Resource type: **JavaScript module**.
5. Click **Create** and reload the browser tab.

#### Using YAML dashboards

```yaml
lovelace:
  mode: yaml
  resources:
    - url: /zigsight_static/topology-card.js
      type: module
    - url: /zigsight_static/topology-visualization.js
      type: module
```

> Upgrading from an older ZigSight version? Replace resource URLs such as
> `/local/community/zigsight/topology-card.js` with the `/zigsight_static/...`
> ones above and delete the old copies from your `www` folder: copies no
> longer get updates.

### Step 2: Add the card to a dashboard

Search for "ZigSight" in the card picker, or use YAML:

```yaml
type: custom:zigsight-topology-card
title: Zigbee Network Topology
```

```yaml
type: custom:zigsight-topology-visualization
title: Network Topology
layout: radial   # radial (default) or force
height: 500      # graph height in pixels
```

## Configuration options

### `custom:zigsight-topology-card`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `title` | string | `Zigbee Network Topology` | Card title |

### `custom:zigsight-topology-visualization`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `title` | string | `Network Topology` | Card title |
| `layout` | `radial` / `force` | `radial` | Initial graph layout |
| `height` | number | `500` | Graph height in pixels |

## Understanding the view

- **Nodes** are keyed by IEEE address and labelled with the friendly name.
  Shapes and colours: coordinator (blue diamond), routers (green squares),
  end devices (orange circles), unknown type (grey, e.g. ZHA devices whose
  role ZigSight can't read). Offline devices are faded.
- **Links**:
  - With Zigbee2MQTT and a **network map** (requested from the ZigSight
    panel), links are the neighbour tables reported by the devices, coloured
    by LQI (green excellent ≥ 200, light green good ≥ 150, orange fair ≥ 100,
    red poor). A pair of devices is drawn once, with the best LQI of both
    directions.
  - Without a network map (not requested yet, or ZHA), every device is drawn
    linked to the coordinator with a dashed grey line: these links are
    **inferred** and don't say how messages are routed.
- **Highlight issues** colours devices with connectivity or battery drain
  warnings, offline devices and devices with a health score below 50 in red.

The cards refresh every minute; the **Refresh** button reloads immediately.

## Data source

Both cards read `GET /api/zigsight/topology` (any logged in user):

```json
{
  "nodes": [
    {"id": "0x00124b0024c1a2b3", "label": "Coordinator", "type": "coordinator", ...},
    {"id": "0x0017880104e45517", "label": "Living Room Lamp", "type": "router",
     "model": "Hue white and color ambiance E26/E27", "manufacturer": "Philips",
     "available": true, "link_quality": 156, "battery": null, "health_score": 95.0,
     "last_seen": "2026-09-24T08:10:00+00:00", "source": "zigbee2mqtt", "analytics": {...}}
  ],
  "edges": [
    {"from": "0x00124b0024c1a2b3", "to": "0x0017880104e45517", "link_quality": 156,
     "relationship": "child", "depth": 1, "inferred": false}
  ],
  "links_source": "networkmap",
  "coordinator_id": "0x00124b0024c1a2b3",
  "network_map": {"supported": true, "updated": "...", "requested": "..."},
  "network": {"channel": 15, "pan_id": 6754, ...},
  "device_count": 6, "coordinator_count": 1, "router_count": 2,
  "end_device_count": 3, "unknown_count": 0
}
```

## Troubleshooting

### Card not loading ("Custom element doesn't exist")

- Check the resource URL is `/zigsight_static/...` and the type is
  *JavaScript module*.
- Open `http://<your-ha>/zigsight_static/topology-card.js` in the browser: it
  must return JavaScript. If it returns 404 the ZigSight integration is not
  set up (the files are served once the integration is loaded).
- Hard-reload the browser tab (the Companion app: *Settings* → *Companion app*
  → *Debugging* → *Reset frontend cache*).

### "No ZigSight coordinator found"

The ZigSight integration has no loaded config entry. Check **Settings** →
**Devices & services** → ZigSight.

### All links are dashed / grey

No network map yet: open the ZigSight panel, **Topology** tab, and click
**Request network map** (Zigbee2MQTT only).

## See also

- [Frontend panel](frontend_panel.md)
- [Getting started](getting_started.md)
