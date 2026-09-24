/**
 * <zigsight-topology-graph>: SVG rendering of a ZigSight topology
 * (`GET /api/zigsight/topology`), with pan, zoom and node selection.
 *
 * Self contained (vendored Lit, no CDN). All text goes through Lit
 * templates, so device names are escaped; tooltips are SVG <title> text.
 *
 * Properties:
 *   topology        topology API response
 *   layout          "radial" (default) or "force"
 *   showLqi         show LQI labels on links
 *   visibleTypes    node types to show (default: all)
 *   highlightIssues colour nodes with warnings / poor health in red
 *   selectedId      id of the selected node
 * Events:
 *   node-selected   detail: {node} (node is null when the background is clicked)
 */

import { LitElement, css, html, nothing, svg } from "../vendor/lit-core.min.js";
import { bounds, computeLayout } from "./layout.js";
import {
  ISSUE_COLOR,
  LQI_COLORS,
  TYPE_COLORS,
  hasIssues,
  lqiColor,
  typeLabel,
} from "./format.js";

const ALL_TYPES = ["coordinator", "router", "end_device", "unknown"];
const NODE_RADIUS = { coordinator: 16, router: 12, end_device: 9, unknown: 9 };
const LABEL_MAX = 22;

function truncate(text, max = LABEL_MAX) {
  const value = String(text ?? "");
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function nodeTooltip(node) {
  const lines = [node.label, typeLabel(node.type)];
  if (node.label !== node.id) lines.push(node.id);
  if (node.model) lines.push(node.manufacturer ? `${node.manufacturer} ${node.model}` : node.model);
  if (typeof node.link_quality === "number") lines.push(`LQI: ${node.link_quality}`);
  if (typeof node.battery === "number") lines.push(`Battery: ${node.battery}%`);
  if (typeof node.health_score === "number") lines.push(`Health: ${Math.round(node.health_score)}`);
  if (node.available === false) lines.push("Offline");
  return lines.join("\n");
}

export class ZigSightTopologyGraph extends LitElement {
  static properties = {
    topology: { attribute: false },
    layout: { type: String },
    showLqi: { type: Boolean, attribute: "show-lqi" },
    visibleTypes: { attribute: false },
    highlightIssues: { type: Boolean, attribute: "highlight-issues" },
    selectedId: { type: String, attribute: "selected-id" },
    _view: { state: true },
    _size: { state: true },
  };

  constructor() {
    super();
    this.topology = null;
    this.layout = "radial";
    this.showLqi = true;
    this.visibleTypes = ALL_TYPES;
    this.highlightIssues = false;
    this.selectedId = null;
    this._positions = new Map();
    this._layoutKey = null;
    this._view = { x: -200, y: -200, w: 400, h: 400 };
    this._drag = null;
    this._size = { width: 800, height: 500 };
  }

  connectedCallback() {
    super.connectedCallback();
    this._resizeObserver = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (rect && rect.width && rect.height) {
        this._size = { width: rect.width, height: rect.height };
      }
    });
    this._observed = null;
    this.requestUpdate();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._resizeObserver?.disconnect();
    this._resizeObserver = null;
  }

  updated() {
    // The <svg> only exists once there are nodes to draw.
    const svgEl = this.renderRoot.querySelector("svg");
    if (svgEl && svgEl !== this._observed && this._resizeObserver) {
      this._observed = svgEl;
      this._resizeObserver.observe(svgEl);
    }
  }

  /** Graph units per screen pixel: nodes and labels keep a constant size. */
  _unitsPerPixel() {
    const { width, height } = this._size;
    return Math.max(this._view.w / width, this._view.h / height) || 1;
  }

  willUpdate(changed) {
    if (changed.has("topology") || changed.has("layout")) {
      const nodes = this.topology?.nodes || [];
      const edges = this.topology?.edges || [];
      const key = [
        this.layout,
        nodes.map((n) => `${n.id}:${n.type}`).sort().join(","),
        edges.map((e) => `${e.from}>${e.to}`).sort().join(","),
      ].join("|");
      // Only re-layout when the graph itself changed (not on every refresh).
      if (key !== this._layoutKey) {
        this._layoutKey = key;
        this._positions = computeLayout(
          nodes,
          edges,
          this.topology?.coordinator_id,
          this.layout,
        );
        this._fitView();
      }
    }
  }

  /** Zoom to show the whole graph. */
  fit() {
    this._fitView();
  }

  _fitView() {
    const box = bounds(this._positions);
    this._view = { x: box.x, y: box.y, w: box.width, h: box.height };
  }

  _svgPoint(event) {
    const svgEl = this.renderRoot.querySelector("svg");
    const ctm = svgEl?.getScreenCTM();
    if (!ctm) return null;
    const point = svgEl.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(ctm.inverse());
  }

  _onWheel(event) {
    event.preventDefault();
    const point = this._svgPoint(event);
    if (!point) return;
    const factor = event.deltaY > 0 ? 1.15 : 1 / 1.15;
    const view = this._view;
    const w = Math.min(Math.max(view.w * factor, 80), 20000);
    const h = (view.h * w) / view.w;
    this._view = {
      x: point.x - ((point.x - view.x) * w) / view.w,
      y: point.y - ((point.y - view.y) * h) / view.h,
      w,
      h,
    };
  }

  _onPointerDown(event) {
    if (event.button !== 0 || event.target.closest?.(".node")) return;
    const svgEl = event.currentTarget;
    const ctm = svgEl.getScreenCTM();
    if (!ctm) return;
    svgEl.setPointerCapture?.(event.pointerId);
    this._drag = {
      clientX: event.clientX,
      clientY: event.clientY,
      view: this._view,
      scale: 1 / ctm.a,
      moved: false,
    };
  }

  _onPointerMove(event) {
    const drag = this._drag;
    if (!drag) return;
    const dx = (event.clientX - drag.clientX) * drag.scale;
    const dy = (event.clientY - drag.clientY) * drag.scale;
    if (Math.abs(dx) + Math.abs(dy) > 2 * drag.scale) drag.moved = true;
    this._view = { ...drag.view, x: drag.view.x - dx, y: drag.view.y - dy };
  }

  _onPointerUp() {
    const drag = this._drag;
    this._drag = null;
    if (drag && !drag.moved) this._select(null);
  }

  _select(node) {
    this.dispatchEvent(
      new CustomEvent("node-selected", { detail: { node }, bubbles: true, composed: true }),
    );
  }

  _onNodeKey(event, node) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      this._select(node);
    }
  }

  _nodeShape(node, fill, radius, unit) {
    const stroke = node.id === this.selectedId ? "var(--primary-text-color, #212121)" : "#ffffff";
    const strokeWidth = (node.id === this.selectedId ? 3 : 1.5) * unit;
    if (node.type === "coordinator") {
      const r = radius * 1.25;
      return svg`<polygon points="0,${-r} ${r},0 0,${r} ${-r},0"
        fill=${fill} stroke=${stroke} stroke-width=${strokeWidth}></polygon>`;
    }
    if (node.type === "router") {
      return svg`<rect x=${-radius} y=${-radius} width=${radius * 2} height=${radius * 2}
        rx=${3 * unit} fill=${fill} stroke=${stroke} stroke-width=${strokeWidth}></rect>`;
    }
    return svg`<circle r=${radius} fill=${fill} stroke=${stroke} stroke-width=${strokeWidth}
      stroke-dasharray=${node.type === "unknown" ? `${3 * unit} ${2 * unit}` : nothing}></circle>`;
  }

  render() {
    const nodes = this.topology?.nodes || [];
    const edges = this.topology?.edges || [];
    if (!nodes.length) {
      return html`<div class="empty">No devices to show yet.</div>`;
    }
    const visible = new Set(this.visibleTypes || ALL_TYPES);
    const shown = new Map(
      nodes.filter((node) => visible.has(node.type)).map((node) => [node.id, node]),
    );
    const view = this._view;
    const unit = this._unitsPerPixel();
    const labelSize = 12 * unit;

    const edgeParts = [];
    const lqiParts = [];
    for (const edge of edges) {
      const from = this._positions.get(edge.from);
      const to = this._positions.get(edge.to);
      if (!from || !to || !shown.has(edge.from) || !shown.has(edge.to)) continue;
      const lqi = edge.link_quality;
      const title = [
        `${shown.get(edge.from).label} ↔ ${shown.get(edge.to).label}`,
        `LQI: ${typeof lqi === "number" ? lqi : "unknown"}`,
        edge.relationship ? `Relationship: ${edge.relationship}` : "",
        edge.inferred ? "Inferred link (no network map yet)" : "",
      ]
        .filter(Boolean)
        .join("\n");
      // Slightly curved links: links that would overlap on a straight line
      // (e.g. two routers on opposite sides of the coordinator) stay visible.
      const curve = edge.inferred ? 0 : 0.12;
      const mx = (from.x + to.x) / 2;
      const my = (from.y + to.y) / 2;
      const cx = mx - (to.y - from.y) * curve;
      const cy = my + (to.x - from.x) * curve;
      edgeParts.push(svg`<path class=${edge.inferred ? "edge inferred" : "edge"}
          d="M ${from.x} ${from.y} Q ${cx} ${cy} ${to.x} ${to.y}"
          fill="none"
          stroke=${edge.inferred ? LQI_COLORS.unknown : lqiColor(lqi)}
          vector-effect="non-scaling-stroke"
          stroke-width=${edge.inferred ? 1.5 : typeof lqi === "number" ? 1 + lqi / 85 : 1.5}>
          <title>${title}</title></path>`);
      if (this.showLqi && !edge.inferred && typeof lqi === "number") {
        lqiParts.push(svg`<text class="lqi" x=${(mx + cx) / 2} y=${(my + cy) / 2}
            font-size=${labelSize * 0.85} stroke-width=${3 * unit} text-anchor="middle"
            dominant-baseline="middle">${lqi}</text>`);
      }
    }

    const nodeParts = [];
    for (const node of shown.values()) {
      const pos = this._positions.get(node.id);
      if (!pos) continue;
      const radius = (NODE_RADIUS[node.type] || NODE_RADIUS.unknown) * unit;
      const issue = this.highlightIssues && hasIssues(node);
      const fill = issue ? ISSUE_COLOR : TYPE_COLORS[node.type] || TYPE_COLORS.unknown;
      nodeParts.push(svg`<g class=${node.available === false ? "node offline" : "node"}
          transform="translate(${pos.x} ${pos.y})" tabindex="0" role="button"
          aria-label=${`${node.label} (${typeLabel(node.type)})`}
          @click=${() => this._select(node)}
          @keydown=${(event) => this._onNodeKey(event, node)}>
          <title>${nodeTooltip(node)}</title>
          ${this._nodeShape(node, fill, radius, unit)}
          <text class="label" y=${radius + labelSize + 2 * unit} font-size=${labelSize}
            stroke-width=${3 * unit}
            text-anchor="middle">${truncate(node.label)}</text>
        </g>`);
    }

    return html`
      <svg
        viewBox="${view.x} ${view.y} ${view.w} ${view.h}"
        preserveAspectRatio="xMidYMid meet"
        role="group"
        aria-label="Zigbee network topology"
        @wheel=${this._onWheel}
        @pointerdown=${this._onPointerDown}
        @pointermove=${this._onPointerMove}
        @pointerup=${this._onPointerUp}
        @pointercancel=${this._onPointerUp}
      >
        <g class="edges">${edgeParts}</g>
        <g class="lqis">${lqiParts}</g>
        <g class="nodes">${nodeParts}</g>
      </svg>
      <div class="legend">
        ${ALL_TYPES.map(
          (type) => html`<span class="legend-item"
            ><span class="swatch ${type}" style="background:${TYPE_COLORS[type]}"></span
            >${typeLabel(type)}</span
          >`,
        )}
        ${this.highlightIssues
          ? html`<span class="legend-item"
              ><span class="swatch" style="background:${ISSUE_COLOR}"></span>Needs attention</span
            >`
          : nothing}
        ${["excellent", "good", "fair", "poor"].map(
          (level) => html`<span class="legend-item"
            ><span class="line" style="background:${LQI_COLORS[level]}"></span>LQI ${level}</span
          >`,
        )}
        <span class="legend-item"><span class="line dashed"></span>Inferred</span>
      </div>
    `;
  }

  static styles = css`
    :host {
      display: flex;
      flex-direction: column;
      min-height: 320px;
    }
    svg {
      flex: 1;
      width: 100%;
      min-height: 320px;
      touch-action: none;
      cursor: grab;
      user-select: none;
      background: var(--card-background-color, #fff);
    }
    svg:active {
      cursor: grabbing;
    }
    .edge {
      stroke-linecap: round;
      opacity: 0.85;
    }
    .edge.inferred {
      stroke-dasharray: 4 4;
      opacity: 0.6;
    }
    .lqi {
      fill: var(--secondary-text-color, #555);
      paint-order: stroke;
      stroke: var(--card-background-color, #fff);
      pointer-events: none;
    }
    .node {
      cursor: pointer;
      outline: none;
    }
    .node.offline {
      opacity: 0.45;
    }
    .node:focus-visible > :not(text):not(title) {
      stroke: var(--primary-color, #03a9f4);
    }
    .label {
      fill: var(--primary-text-color, #212121);
      paint-order: stroke;
      stroke: var(--card-background-color, #fff);
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 6px 16px;
      padding: 8px 12px;
      font-size: 12px;
      color: var(--secondary-text-color, #555);
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .swatch {
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }
    .swatch.router {
      border-radius: 2px;
    }
    .swatch.coordinator {
      border-radius: 1px;
      transform: rotate(45deg) scale(0.85);
    }
    .line {
      width: 20px;
      height: 3px;
      border-radius: 2px;
    }
    .line.dashed {
      background: repeating-linear-gradient(
        90deg,
        #9e9e9e 0 4px,
        transparent 4px 8px
      );
    }
    .empty {
      padding: 32px;
      text-align: center;
      color: var(--secondary-text-color, #555);
    }
  `;
}

if (!customElements.get("zigsight-topology-graph")) {
  customElements.define("zigsight-topology-graph", ZigSightTopologyGraph);
}
