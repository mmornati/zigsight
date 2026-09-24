# ZigSight Frontend Panel

ZigSight adds a **ZigSight** entry to the Home Assistant sidebar with four
tabs: **Devices**, **Topology**, **Analytics** and **Channel**.

## Setup

There is nothing to configure. When the ZigSight integration is set up it:

- serves its frontend files from `/zigsight_static/` (the
  `custom_components/zigsight/www` folder of the integration), and
- registers the sidebar panel at `/zigsight`, visible to **administrators**
  only (the panel can trigger a network scan and a Wi-Fi analysis).

The panel is removed from the sidebar when the integration is removed or
disabled. Everything it needs (including the Lit library) ships with the
integration: it works without internet access.

### Upgrading from ZigSight 1.x (manual panel setup)

Older versions asked you to copy `zigsight-panel.js` to `www/` and to add a
`panel_custom:` entry to `configuration.yaml`. That is no longer needed:

1. Remove the `panel_custom:` entry whose `url_path` is `zigsight` from
   `configuration.yaml`.
2. Delete the copied file (`www/community/zigsight/zigsight-panel.js` or
   `www/zigsight/zigsight-panel.js`).
3. Restart Home Assistant.

4. In **Settings** → **Dashboards** → **Resources**, replace resources
   pointing to `/local/.../zigsight/...` with the `/zigsight_static/...` ones
   (see [UI](ui.md)).

Until the YAML entry is removed ZigSight keeps it (your copied, outdated
panel is shown), logs a warning and raises a **repair issue** ("Remove the old
manual ZigSight panel setup", in **Settings** → **Repairs**) listing the old
panels. The old copy has known security issues, so please don't ignore it.
The issue is also raised when another panel (under any URL) loads a
`zigsight-panel` element from a copied file, since only one definition of
that element can be active in the browser. It clears once ZigSight's own
panel registers without conflicts.

## Devices

All devices known to ZigSight, as cards: name, availability (green online,
red offline, grey unknown), type and model, link quality (coloured by
quality), battery and health score, plus warning chips (battery drain,
connectivity issues). Search by name, IEEE address, model or manufacturer,
and filter by type. Click a device for its details: IEEE address, model,
manufacturer, power source, availability, metrics and analytics.

## Topology

The network as a graph:

- **Nodes** are keyed by IEEE address and labelled with the friendly name;
  the shape and colour show the type (coordinator, router, end device,
  unknown). Offline devices are faded. Click a node for its details and its
  neighbours with the LQI of each link.
- **Links** come from a Zigbee2MQTT **network map** when one has been
  received: the neighbour tables reported by the devices, coloured by LQI,
  one link per pair of devices (best LQI of both directions), oriented
  parent → child when known.
- Without a network map, every device is drawn linked to the coordinator
  with dashed grey lines, and a banner says the links are **inferred**. This
  is always the case with ZHA.

### Request network map (Zigbee2MQTT)

Click **Request network map** to publish a raw network map request to
Zigbee2MQTT (`<base_topic>/bridge/request/networkmap`, type `raw`). The
panel then polls until the response arrives (usually well under a minute,
longer on big networks; the panel waits up to 5 minutes). Mapping the network
asks every router for its neighbour table: it generates Zigbee traffic, so
don't request it too often. The last map is kept in memory until Home
Assistant restarts; a map also sent by another tool (e.g. the Zigbee2MQTT
frontend with type *raw*) is used as well.

Only administrators can request a map (`POST /api/zigsight/topology/networkmap`).
While a request is pending (no response yet, less than 2 minutes old) further
requests are not sent again to Zigbee2MQTT: the endpoint answers with the
pending request (`"pending": true`) and the panel shows **Scanning…**, also
when it is opened again or in another browser.

### Controls

- **Layout**: *Rings* places the coordinator in the centre and every hop one
  ring further out, children next to their parent. *Force directed* spreads
  the graph so that linked devices attract and others repel.
- **Type filters**, **LQI labels**, **Highlight issues** (warnings, offline,
  health < 50 in red) and **Fit**.
- Drag the background to pan, use the mouse wheel / trackpad to zoom.

## Analytics

Device count, average health score, devices needing attention (offline,
connectivity warning, battery drain, health < 50) and devices with a battery
at or below 20%. Click a device to open its details.

## Channel

- **Current Zigbee channel**: from Zigbee2MQTT's `bridge/info`. With ZHA it
  is shown as unknown (see the ZHA network settings).
- **Wi-Fi networks around the coordinator**: enter the 2.4 GHz access points
  you can see near the coordinator (from your router's admin page or a Wi-Fi
  analyser app) as rows of *Wi-Fi channel* (1-14), *RSSI* in dBm (-120 to 0)
  and an optional SSID, or switch to **Paste JSON**:

  ```json
  [
    {"channel": 1, "rssi": -45, "ssid": "Home"},
    {"channel": 6, "rssi": -72},
    {"channel": 11, "rssi": -80}
  ]
  ```

  (`{"access_points": [...]}` is accepted too.)
- **Recommend a Zigbee channel** sends the data to
  `POST /api/zigsight/channel-recommendation` (administrators only) and shows
  the recommended channel among 11, 15, 20 and 25, the interference score of
  each (lower is better) and an explanation. The last result is also shown
  when you reopen the panel (until Home Assistant restarts).

Changing the channel of an existing Zigbee network is disruptive (some
devices may need to be re-paired): only do it if you have interference
problems. See [Wi-Fi recommendation](wifi_recommendation.md) for how the
score is computed; the `zigsight.recommend_channel` service does the same from
automations and scripts.

## REST API

The panel only uses ZigSight's REST API (authenticated with your Home
Assistant session):

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/api/zigsight/devices` | admin | device records |
| GET | `/api/zigsight/topology` | user | nodes, edges, network map status, network info (see [UI](ui.md#data-source)); also polled by the `zigsight-topology-card`/`zigsight-topology-visualization` Lovelace cards, so it stays readable by any authenticated user, not just admins |
| POST | `/api/zigsight/topology/networkmap` | admin | request a raw network map (returns 202) |
| GET | `/api/zigsight/analytics/overview` | admin | fleet-wide health/battery/link-quality summary |
| GET | `/api/zigsight/analytics/trends` | admin | a metric's history for one device, or the network |
| GET | `/api/zigsight/analytics/export` | admin | devices as JSON or CSV (`?format=csv`) |
| GET | `/api/zigsight/channel-recommendation` | admin | current channel and last recommendation |
| POST | `/api/zigsight/channel-recommendation` | admin | compute a recommendation: `{"mode": "manual", "wifi_scan_data": [...]}` |
| GET | `/api/zigsight/recommendation-history` | admin | last 10 recommendations |

Invalid requests get a `400` with an `error` message; non-admin users get
`401` on every admin endpoint above. `topology` is the one exception (see
its row): it is intentionally readable by any authenticated user, because
the Lovelace cards that poll it every 60 seconds may be on a dashboard a
non-admin user can see, and Home Assistant's login-attempt tracking treats
a rejected admin check on a repeating poll like a failed login attempt
(spamming notifications and, with `ip_ban_enabled`, banning the viewer).

## Troubleshooting

### The panel is not in the sidebar

- It is only shown to administrators.
- Check the integration is loaded (**Settings** → **Devices & services** →
  ZigSight).
- Look for the `panel_custom` warning described in
  [Upgrading](#upgrading-from-zigsight-1x-manual-panel-setup).

### "Unable to load custom panel" / blank panel

Hard-reload the browser tab (the Companion app: *Settings* → *Companion app*
→ *Debugging* → *Reset frontend cache*). The panel module URL contains the
ZigSight version, so updates are picked up after a reload.

### "Request network map" never finishes

Check that Zigbee2MQTT is online and look at its log for the network map
request; very large networks can take several minutes. Refresh the panel
later: the map is used as soon as it arrives.

### "No ZigSight coordinator found"

The integration has no loaded config entry.

## See also

- [Dashboard cards](ui.md)
- [Getting started](getting_started.md)
- [Wi-Fi channel recommendation](wifi_recommendation.md)
