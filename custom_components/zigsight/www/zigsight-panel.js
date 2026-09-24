/**
 * ZigSight sidebar panel.
 *
 * Registered automatically by the integration (panel_custom, admin only) and
 * served from /zigsight_static/. Everything it needs is bundled: Lit is
 * vendored in ./vendor and the topology graph is plain SVG, so the panel
 * works without internet access.
 *
 * Security: all API data (device names, models, explanations, ...) is
 * rendered through Lit templates, which escape text. Don't use innerHTML.
 */

import { LitElement, css, html, nothing } from "./vendor/lit-core.min.js";
import "./lib/topology-graph.js";
import {
  apiErrorMessage,
  formatDate,
  formatNumber,
  hasIssues,
  healthStatus,
  lqiColor,
  typeLabel,
} from "./lib/format.js";
import { WIFI_CHANNELS, parseWifiJson, validateAccessPoints } from "./lib/wifi.js";

const REFRESH_INTERVAL_MS = 30000;
const NETWORK_MAP_POLL_MS = 10000;
const NETWORK_MAP_TIMEOUT_MS = 5 * 60 * 1000;
const TABS = [
  { id: "devices", label: "Devices", icon: "mdi:devices" },
  { id: "topology", label: "Topology", icon: "mdi:graph-outline" },
  { id: "analytics", label: "Analytics", icon: "mdi:chart-line" },
  { id: "channel", label: "Channel", icon: "mdi:wifi" },
];
const NODE_TYPES = ["coordinator", "router", "end_device", "unknown"];

function emptyRow() {
  return { channel: "6", rssi: "", ssid: "" };
}

class ZigSightPanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    route: { attribute: false },
    panel: { attribute: false },
    _devices: { state: true },
    _topology: { state: true },
    _selectedDevice: { state: true },
    _selectedNode: { state: true },
    _activeTab: { state: true },
    _loading: { state: true },
    _error: { state: true },
    _search: { state: true },
    _typeFilter: { state: true },
    _layout: { state: true },
    _showLqi: { state: true },
    _visibleTypes: { state: true },
    _highlightIssues: { state: true },
    _mapStatus: { state: true },
    _channel: { state: true },
    _wifiRows: { state: true },
    _wifiJson: { state: true },
    _wifiInputMode: { state: true },
    _wifiErrors: { state: true },
    _recommending: { state: true },
  };

  constructor() {
    super();
    this._devices = [];
    this._topology = null;
    this._selectedDevice = null;
    this._selectedNode = null;
    this._activeTab = "devices";
    this._loading = false;
    this._error = null;
    this._search = "";
    this._typeFilter = "all";
    this._layout = "radial";
    this._showLqi = true;
    this._visibleTypes = [...NODE_TYPES];
    this._highlightIssues = false;
    this._mapStatus = null;
    this._channel = null;
    this._wifiRows = [emptyRow()];
    this._wifiJson = "";
    this._wifiInputMode = "table";
    this._wifiErrors = [];
    this._recommending = false;
    this._loaded = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this._refreshTimer = setInterval(() => this._loadData(), REFRESH_INTERVAL_MS);
    if (this.hass) this._loadData();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearInterval(this._refreshTimer);
    clearTimeout(this._mapPollTimer);
  }

  updated(changed) {
    // hass is set after the element is attached the first time.
    if (changed.has("hass") && this.hass && !this._loaded) {
      this._loaded = true;
      this._loadData();
    }
  }

  async _api(method, path, body) {
    // hass.callApi prefixes "/api/".
    return this.hass.callApi(method, path, body);
  }

  async _loadData() {
    if (!this.hass || this._loading) return;
    this._loaded = true;
    this._loading = true;
    try {
      const [devices, topology, channel] = await Promise.all([
        this._api("GET", "zigsight/devices"),
        this._api("GET", "zigsight/topology"),
        this._api("GET", "zigsight/channel-recommendation"),
      ]);
      this._devices = devices.devices || [];
      this._topology = topology;
      this._channel = { ...(this._channel || {}), status: channel };
      this._error = null;
      if (this._selectedDevice) {
        this._selectedDevice =
          this._devices.find((d) => d.device_id === this._selectedDevice.device_id) || null;
      }
      if (this._selectedNode) {
        this._selectedNode =
          topology.nodes?.find((n) => n.id === this._selectedNode.id) || null;
      }
    } catch (error) {
      this._error = apiErrorMessage(error);
    } finally {
      this._loading = false;
    }
  }

  // -------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------
  render() {
    return html`
      <div class="toolbar">
        <ha-menu-button .hass=${this.hass} .narrow=${this.narrow}></ha-menu-button>
        <div class="title">ZigSight</div>
        <button
          class="icon-button"
          title="Refresh"
          aria-label="Refresh"
          ?disabled=${this._loading}
          @click=${() => this._loadData()}
        >
          <ha-icon icon="mdi:refresh"></ha-icon>
        </button>
      </div>
      <div class="tabs" role="tablist">
        ${TABS.map(
          (tab) => html`<button
            role="tab"
            class="tab ${this._activeTab === tab.id ? "active" : ""}"
            aria-selected=${this._activeTab === tab.id ? "true" : "false"}
            @click=${() => this._setTab(tab.id)}
          >
            <ha-icon icon=${tab.icon}></ha-icon>
            <span>${tab.label}${tab.id === "devices" ? ` (${this._devices.length})` : ""}</span>
          </button>`,
        )}
      </div>
      <div class="content">
        ${this._error
          ? html`<div class="alert error" role="alert">
              <span>${this._error}</span>
              <button class="button" @click=${() => this._loadData()}>Retry</button>
            </div>`
          : nothing}
        ${!this._topology && this._loading
          ? html`<div class="loading">Loading ZigSight data…</div>`
          : this._renderTab()}
      </div>
    `;
  }

  _setTab(tab) {
    this._activeTab = tab;
    this._selectedDevice = null;
  }

  _renderTab() {
    switch (this._activeTab) {
      case "topology":
        return this._renderTopology();
      case "analytics":
        return this._renderAnalytics();
      case "channel":
        return this._renderChannel();
      default:
        return this._selectedDevice ? this._renderDeviceDetails() : this._renderDevices();
    }
  }

  // ----------------------------- Devices ------------------------------
  _filteredDevices() {
    const search = this._search.trim().toLowerCase();
    return this._devices
      .filter((device) => {
        if (this._typeFilter !== "all" && this._deviceType(device) !== this._typeFilter) {
          return false;
        }
        if (!search) return true;
        return [device.friendly_name, device.device_id, device.model, device.manufacturer]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(search));
      })
      .sort((a, b) =>
        String(a.friendly_name || a.device_id).localeCompare(String(b.friendly_name || b.device_id)),
      );
  }

  _deviceType(device) {
    return {
      Coordinator: "coordinator",
      Router: "router",
      EndDevice: "end_device",
    }[device.type] || "unknown";
  }

  _renderDevices() {
    if (!this._devices.length) {
      return html`<div class="empty">
        <ha-icon icon="mdi:zigbee"></ha-icon>
        <h2>No devices yet</h2>
        <p>
          Devices appear once Zigbee2MQTT publishes its device list (or ZHA devices are
          found).
        </p>
      </div>`;
    }
    const devices = this._filteredDevices();
    return html`
      <div class="filters">
        <input
          type="search"
          placeholder="Search name, IEEE, model…"
          aria-label="Search devices"
          .value=${this._search}
          @input=${(event) => (this._search = event.target.value)}
        />
        <select
          aria-label="Device type"
          @change=${(event) => (this._typeFilter = event.target.value)}
        >
          <option value="all">All types</option>
          ${NODE_TYPES.filter((type) => type !== "coordinator").map(
            (type) =>
              html`<option value=${type} ?selected=${this._typeFilter === type}>
                ${typeLabel(type)}
              </option>`,
          )}
        </select>
      </div>
      <div class="devices-grid">
        ${devices.map((device) => this._renderDeviceCard(device))}
      </div>
      ${devices.length ? nothing : html`<p class="muted">No device matches the filters.</p>`}
    `;
  }

  _renderDeviceCard(device) {
    const metrics = device.metrics || {};
    const analytics = device.analytics_metrics || {};
    const issue = hasIssues(device);
    return html`
      <button
        class="device-card ${issue ? "warning" : ""}"
        @click=${() => (this._selectedDevice = device)}
      >
        <div class="device-name">
          <span
            class="dot ${device.available === false ? "offline" : device.available ? "online" : ""}"
            title=${device.available === false ? "Offline" : device.available ? "Online" : "Availability unknown"}
          ></span>
          <span>${device.friendly_name || device.device_id}</span>
        </div>
        <div class="device-sub">
          ${typeLabel(this._deviceType(device))}${device.model ? ` · ${device.model}` : ""}
        </div>
        <div class="device-metrics">
          <span title="Link quality">
            <ha-icon icon="mdi:signal"></ha-icon>
            <span style="color:${lqiColor(metrics.link_quality)}"
              >${formatNumber(metrics.link_quality)}</span
            >
          </span>
          ${typeof metrics.battery === "number"
            ? html`<span title="Battery"
                ><ha-icon icon="mdi:battery"></ha-icon>${formatNumber(metrics.battery, 0, "%")}</span
              >`
            : nothing}
          <span title="Health score">
            <ha-icon icon="mdi:heart-pulse"></ha-icon>${formatNumber(analytics.health_score, 0)}
          </span>
        </div>
        ${analytics.battery_drain_warning
          ? html`<div class="chip warning">Battery drain</div>`
          : nothing}
        ${analytics.connectivity_warning
          ? html`<div class="chip warning">Connectivity issues</div>`
          : nothing}
      </button>
    `;
  }

  _renderDeviceDetails() {
    const device = this._selectedDevice;
    const metrics = device.metrics || {};
    const analytics = device.analytics_metrics || {};
    const trend = analytics.battery_trend;
    return html`
      <div class="details">
        <div class="details-header">
          <button class="button secondary" @click=${() => (this._selectedDevice = null)}>
            <ha-icon icon="mdi:arrow-left"></ha-icon> Back
          </button>
          <h2>${device.friendly_name || device.device_id}</h2>
        </div>
        <div class="details-grid">
          <section>
            <h3>Device</h3>
            <dl>
              <dt>IEEE address</dt>
              <dd>${device.ieee_address || device.device_id}</dd>
              <dt>Type</dt>
              <dd>${typeLabel(this._deviceType(device))}</dd>
              <dt>Model</dt>
              <dd>${device.model || "—"}</dd>
              <dt>Manufacturer</dt>
              <dd>${device.manufacturer || "—"}</dd>
              <dt>Power source</dt>
              <dd>${device.power_source || "—"}</dd>
              <dt>Source</dt>
              <dd>${device.source || "—"}</dd>
              <dt>Available</dt>
              <dd>${device.available === false ? "No" : device.available ? "Yes" : "Unknown"}</dd>
              <dt>First seen</dt>
              <dd>${formatDate(device.first_seen)}</dd>
            </dl>
          </section>
          <section>
            <h3>Metrics</h3>
            <dl>
              <dt>Link quality</dt>
              <dd>${formatNumber(metrics.link_quality)}</dd>
              <dt>Battery</dt>
              <dd>${formatNumber(metrics.battery, 0, "%")}</dd>
              <dt>Voltage</dt>
              <dd>${formatNumber(metrics.voltage, 0)}</dd>
              <dt>Last seen</dt>
              <dd>${formatDate(metrics.last_seen)}</dd>
              <dt>Reconnects</dt>
              <dd>${device.reconnect_count ?? 0}</dd>
            </dl>
          </section>
          <section>
            <h3>Analytics</h3>
            <dl>
              <dt>Health score</dt>
              <dd>
                ${formatNumber(analytics.health_score, 1)} (${healthStatus(analytics.health_score)})
              </dd>
              <dt>Reconnect rate</dt>
              <dd>${formatNumber(analytics.reconnect_rate, 2, " /h")}</dd>
              <dt>Battery trend</dt>
              <dd>
                ${typeof trend === "number"
                  ? `${trend > 0 ? "+" : ""}${trend.toFixed(2)} %/h`
                  : "—"}
              </dd>
              <dt>Battery drain warning</dt>
              <dd>${analytics.battery_drain_warning ? "Yes" : "No"}</dd>
              <dt>Connectivity warning</dt>
              <dd>${analytics.connectivity_warning ? "Yes" : "No"}</dd>
            </dl>
          </section>
        </div>
      </div>
    `;
  }

  // ----------------------------- Topology -----------------------------
  _renderTopology() {
    const topology = this._topology;
    if (!topology) return html`<div class="empty"><p>No topology data.</p></div>`;
    const map = topology.network_map || {};
    const inferred = topology.links_source !== "networkmap";
    return html`
      <div class="stats">
        ${this._stat(topology.device_count, "Nodes")}
        ${this._stat(topology.router_count, "Routers")}
        ${this._stat(topology.end_device_count, "End devices")}
        ${this._stat(topology.edges?.length || 0, inferred ? "Inferred links" : "Links")}
      </div>

      <div class="alert ${inferred ? "info" : "success"}">
        <div>
          ${inferred
            ? html`<strong>Links are inferred.</strong> Without a network map every device is
                drawn connected to the coordinator; this is not how messages are routed.`
            : html`<strong>Network map</strong> received ${formatDate(map.updated)}. Links
                show the neighbour tables reported by the devices, with their LQI.`}
          ${map.supported
            ? html`<div class="muted small">
                Requesting a network map asks every router for its neighbour table. It can take
                a minute or more and loads the Zigbee mesh, so don't request it too often.
              </div>`
            : html`<div class="muted small">
                Network maps are only available with Zigbee2MQTT.
              </div>`}
          ${this._mapStatus ? html`<div class="small">${this._mapStatus}</div>` : nothing}
        </div>
        ${map.supported
          ? html`<button
              class="button"
              ?disabled=${Boolean(this._mapPollTimer)}
              @click=${this._requestNetworkMap}
            >
              <ha-icon icon="mdi:radar"></ha-icon>
              ${this._mapPollTimer ? "Scanning…" : "Request network map"}
            </button>`
          : nothing}
      </div>

      <div class="graph-toolbar">
        <label>
          Layout
          <select
            .value=${this._layout}
            @change=${(event) => (this._layout = event.target.value)}
          >
            <option value="radial">Rings (hops from coordinator)</option>
            <option value="force">Force directed</option>
          </select>
        </label>
        ${NODE_TYPES.map(
          (type) => html`<label class="check">
            <input
              type="checkbox"
              .checked=${this._visibleTypes.includes(type)}
              @change=${(event) => this._toggleType(type, event.target.checked)}
            />
            ${typeLabel(type)}
          </label>`,
        )}
        <label class="check">
          <input
            type="checkbox"
            .checked=${this._showLqi}
            @change=${(event) => (this._showLqi = event.target.checked)}
          />
          LQI labels
        </label>
        <label class="check">
          <input
            type="checkbox"
            .checked=${this._highlightIssues}
            @change=${(event) => (this._highlightIssues = event.target.checked)}
          />
          Highlight issues
        </label>
        <button class="button secondary" @click=${this._fitGraph}>
          <ha-icon icon="mdi:fit-to-screen-outline"></ha-icon> Fit
        </button>
      </div>

      <div class="graph-wrap">
        <zigsight-topology-graph
          .topology=${topology}
          .layout=${this._layout}
          .showLqi=${this._showLqi}
          .visibleTypes=${this._visibleTypes}
          .highlightIssues=${this._highlightIssues}
          .selectedId=${this._selectedNode?.id || null}
          @node-selected=${(event) => (this._selectedNode = event.detail.node)}
        ></zigsight-topology-graph>
        ${this._selectedNode ? this._renderNodeInfo(this._selectedNode) : nothing}
      </div>
    `;
  }

  _toggleType(type, checked) {
    const types = new Set(this._visibleTypes);
    if (checked) types.add(type);
    else types.delete(type);
    this._visibleTypes = NODE_TYPES.filter((t) => types.has(t));
  }

  _fitGraph() {
    this.renderRoot.querySelector("zigsight-topology-graph")?.fit();
  }

  _renderNodeInfo(node) {
    const analytics = node.analytics || {};
    const links = (this._topology.edges || []).filter(
      (edge) => edge.from === node.id || edge.to === node.id,
    );
    const names = new Map((this._topology.nodes || []).map((n) => [n.id, n.label]));
    return html`
      <aside class="node-info">
        <button
          class="icon-button close"
          aria-label="Close"
          @click=${() => (this._selectedNode = null)}
        >
          <ha-icon icon="mdi:close"></ha-icon>
        </button>
        <h3>${node.label}</h3>
        <dl>
          <dt>Type</dt>
          <dd>${typeLabel(node.type)}</dd>
          <dt>IEEE</dt>
          <dd>${node.id}</dd>
          ${node.model
            ? html`<dt>Model</dt>
                <dd>${node.manufacturer ? `${node.manufacturer} ` : ""}${node.model}</dd>`
            : nothing}
          <dt>LQI</dt>
          <dd>${formatNumber(node.link_quality)}</dd>
          ${typeof node.battery === "number"
            ? html`<dt>Battery</dt>
                <dd>${formatNumber(node.battery, 0, "%")}</dd>`
            : nothing}
          <dt>Health</dt>
          <dd>${formatNumber(node.health_score)} (${healthStatus(node.health_score)})</dd>
          <dt>Last seen</dt>
          <dd>${formatDate(node.last_seen)}</dd>
          ${analytics.connectivity_warning || analytics.battery_drain_warning
            ? html`<dt>Warnings</dt>
                <dd class="warning-text">
                  ${[
                    analytics.connectivity_warning ? "Connectivity" : "",
                    analytics.battery_drain_warning ? "Battery drain" : "",
                  ]
                    .filter(Boolean)
                    .join(", ")}
                </dd>`
            : nothing}
        </dl>
        ${links.length
          ? html`<h4>${links.some((l) => l.inferred) ? "Inferred links" : "Neighbours"}</h4>
              <ul class="links">
                ${links.map((edge) => {
                  const other = edge.from === node.id ? edge.to : edge.from;
                  return html`<li>
                    <span>${names.get(other) || other}</span>
                    <span style="color:${lqiColor(edge.link_quality)}"
                      >${formatNumber(edge.link_quality)}</span
                    >
                  </li>`;
                })}
              </ul>`
          : nothing}
      </aside>
    `;
  }

  async _requestNetworkMap() {
    const before = this._topology?.network_map?.updated || null;
    try {
      await this._api("POST", "zigsight/topology/networkmap");
    } catch (error) {
      this._mapStatus = `Could not request a network map: ${apiErrorMessage(error)}`;
      return;
    }
    this._mapStatus =
      "Network map requested. Waiting for Zigbee2MQTT to scan the network (this can take a few minutes)…";
    const started = Date.now();
    const poll = async () => {
      try {
        const topology = await this._api("GET", "zigsight/topology");
        this._topology = topology;
        const updated = topology.network_map?.updated || null;
        if (updated && updated !== before) {
          this._mapPollTimer = null;
          this._mapStatus = null;
          this.requestUpdate();
          return;
        }
      } catch (error) {
        // Keep polling; a single failed request is not fatal.
      }
      if (Date.now() - started > NETWORK_MAP_TIMEOUT_MS) {
        this._mapPollTimer = null;
        this._mapStatus =
          "No network map received yet. Zigbee2MQTT may still be scanning; check its logs and refresh later.";
        return;
      }
      this._mapPollTimer = setTimeout(poll, NETWORK_MAP_POLL_MS);
      this.requestUpdate();
    };
    this._mapPollTimer = setTimeout(poll, NETWORK_MAP_POLL_MS);
    this.requestUpdate();
  }

  // ----------------------------- Analytics ----------------------------
  _renderAnalytics() {
    const devices = this._devices;
    const withIssues = devices.filter((device) => hasIssues(device));
    const scores = devices
      .map((d) => d.analytics_metrics?.health_score)
      .filter((score) => typeof score === "number");
    const average = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
    const lowBattery = devices.filter(
      (d) => typeof d.metrics?.battery === "number" && d.metrics.battery <= 20,
    );
    return html`
      <div class="stats">
        ${this._stat(devices.length, "Devices")}
        ${this._stat(formatNumber(average, 1), "Average health")}
        ${this._stat(withIssues.length, "Need attention", withIssues.length > 0)}
        ${this._stat(lowBattery.length, "Battery ≤ 20%", lowBattery.length > 0)}
      </div>
      ${withIssues.length
        ? html`<h3>Devices needing attention</h3>
            <ul class="issue-list">
              ${withIssues.map((device) => {
                const analytics = device.analytics_metrics || {};
                const reasons = [
                  device.available === false ? "offline" : "",
                  analytics.connectivity_warning ? "connectivity issues" : "",
                  analytics.battery_drain_warning ? "battery drain" : "",
                  typeof analytics.health_score === "number" && analytics.health_score < 50
                    ? `health ${Math.round(analytics.health_score)}`
                    : "",
                ].filter(Boolean);
                return html`<li>
                  <button
                    class="link"
                    @click=${() => {
                      this._activeTab = "devices";
                      this._selectedDevice = device;
                    }}
                  >
                    ${device.friendly_name || device.device_id}
                  </button>
                  <span class="muted">${reasons.join(", ")}</span>
                </li>`;
              })}
            </ul>`
        : html`<p class="muted">No device needs attention.</p>`}
    `;
  }

  _stat(value, label, warn = false) {
    return html`<div class="stat ${warn ? "warn" : ""}">
      <div class="stat-value">${value ?? "—"}</div>
      <div class="stat-label">${label}</div>
    </div>`;
  }

  // ------------------------------ Channel -----------------------------
  _renderChannel() {
    const status = this._channel?.status || {};
    const result = this._channel?.result || (status.has_recommendation ? status : null);
    const current = status.current_channel ?? result?.current_channel ?? null;
    return html`
      <div class="channel-grid">
        <section class="card">
          <h3>Current Zigbee channel</h3>
          <div class="big">${current ?? "Unknown"}</div>
          <p class="muted small">
            ${current !== null
              ? "Reported by Zigbee2MQTT (bridge/info)."
              : "Not known: Zigbee2MQTT hasn't published bridge/info yet, or you use ZHA (see the ZHA network settings)."}
          </p>
        </section>
        ${result ? this._renderRecommendation(result, current) : nothing}
      </div>

      <section class="card">
        <h3>Wi-Fi networks around the coordinator</h3>
        <p class="muted small">
          Enter the 2.4 GHz access points you can see near the Zigbee coordinator (from your
          router's admin page or a Wi-Fi analyser app on a phone next to the coordinator). RSSI is
          the signal strength in dBm (for example -45 for a strong, nearby network, -85 for a
          weak one).
        </p>
        <div class="segmented" role="radiogroup" aria-label="Input mode">
          <button
            class=${this._wifiInputMode === "table" ? "active" : ""}
            @click=${() => (this._wifiInputMode = "table")}
          >
            Table
          </button>
          <button
            class=${this._wifiInputMode === "json" ? "active" : ""}
            @click=${() => (this._wifiInputMode = "json")}
          >
            Paste JSON
          </button>
        </div>
        ${this._wifiInputMode === "table" ? this._renderWifiTable() : this._renderWifiJson()}
        ${this._wifiErrors.length
          ? html`<ul class="alert error">
              ${this._wifiErrors.map((message) => html`<li>${message}</li>`)}
            </ul>`
          : nothing}
        <div class="actions">
          <button class="button" ?disabled=${this._recommending} @click=${this._recommend}>
            <ha-icon icon="mdi:auto-fix"></ha-icon>
            ${this._recommending ? "Analysing…" : "Recommend a Zigbee channel"}
          </button>
        </div>
      </section>
    `;
  }

  _renderWifiTable() {
    return html`
      <table class="wifi-table">
        <thead>
          <tr>
            <th>Wi-Fi channel</th>
            <th>RSSI (dBm)</th>
            <th>SSID (optional)</th>
            <th><span class="visually-hidden">Remove</span></th>
          </tr>
        </thead>
        <tbody>
          ${this._wifiRows.map(
            (row, index) => html`<tr>
              <td>
                <select
                  aria-label="Wi-Fi channel"
                  @change=${(event) => this._updateRow(index, "channel", event.target.value)}
                >
                  ${WIFI_CHANNELS.map(
                    (channel) =>
                      html`<option value=${String(channel)} ?selected=${String(channel) === row.channel}>
                        ${channel}
                      </option>`,
                  )}
                </select>
              </td>
              <td>
                <input
                  type="number"
                  min="-120"
                  max="0"
                  step="1"
                  placeholder="-60"
                  aria-label="RSSI"
                  .value=${row.rssi}
                  @input=${(event) => this._updateRow(index, "rssi", event.target.value)}
                />
              </td>
              <td>
                <input
                  type="text"
                  maxlength="64"
                  aria-label="SSID"
                  .value=${row.ssid}
                  @input=${(event) => this._updateRow(index, "ssid", event.target.value)}
                />
              </td>
              <td>
                <button
                  class="icon-button"
                  aria-label="Remove access point"
                  ?disabled=${this._wifiRows.length === 1}
                  @click=${() => this._removeRow(index)}
                >
                  <ha-icon icon="mdi:delete-outline"></ha-icon>
                </button>
              </td>
            </tr>`,
          )}
        </tbody>
      </table>
      <button class="button secondary" @click=${this._addRow}>
        <ha-icon icon="mdi:plus"></ha-icon> Add access point
      </button>
    `;
  }

  _renderWifiJson() {
    return html`
      <textarea
        rows="8"
        spellcheck="false"
        aria-label="Wi-Fi scan JSON"
        placeholder='[{"channel": 1, "rssi": -45}, {"channel": 6, "rssi": -70, "ssid": "Neighbour"}]'
        .value=${this._wifiJson}
        @input=${(event) => (this._wifiJson = event.target.value)}
      ></textarea>
      <p class="muted small">
        A list of <code>{"channel", "rssi", "ssid"}</code> objects, or
        <code>{"access_points": [...]}</code>.
      </p>
    `;
  }

  _updateRow(index, key, value) {
    this._wifiRows = this._wifiRows.map((row, i) => (i === index ? { ...row, [key]: value } : row));
  }

  _addRow() {
    this._wifiRows = [...this._wifiRows, emptyRow()];
  }

  _removeRow(index) {
    this._wifiRows = this._wifiRows.filter((_, i) => i !== index);
  }

  async _recommend() {
    const parsed =
      this._wifiInputMode === "json"
        ? parseWifiJson(this._wifiJson)
        : validateAccessPoints(this._wifiRows.filter((row) => String(row.rssi).trim() !== ""));
    this._wifiErrors = parsed.errors;
    if (parsed.errors.length) return;

    this._recommending = true;
    try {
      const result = await this._api("POST", "zigsight/channel-recommendation", {
        mode: "manual",
        wifi_scan_data: parsed.accessPoints,
      });
      this._channel = { ...(this._channel || {}), result };
    } catch (error) {
      this._wifiErrors = [apiErrorMessage(error)];
    } finally {
      this._recommending = false;
    }
  }

  _renderRecommendation(result, current) {
    const scores = Object.entries(result.scores || {})
      .map(([channel, score]) => [Number(channel), Number(score)])
      .sort((a, b) => a[0] - b[0]);
    const recommended = result.recommended_channel;
    return html`
      <section class="card">
        <h3>Recommended Zigbee channel</h3>
        <div class="big">${recommended}</div>
        ${current !== null && current !== undefined
          ? html`<p class="small">
              ${current === recommended
                ? "Your network already uses the recommended channel."
                : html`Your network uses channel ${current}. Changing the channel of an existing
                    network is disruptive (some devices may need to be re-paired); only do it if
                    you have interference problems.`}
            </p>`
          : nothing}
        <div class="scores" aria-label="Interference score per channel (lower is better)">
          ${scores.map(
            ([channel, score]) => html`<div class="score-row ${channel === recommended ? "best" : ""}">
              <span class="score-channel">Ch ${channel}</span>
              <span class="score-bar"
                ><span style="width:${Math.max(0, Math.min(100, score))}%"></span
              ></span>
              <span class="score-value">${score.toFixed(1)}</span>
            </div>`,
          )}
        </div>
        <p class="muted small">Interference score per channel, lower is better.</p>
        <p>${result.explanation}</p>
        ${result.timestamp ? html`<p class="muted small">${formatDate(result.timestamp)}</p>` : nothing}
      </section>
    `;
  }

  static styles = css`
    :host {
      display: block;
      min-height: 100vh;
      background: var(--primary-background-color, #fafafa);
      color: var(--primary-text-color, #212121);
      font-family: var(--ha-font-family-body, Roboto, sans-serif);
      --zs-radius: var(--ha-card-border-radius, 12px);
    }
    .toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      height: var(--header-height, 56px);
      padding: 0 12px;
      background: var(--app-header-background-color, var(--primary-color, #03a9f4));
      color: var(--app-header-text-color, #fff);
      box-sizing: border-box;
    }
    .toolbar .title {
      flex: 1;
      font-size: 20px;
    }
    .toolbar .icon-button {
      color: inherit;
    }
    .tabs {
      display: flex;
      gap: 4px;
      padding: 0 12px;
      overflow-x: auto;
      background: var(--card-background-color, #fff);
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    .tab {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 12px 16px;
      border: none;
      border-bottom: 2px solid transparent;
      background: none;
      color: var(--secondary-text-color, #555);
      font: inherit;
      cursor: pointer;
      white-space: nowrap;
    }
    .tab.active {
      color: var(--primary-color, #03a9f4);
      border-bottom-color: var(--primary-color, #03a9f4);
    }
    .content {
      max-width: 1400px;
      margin: 0 auto;
      padding: 16px;
    }
    .button {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border: none;
      border-radius: 8px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
      font: inherit;
      cursor: pointer;
    }
    .button.secondary {
      background: transparent;
      color: var(--primary-color, #03a9f4);
      border: 1px solid var(--divider-color, #e0e0e0);
    }
    .button[disabled] {
      opacity: 0.6;
      cursor: default;
    }
    .icon-button {
      display: inline-flex;
      padding: 8px;
      border: none;
      border-radius: 50%;
      background: none;
      color: var(--secondary-text-color, #555);
      cursor: pointer;
    }
    .icon-button[disabled] {
      opacity: 0.4;
      cursor: default;
    }
    .link {
      padding: 0;
      border: none;
      background: none;
      color: var(--primary-color, #03a9f4);
      font: inherit;
      cursor: pointer;
    }
    input,
    select,
    textarea {
      padding: 8px;
      border: 1px solid var(--divider-color, #ccc);
      border-radius: 6px;
      background: var(--card-background-color, #fff);
      color: var(--primary-text-color, #212121);
      font: inherit;
    }
    textarea {
      width: 100%;
      box-sizing: border-box;
      font-family: var(--ha-font-family-code, monospace);
    }
    code {
      font-family: var(--ha-font-family-code, monospace);
      font-size: 0.9em;
    }
    .muted {
      color: var(--secondary-text-color, #555);
    }
    .small {
      font-size: 13px;
    }
    .loading,
    .empty {
      padding: 48px 16px;
      text-align: center;
      color: var(--secondary-text-color, #555);
    }
    .empty ha-icon {
      --mdc-icon-size: 48px;
    }
    .alert {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 16px;
      padding: 12px 16px;
      border-radius: 8px;
      border-left: 4px solid var(--info-color, #039be5);
      background: var(--card-background-color, #fff);
    }
    ul.alert {
      display: block;
      padding-left: 32px;
    }
    .alert.error {
      border-left-color: var(--error-color, #db4437);
      color: var(--error-color, #db4437);
    }
    .alert.success {
      border-left-color: var(--success-color, #43a047);
    }
    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }
    .filters input {
      flex: 1;
      min-width: 200px;
    }
    .devices-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 12px;
    }
    .device-card {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 14px;
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: var(--zs-radius);
      background: var(--card-background-color, #fff);
      color: inherit;
      font: inherit;
      text-align: left;
      cursor: pointer;
    }
    .device-card:hover {
      border-color: var(--primary-color, #03a9f4);
    }
    .device-card.warning {
      border-left: 4px solid var(--warning-color, #ffa600);
    }
    .device-name {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
      overflow-wrap: anywhere;
    }
    .device-sub {
      font-size: 13px;
      color: var(--secondary-text-color, #555);
    }
    .device-metrics {
      display: flex;
      gap: 14px;
      font-size: 14px;
    }
    .device-metrics ha-icon {
      --mdc-icon-size: 16px;
      margin-right: 2px;
      color: var(--secondary-text-color, #555);
    }
    .dot {
      flex: none;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--disabled-text-color, #bdbdbd);
    }
    .dot.online {
      background: var(--success-color, #43a047);
    }
    .dot.offline {
      background: var(--error-color, #db4437);
    }
    .chip {
      align-self: flex-start;
      padding: 2px 8px;
      border-radius: 10px;
      font-size: 12px;
    }
    .chip.warning {
      background: rgba(255, 166, 0, 0.18);
      color: var(--primary-text-color, #212121);
    }
    .details-header {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .details-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }
    section,
    .card {
      padding: 16px;
      border-radius: var(--zs-radius);
      background: var(--card-background-color, #fff);
      box-shadow: var(--ha-card-box-shadow, none);
      border: 1px solid var(--divider-color, #e0e0e0);
      margin-bottom: 16px;
    }
    h3 {
      margin: 0 0 12px;
      font-size: 16px;
      font-weight: 500;
    }
    dl {
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 6px 16px;
      margin: 0;
    }
    dt {
      color: var(--secondary-text-color, #555);
    }
    dd {
      margin: 0;
      overflow-wrap: anywhere;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .stat {
      padding: 12px;
      border-radius: var(--zs-radius);
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
    }
    .stat.warn {
      border-left: 4px solid var(--warning-color, #ffa600);
    }
    .stat-value {
      font-size: 26px;
      font-weight: 500;
    }
    .stat-label {
      font-size: 13px;
      color: var(--secondary-text-color, #555);
    }
    .graph-toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 16px;
      margin-bottom: 8px;
      font-size: 14px;
    }
    .graph-toolbar label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .graph-wrap {
      position: relative;
      height: 65vh;
      min-height: 380px;
      display: flex;
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: var(--zs-radius);
      overflow: hidden;
      background: var(--card-background-color, #fff);
    }
    zigsight-topology-graph {
      flex: 1;
    }
    .node-info {
      padding: 16px;
      border-radius: var(--zs-radius);
      border: 1px solid var(--divider-color, #e0e0e0);
      background: var(--card-background-color, #fff);
      position: absolute;
      top: 12px;
      right: 12px;
      width: min(320px, calc(100% - 24px));
      max-height: calc(100% - 24px);
      overflow: auto;
      margin: 0;
      box-sizing: border-box;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    }
    .node-info h3 {
      padding-right: 32px;
      overflow-wrap: anywhere;
    }
    .node-info .close {
      position: absolute;
      top: 4px;
      right: 4px;
    }
    .links {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .links li {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      padding: 4px 0;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    .warning-text {
      color: var(--warning-color, #ffa600);
    }
    .issue-list {
      padding-left: 20px;
    }
    .issue-list li {
      margin-bottom: 6px;
    }
    .channel-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }
    .big {
      font-size: 44px;
      font-weight: 500;
      line-height: 1.1;
    }
    .segmented {
      display: inline-flex;
      margin-bottom: 12px;
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 8px;
      overflow: hidden;
    }
    .segmented button {
      padding: 6px 14px;
      border: none;
      background: none;
      color: var(--primary-text-color, #212121);
      font: inherit;
      cursor: pointer;
    }
    .segmented button.active {
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
    }
    .wifi-table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 8px;
    }
    .wifi-table th {
      text-align: left;
      font-weight: 500;
      font-size: 13px;
      color: var(--secondary-text-color, #555);
      padding: 4px;
    }
    .wifi-table td {
      padding: 4px;
    }
    .wifi-table input {
      width: 100%;
      box-sizing: border-box;
    }
    .actions {
      margin-top: 12px;
    }
    .scores {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin: 12px 0 4px;
    }
    .score-row {
      display: grid;
      grid-template-columns: 52px 1fr 48px;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }
    .score-row.best {
      font-weight: 600;
    }
    .score-bar {
      height: 8px;
      border-radius: 4px;
      background: var(--divider-color, #e0e0e0);
      overflow: hidden;
    }
    .score-bar span {
      display: block;
      height: 100%;
      background: var(--warning-color, #ffa600);
    }
    .score-row.best .score-bar span {
      background: var(--success-color, #43a047);
    }
    .score-value {
      text-align: right;
    }
    .visually-hidden {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
    }
    @media (max-width: 600px) {
      .content {
        padding: 8px;
      }
      .graph-wrap {
        height: 55vh;
      }
    }
  `;
}

if (!customElements.get("zigsight-panel")) {
  customElements.define("zigsight-panel", ZigSightPanel);
}
