/**
 * ZigSight interactive network topology card (Lovelace).
 *
 *   type: custom:zigsight-topology-visualization
 *   title: Network Topology   # optional
 *   layout: radial            # optional: radial | force
 *   height: 500               # optional, pixels
 *
 * Resource URL: /zigsight_static/topology-visualization.js (JavaScript module).
 * Self contained: vendored Lit and an SVG graph, no CDN.
 */

import { LitElement, css, html, nothing } from "./vendor/lit-core.min.js";
import "./lib/topology-graph.js";
import { apiErrorMessage, formatDate, formatNumber, healthStatus, typeLabel } from "./lib/format.js";

const NODE_TYPES = ["coordinator", "router", "end_device", "unknown"];
const REFRESH_INTERVAL_MS = 60000;

class ZigSightTopologyVisualization extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _topology: { state: true },
    _error: { state: true },
    _layout: { state: true },
    _showLqi: { state: true },
    _visibleTypes: { state: true },
    _highlightIssues: { state: true },
    _selected: { state: true },
  };

  constructor() {
    super();
    this._config = {};
    this._topology = null;
    this._error = null;
    this._layout = "radial";
    this._showLqi = true;
    this._visibleTypes = [...NODE_TYPES];
    this._highlightIssues = false;
    this._selected = null;
    this._loadedOnce = false;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = config;
    this._layout = config.layout === "force" ? "force" : "radial";
  }

  connectedCallback() {
    super.connectedCallback();
    this._timer = setInterval(() => this._load(), REFRESH_INTERVAL_MS);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearInterval(this._timer);
  }

  updated(changed) {
    // The hass object changes on every state change: only load once here.
    if (changed.has("hass") && this.hass && !this._loadedOnce) {
      this._loadedOnce = true;
      this._load();
    }
  }

  async _load() {
    if (!this.hass) return;
    try {
      this._topology = await this.hass.callApi("GET", "zigsight/topology");
      this._error = null;
      if (this._selected) {
        this._selected = this._topology.nodes?.find((n) => n.id === this._selected.id) || null;
      }
    } catch (error) {
      this._error = apiErrorMessage(error);
    }
  }

  _toggleType(type) {
    const types = new Set(this._visibleTypes);
    if (types.has(type)) types.delete(type);
    else types.add(type);
    this._visibleTypes = NODE_TYPES.filter((t) => types.has(t));
  }

  render() {
    const title = this._config.title || "Network Topology";
    const topology = this._topology;
    const height = Number(this._config.height) || 500;
    return html`
      <ha-card>
        <div class="header">
          <span class="title">${title}</span>
          <span class="actions">
            <button class="secondary" @click=${() => this._load()}>Refresh</button>
            <button
              class="secondary"
              @click=${() => this.renderRoot.querySelector("zigsight-topology-graph")?.fit()}
            >
              Fit
            </button>
          </span>
        </div>
        ${this._error ? html`<div class="error">${this._error}</div>` : nothing}
        ${!topology && !this._error ? html`<div class="loading">Loading topology…</div>` : nothing}
        ${topology
          ? html`
              <div class="stats">
                <span><b>${topology.device_count}</b> nodes</span>
                <span><b>${topology.router_count}</b> routers</span>
                <span><b>${topology.end_device_count}</b> end devices</span>
                <span
                  ><b>${topology.edges?.length || 0}</b>
                  ${topology.links_source === "networkmap" ? "links" : "inferred links"}</span
                >
              </div>
              <div class="toolbar">
                <select @change=${(event) => (this._layout = event.target.value)}>
                  <option value="radial" ?selected=${this._layout === "radial"}>Rings</option>
                  <option value="force" ?selected=${this._layout === "force"}>Force directed</option>
                </select>
                ${NODE_TYPES.map(
                  (type) => html`<button
                    class="toggle ${this._visibleTypes.includes(type) ? "active" : ""}"
                    @click=${() => this._toggleType(type)}
                  >
                    ${typeLabel(type)}
                  </button>`,
                )}
                <button
                  class="toggle ${this._showLqi ? "active" : ""}"
                  @click=${() => (this._showLqi = !this._showLqi)}
                >
                  LQI
                </button>
                <button
                  class="toggle ${this._highlightIssues ? "active" : ""}"
                  @click=${() => (this._highlightIssues = !this._highlightIssues)}
                >
                  Issues
                </button>
              </div>
              ${topology.links_source !== "networkmap"
                ? html`<div class="note">
                    Links are inferred (no network map yet). Request a network map from the
                    ZigSight panel to see the real mesh.
                  </div>`
                : nothing}
              <div class="graph" style="height:${height}px">
                <zigsight-topology-graph
                  .topology=${topology}
                  .layout=${this._layout}
                  .showLqi=${this._showLqi}
                  .visibleTypes=${this._visibleTypes}
                  .highlightIssues=${this._highlightIssues}
                  .selectedId=${this._selected?.id || null}
                  @node-selected=${(event) => (this._selected = event.detail.node)}
                ></zigsight-topology-graph>
                ${this._selected ? this._renderInfo(this._selected) : nothing}
              </div>
            `
          : nothing}
      </ha-card>
    `;
  }

  _renderInfo(node) {
    return html`<div class="info">
      <button class="close" aria-label="Close" @click=${() => (this._selected = null)}>×</button>
      <div class="info-title">${node.label}</div>
      <div class="row"><span>Type</span><span>${typeLabel(node.type)}</span></div>
      <div class="row"><span>IEEE</span><span>${node.id}</span></div>
      <div class="row"><span>LQI</span><span>${formatNumber(node.link_quality)}</span></div>
      ${typeof node.battery === "number"
        ? html`<div class="row"><span>Battery</span><span>${node.battery}%</span></div>`
        : nothing}
      <div class="row">
        <span>Health</span
        ><span>${formatNumber(node.health_score)} (${healthStatus(node.health_score)})</span>
      </div>
      <div class="row"><span>Last seen</span><span>${formatDate(node.last_seen)}</span></div>
    </div>`;
  }

  getCardSize() {
    return 8;
  }

  static getStubConfig() {
    return { title: "Network Topology" };
  }

  static styles = css`
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
    }
    .title {
      font-size: 20px;
    }
    .actions {
      display: flex;
      gap: 6px;
    }
    button {
      padding: 4px 10px;
      border-radius: 6px;
      border: 1px solid var(--divider-color, #e0e0e0);
      background: var(--card-background-color, #fff);
      color: var(--primary-text-color, #212121);
      font: inherit;
      font-size: 13px;
      cursor: pointer;
    }
    button.toggle.active {
      background: var(--primary-color, #03a9f4);
      border-color: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
    }
    select {
      padding: 4px;
      border-radius: 6px;
      border: 1px solid var(--divider-color, #e0e0e0);
      background: var(--card-background-color, #fff);
      color: var(--primary-text-color, #212121);
    }
    .stats,
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 6px 14px;
      padding: 0 16px 8px;
      font-size: 13px;
      align-items: center;
    }
    .note {
      margin: 0 16px 8px;
      font-size: 12px;
      color: var(--secondary-text-color, #555);
    }
    .graph {
      position: relative;
      display: flex;
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    zigsight-topology-graph {
      flex: 1;
    }
    .info {
      position: absolute;
      top: 8px;
      right: 8px;
      width: min(260px, calc(100% - 16px));
      padding: 12px;
      border-radius: 8px;
      background: var(--card-background-color, #fff);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
      font-size: 13px;
      box-sizing: border-box;
    }
    .info-title {
      font-weight: 500;
      margin: 0 20px 8px 0;
      overflow-wrap: anywhere;
    }
    .row {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      padding: 3px 0;
    }
    .row span:last-child {
      overflow-wrap: anywhere;
      text-align: right;
    }
    .close {
      position: absolute;
      top: 4px;
      right: 4px;
      border: none;
      background: none;
      font-size: 18px;
    }
    .loading,
    .error {
      padding: 16px;
      text-align: center;
      color: var(--secondary-text-color, #555);
    }
    .error {
      color: var(--error-color, #db4437);
    }
  `;
}

if (!customElements.get("zigsight-topology-visualization")) {
  customElements.define("zigsight-topology-visualization", ZigSightTopologyVisualization);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "zigsight-topology-visualization",
    name: "ZigSight Interactive Network Topology",
    description: "Interactive Zigbee network graph with link quality and filters",
    preview: true,
  });
}
