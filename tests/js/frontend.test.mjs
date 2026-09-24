// Unit tests for the DOM free frontend helpers. Run with:
//   node --test tests/js/
import assert from "node:assert/strict";
import test from "node:test";

import {
  apiErrorMessage,
  formatNumber,
  hasIssues,
  healthStatus,
  lqiLevel,
  typeLabel,
} from "../../custom_components/zigsight/www/lib/format.js";
import {
  adjacency,
  bounds,
  computeLayout,
  depths,
  radialLayout,
} from "../../custom_components/zigsight/www/lib/layout.js";
import {
  parseWifiJson,
  validateAccessPoints,
} from "../../custom_components/zigsight/www/lib/wifi.js";

const nodes = [
  { id: "c", type: "coordinator", label: "Coordinator" },
  { id: "r1", type: "router", label: "Plug" },
  { id: "r2", type: "router", label: "Lamp" },
  { id: "e1", type: "end_device", label: "Sensor" },
  { id: "lonely", type: "end_device", label: "Lonely" },
];
const edges = [
  { from: "c", to: "r1" },
  { from: "c", to: "r2" },
  { from: "r2", to: "e1" },
  { from: "r2", to: "ghost" },
];

test("adjacency ignores unknown endpoints", () => {
  const adj = adjacency(nodes, edges);
  assert.deepEqual([...adj.get("r2")].sort(), ["c", "e1"]);
  assert.equal(adj.has("ghost"), false);
});

test("depths are hop counts, unreachable nodes go last", () => {
  const result = depths(nodes, edges, "c");
  assert.equal(result.get("c"), 0);
  assert.equal(result.get("r1"), 1);
  assert.equal(result.get("e1"), 2);
  assert.equal(result.get("lonely"), 3);
});

test("radial layout puts the root in the centre and is deterministic", () => {
  const first = radialLayout(nodes, edges, "c");
  const second = radialLayout(nodes, edges, "c");
  assert.deepEqual(first.get("c"), { x: 0, y: 0 });
  assert.deepEqual([...first.entries()], [...second.entries()]);
  const r1 = first.get("r1");
  const e1 = first.get("e1");
  assert.ok(Math.hypot(e1.x, e1.y) > Math.hypot(r1.x, r1.y));
});

test("force layout keeps the root pinned and separates nodes", () => {
  const positions = computeLayout(nodes, edges, "c", "force");
  assert.deepEqual(positions.get("c"), { x: 0, y: 0 });
  for (const a of nodes) {
    for (const b of nodes) {
      if (a.id >= b.id) continue;
      const pa = positions.get(a.id);
      const pb = positions.get(b.id);
      assert.ok(Math.hypot(pa.x - pb.x, pa.y - pb.y) > 10, `${a.id}/${b.id} overlap`);
    }
  }
  assert.ok([...positions.values()].every((p) => Number.isFinite(p.x) && Number.isFinite(p.y)));
});

test("bounds pads the positions", () => {
  const box = bounds(new Map([["a", { x: 0, y: 0 }], ["b", { x: 100, y: 50 }]]), 10);
  assert.deepEqual(box, { x: -10, y: -10, width: 120, height: 70 });
  assert.deepEqual(bounds(new Map()), { x: -100, y: -100, width: 200, height: 200 });
});

test("format helpers", () => {
  assert.equal(lqiLevel(210), "excellent");
  assert.equal(lqiLevel(160), "good");
  assert.equal(lqiLevel(120), "fair");
  assert.equal(lqiLevel(12), "poor");
  assert.equal(lqiLevel(null), "unknown");
  assert.equal(typeLabel("end_device"), "End device");
  assert.equal(typeLabel("<img>"), "Unknown type");
  assert.equal(healthStatus(90), "Healthy");
  assert.equal(healthStatus(60), "Warning");
  assert.equal(healthStatus(10), "Critical");
  assert.equal(healthStatus(undefined), "Unknown");
  assert.equal(formatNumber(3.14159, 2, "%"), "3.14%");
  assert.equal(formatNumber(null), "—");
  assert.equal(hasIssues({ analytics: { connectivity_warning: true } }), true);
  assert.equal(hasIssues({ available: false }), true);
  assert.equal(hasIssues({ analytics_metrics: { health_score: 20 } }), true);
  assert.equal(hasIssues({ health_score: 90, analytics: {} }), false);
});

test("apiErrorMessage understands hass.callApi errors", () => {
  assert.equal(apiErrorMessage({ body: { error: "Invalid request" } }), "Invalid request");
  assert.equal(apiErrorMessage({ status_code: 401 }), "Request failed (401)");
  assert.equal(apiErrorMessage(new Error("boom")), "boom");
  assert.equal(apiErrorMessage("text"), "text");
  assert.equal(apiErrorMessage(null), "Unknown error");
});

test("validateAccessPoints accepts table rows", () => {
  const { accessPoints, errors } = validateAccessPoints([
    { channel: "6", rssi: "-45", ssid: "  home " },
    { channel: 11, rssi: -80 },
  ]);
  assert.deepEqual(errors, []);
  assert.deepEqual(accessPoints, [
    { channel: 6, rssi: -45, ssid: "home" },
    { channel: 11, rssi: -80 },
  ]);
});

test("validateAccessPoints rejects bad rows", () => {
  assert.equal(validateAccessPoints([]).errors.length, 1);
  assert.match(validateAccessPoints([{ channel: 15, rssi: -40 }]).errors[0], /1 to 14/);
  assert.match(validateAccessPoints([{ channel: 6, rssi: 10 }]).errors[0], /RSSI/);
  assert.match(validateAccessPoints([{ channel: 6, rssi: "" }]).errors[0], /RSSI/);
  assert.match(validateAccessPoints([null]).errors[0], /expected an object/);
  assert.match(validateAccessPoints("x").errors[0], /list/);
});

test("parseWifiJson handles both formats and bad JSON", () => {
  assert.equal(parseWifiJson('[{"channel": 1, "rssi": -40}]').accessPoints.length, 1);
  assert.equal(
    parseWifiJson('{"access_points": [{"channel": 1, "rssi": -40}]}').accessPoints.length,
    1,
  );
  assert.match(parseWifiJson("{nope").errors[0], /Invalid JSON/);
});
