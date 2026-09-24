/**
 * ZigSight network topology card (Lovelace): device grid by type with link
 * quality, battery and health, plus a details popup.
 *
 *   type: custom:zigsight-topology-card
 *   title: Zigbee Network Topology   # optional
 *
 * Resource URL: /zigsight_static/topology-card.js (JavaScript module).
 * All device data is rendered with Lit templates (escaped text).
 */

import { LitElement, css, html, nothing } from "./vendor/lit-core.min.js";
import {
  apiErrorMessage,
  formatDate,
  formatNumber,
  hasIssues,
  healthStatus,
  lqiColor,
  typeColor,
  typeLabel,
} from "./lib/format.js";

const REFRESH_INTERVAL_MS = 60000;

class ZigSightTopologyCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _topology: { state: true },
    _error: { state: true },
    _selected: { state: true },
  };

  constructor() {
    super();
    this._config = {};
    this._topology = null;
    this._error = null;
    this._selected = null;
    this._loadedOnce = false;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = config;
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
    } catch (error) {
      this._error = apiErrorMessage(error);
    }
  }

  render() {
    const topology = this._topology;
    return html`
      <ha-card>
        <div class="header">
          <span class="title">${this._config.title || "Zigbee Network Topology"}</span>
          <button @click=${() => this._load()}>Refresh</button>
        </div>
        ${this._error ? html`<div class="error">${this._error}</div>` : nothing}
        ${!topology && !this._error ? html`<div class="loading">Loading topology…</div>` : nothing}
        ${topology
          ? html`
              <div class="stats">
                ${this._stat("Devices", topology.device_count)}
                ${this._stat("Coordinator", topology.coordinator_count)}
                ${this._stat("Routers", topology.router_count)}
                ${this._stat("End devices", topology.end_device_count)}
              </div>
              <div class="grid">
                ${(topology.nodes || []).map((node) => this._renderNode(node))}
              </div>
            `
          : nothing}
        ${this._selected ? this._renderDialog(this._selected) : nothing}
      </ha-card>
    `;
  }

  _stat(label, value) {
    return html`<div class="stat">
      <div class="stat-label">${label}</div>
      <div class="stat-value">${value ?? 0}</div>
    </div>`;
  }

  _renderNode(node) {
    const issue = hasIssues(node);
    return html`<button
      class="device"
      style="border-left-color:${issue ? "var(--error-color, #db4437)" : typeColor(node.type)}"
      @click=${() => (this._selected = node)}
    >
      <div class="name">${node.label}</div>
      <div class="type">${typeLabel(node.type)}</div>
      <div class="metrics">
        ${typeof node.link_quality === "number"
          ? html`<span><span style="color:${lqiColor(node.link_quality)}">●</span> LQI
                ${node.link_quality}</span
              >`
          : nothing}
        ${typeof node.battery === "number" ? html`<span>Battery ${node.battery}%</span>` : nothing}
        ${typeof node.health_score === "number"
          ? html`<span>Health ${Math.round(node.health_score)}</span>`
          : nothing}
      </div>
    </button>`;
  }

  _renderDialog(node) {
    const analytics = node.analytics || {};
    return html`
      <div class="overlay" @click=${() => (this._selected = null)}></div>
      <div class="dialog" role="dialog" aria-modal="true" aria-label=${node.label}>
        <div class="dialog-title">${node.label}</div>
        <div class="row"><span>Type</span><span>${typeLabel(node.type)}</span></div>
        <div class="row"><span>IEEE</span><span>${node.id}</span></div>
        ${node.model
          ? html`<div class="row"><span>Model</span><span>${node.model}</span></div>`
          : nothing}
        <div class="row"><span>Link quality</span><span>${formatNumber(node.link_quality)}</span></div>
        ${typeof node.battery === "number"
          ? html`<div class="row"><span>Battery</span><span>${node.battery}%</span></div>`
          : nothing}
        <div class="row">
          <span>Health</span
          ><span>${formatNumber(node.health_score)} (${healthStatus(node.health_score)})</span>
        </div>
        ${typeof analytics.reconnect_rate === "number"
          ? html`<div class="row">
              <span>Reconnect rate</span><span>${analytics.reconnect_rate.toFixed(2)} /h</span>
            </div>`
          : nothing}
        <div class="row"><span>Last seen</span><span>${formatDate(node.last_seen)}</span></div>
        <button class="close" @click=${() => (this._selected = null)}>Close</button>
      </div>
    `;
  }

  getCardSize() {
    return 6;
  }

  static getStubConfig() {
    return { title: "Zigbee Network Topology" };
  }

  static styles = css`
    :host {
      display: block;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
    }
    .title {
      font-size: 20px;
    }
    button {
      font: inherit;
      cursor: pointer;
    }
    .header button,
    .close {
      padding: 4px 12px;
      border: none;
      border-radius: 6px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
    }
    .stats {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 0 16px 12px;
    }
    .stat {
      padding: 6px 10px;
      border-radius: 8px;
      background: var(--secondary-background-color, #f5f5f5);
    }
    .stat-label {
      font-size: 12px;
      color: var(--secondary-text-color, #555);
    }
    .stat-value {
      font-size: 18px;
      font-weight: 500;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 8px;
      padding: 0 16px 16px;
    }
    .device {
      padding: 10px;
      border: none;
      border-left: 4px solid;
      border-radius: 8px;
      background: var(--secondary-background-color, #f5f5f5);
      color: var(--primary-text-color, #212121);
      text-align: left;
    }
    .name {
      font-weight: 500;
      overflow-wrap: anywhere;
    }
    .type {
      font-size: 12px;
      color: var(--secondary-text-color, #555);
      margin-bottom: 4px;
    }
    .metrics {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-size: 12px;
    }
    .overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.45);
      z-index: 10;
    }
    .dialog {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: min(400px, 90vw);
      padding: 20px;
      border-radius: 12px;
      background: var(--card-background-color, #fff);
      color: var(--primary-text-color, #212121);
      z-index: 11;
      box-sizing: border-box;
    }
    .dialog-title {
      font-size: 18px;
      font-weight: 500;
      margin-bottom: 12px;
      overflow-wrap: anywhere;
    }
    .row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 6px 0;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    .row span:first-child {
      color: var(--secondary-text-color, #555);
    }
    .row span:last-child {
      overflow-wrap: anywhere;
      text-align: right;
    }
    .close {
      width: 100%;
      margin-top: 16px;
      padding: 8px;
    }
    .loading,
    .error {
      padding: 16px;
      text-align: center;
    }
    .error {
      color: var(--error-color, #db4437);
    }
  `;
}

if (!customElements.get("zigsight-topology-card")) {
  customElements.define("zigsight-topology-card", ZigSightTopologyCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "zigsight-topology-card",
    name: "ZigSight Network Topology",
    description: "Zigbee devices by type with link quality, battery and health",
    preview: true,
  });
}
