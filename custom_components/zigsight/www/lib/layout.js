/**
 * Graph layouts for the ZigSight topology view (no DOM access, unit tested
 * with `node --test`).
 *
 * Both layouts are deterministic: the same topology always gives the same
 * picture, so refreshing the data doesn't reshuffle the graph.
 */

const TWO_PI = Math.PI * 2;

/** Build an undirected adjacency map (id -> Set of ids) of known nodes. */
export function adjacency(nodes, edges) {
  const ids = new Set(nodes.map((node) => node.id));
  const adj = new Map();
  for (const id of ids) adj.set(id, new Set());
  for (const edge of edges || []) {
    if (!ids.has(edge.from) || !ids.has(edge.to) || edge.from === edge.to) continue;
    adj.get(edge.from).add(edge.to);
    adj.get(edge.to).add(edge.from);
  }
  return adj;
}

/**
 * Hop count of every node from the root (breadth first). Nodes that can't
 * be reached get `maxDepth + 1`.
 */
export function depths(nodes, edges, rootId) {
  const adj = adjacency(nodes, edges);
  const result = new Map();
  if (adj.has(rootId)) {
    result.set(rootId, 0);
    const queue = [rootId];
    while (queue.length) {
      const id = queue.shift();
      for (const next of [...adj.get(id)].sort()) {
        if (!result.has(next)) {
          result.set(next, result.get(id) + 1);
          queue.push(next);
        }
      }
    }
  }
  let max = 0;
  for (const depth of result.values()) max = Math.max(max, depth);
  for (const node of nodes) {
    if (!result.has(node.id)) result.set(node.id, max + 1);
  }
  return result;
}

const TYPE_ORDER = { coordinator: 0, router: 1, end_device: 2, unknown: 3 };

function compareNodes(a, b) {
  const byType = (TYPE_ORDER[a.type] ?? 9) - (TYPE_ORDER[b.type] ?? 9);
  if (byType) return byType;
  return String(a.label ?? a.id).localeCompare(String(b.label ?? b.id));
}

/**
 * Radial tree: the root in the centre, every hop further out one ring. A
 * breadth first spanning tree gives every node a wedge of the circle sized
 * by its number of leaves, so children sit next to their parent. Nodes not
 * connected to the root go on an extra outer ring.
 */
export function radialLayout(nodes, edges, rootId, { ringGap = 120, minArc = 60 } = {}) {
  const positions = new Map();
  if (!nodes.length) return positions;
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const adj = adjacency(nodes, edges);
  const root = byId.has(rootId) ? rootId : [...nodes].sort(compareNodes)[0].id;

  // Breadth first spanning tree (children sorted for a stable picture).
  const children = new Map([[root, []]]);
  const depthOf = new Map([[root, 0]]);
  const queue = [root];
  while (queue.length) {
    const id = queue.shift();
    const next = [...adj.get(id)]
      .filter((other) => !depthOf.has(other))
      .map((other) => byId.get(other))
      .sort(compareNodes);
    for (const child of next) {
      depthOf.set(child.id, depthOf.get(id) + 1);
      children.set(child.id, []);
      children.get(id).push(child.id);
      queue.push(child.id);
    }
  }
  const leaves = new Map();
  const countLeaves = (id) => {
    const kids = children.get(id);
    const count = kids.length ? kids.reduce((sum, kid) => sum + countLeaves(kid), 0) : 1;
    leaves.set(id, count);
    return count;
  };
  countLeaves(root);

  const orphans = nodes.filter((node) => !depthOf.has(node.id)).sort(compareNodes);
  let maxDepth = 0;
  for (const depth of depthOf.values()) maxDepth = Math.max(maxDepth, depth);
  // Enough room on the outer ring for every leaf.
  const gap = Math.max(ringGap, (leaves.get(root) * minArc) / (TWO_PI * Math.max(maxDepth, 1)));

  positions.set(root, { x: 0, y: 0 });
  const place = (id, start, end) => {
    const kids = children.get(id);
    let cursor = start;
    for (const kid of kids) {
      const span = ((end - start) * leaves.get(kid)) / leaves.get(id);
      const angle = cursor + span / 2 - Math.PI / 2;
      const radius = depthOf.get(kid) * gap;
      positions.set(kid, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) });
      place(kid, cursor, cursor + span);
      cursor += span;
    }
  };
  place(root, 0, TWO_PI);

  if (orphans.length) {
    const radius = Math.max((maxDepth + 1) * gap, (orphans.length * minArc) / TWO_PI);
    orphans.forEach((node, index) => {
      const angle = (index / orphans.length) * TWO_PI - Math.PI / 2;
      positions.set(node.id, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) });
    });
  }
  return positions;
}

/**
 * Force directed layout (Fruchterman-Reingold), seeded with the radial
 * layout, root pinned in the centre, with a weak pull towards the centre. O(n^2) per iteration: fine for the few
 * hundred nodes of a Zigbee network.
 */
export function forceLayout(
  nodes,
  edges,
  rootId,
  { iterations = 300, idealLength = 110, gravity = 0.05 } = {},
) {
  const positions = radialLayout(nodes, edges, rootId);
  const ids = nodes.map((node) => node.id);
  const count = ids.length;
  if (count < 2) return positions;

  const links = [];
  const adj = adjacency(nodes, edges);
  for (const [id, neighbours] of adj) {
    for (const other of neighbours) if (id < other) links.push([id, other]);
  }

  const k = idealLength;
  let temperature = k * 2;
  const cooling = temperature / (iterations + 1);
  const disp = new Map(ids.map((id) => [id, { x: 0, y: 0 }]));

  for (let iter = 0; iter < iterations; iter += 1) {
    for (const id of ids) {
      const d = disp.get(id);
      d.x = 0;
      d.y = 0;
    }
    for (let i = 0; i < count; i += 1) {
      const a = positions.get(ids[i]);
      for (let j = i + 1; j < count; j += 1) {
        const b = positions.get(ids[j]);
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let dist = Math.hypot(dx, dy);
        if (dist < 0.01) {
          // Deterministic nudge for overlapping nodes.
          dx = (i - j) * 0.01;
          dy = 0.01;
          dist = Math.hypot(dx, dy);
        }
        const force = (k * k) / dist;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        const da = disp.get(ids[i]);
        const db = disp.get(ids[j]);
        da.x += fx;
        da.y += fy;
        db.x -= fx;
        db.y -= fy;
      }
    }
    for (const [from, to] of links) {
      const a = positions.get(from);
      const b = positions.get(to);
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const dist = Math.max(Math.hypot(dx, dy), 0.01);
      const force = (dist * dist) / k;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      disp.get(from).x -= fx;
      disp.get(from).y -= fy;
      disp.get(to).x += fx;
      disp.get(to).y += fy;
    }
    for (const id of ids) {
      if (id === rootId) continue;
      const d = disp.get(id);
      // Weak gravity towards the centre keeps disconnected nodes close.
      const p0 = positions.get(id);
      const r = Math.hypot(p0.x, p0.y);
      if (r > 0.01) {
        const pull = (gravity * r * r) / k;
        d.x -= (p0.x / r) * pull;
        d.y -= (p0.y / r) * pull;
      }
      const length = Math.hypot(d.x, d.y);
      if (length < 1e-9) continue;
      const step = Math.min(length, temperature);
      const p = positions.get(id);
      p.x += (d.x / length) * step;
      p.y += (d.y / length) * step;
    }
    temperature = Math.max(temperature - cooling, 1);
  }
  return positions;
}

/** Layout dispatcher. */
export function computeLayout(nodes, edges, rootId, mode = "radial") {
  return mode === "force"
    ? forceLayout(nodes, edges, rootId)
    : radialLayout(nodes, edges, rootId);
}

/** Bounding box of positions, padded. */
export function bounds(positions, padding = 60) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const { x, y } of positions.values()) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  if (!Number.isFinite(minX)) return { x: -100, y: -100, width: 200, height: 200 };
  return {
    x: minX - padding,
    y: minY - padding,
    width: maxX - minX + padding * 2,
    height: maxY - minY + padding * 2,
  };
}
