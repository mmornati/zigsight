# ZigSight frontend files

Served by the integration at `/zigsight_static/` (see `async_setup` in
`../__init__.py`). No copy into Home Assistant's `www/` folder and no build
step are needed, and nothing is loaded from a CDN.

| File | What |
|------|------|
| `zigsight-panel.js` | Sidebar panel `<zigsight-panel>`, registered automatically (admin only) |
| `topology-card.js` | Lovelace card `custom:zigsight-topology-card` (device grid) |
| `topology-visualization.js` | Lovelace card `custom:zigsight-topology-visualization` (graph) |
| `lib/topology-graph.js` | `<zigsight-topology-graph>`: SVG graph with pan / zoom / selection, used by the panel and the graph card |
| `lib/layout.js` | Radial tree and force directed layouts (pure functions) |
| `lib/format.js`, `lib/wifi.js` | Formatting and Wi-Fi scan validation helpers (pure functions) |
| `vendor/` | Vendored Lit build and its license, see `vendor/README.md` |

## Using the cards

Add a dashboard resource (Settings → Dashboards → Resources) of type
*JavaScript module* with the URL `/zigsight_static/topology-card.js` and/or
`/zigsight_static/topology-visualization.js`, then:

```yaml
type: custom:zigsight-topology-card
title: Zigbee Network Topology
```

```yaml
type: custom:zigsight-topology-visualization
title: Network Topology
layout: radial   # or force
height: 500
```

See `docs/ui.md` and `docs/frontend_panel.md` for the user documentation and
`docs/DEVELOPER_README.md` (Frontend Development) for the development rules
(Lit templates only, no `innerHTML`; checked by `tests/test_frontend_assets.py`
and `node --test "tests/js/*.test.mjs"`).
