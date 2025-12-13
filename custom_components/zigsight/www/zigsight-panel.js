/**
 * ZigSight Frontend Panel
 *
 * A custom Home Assistant panel for managing and visualizing Zigbee networks.
 * Displays discovered devices, network topology, analytics, and channel recommendations.
 */

import { LitElement, html, css } from "https://unpkg.com/[email protected]/lit-element.js?module";

class ZigSightPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      route: { type: Object },
      panel: { type: Object },
      _devices: { type: Array, state: true },
      _topology: { type: Object, state: true },
      _selectedDevice: { type: Object, state: true },
      _activeTab: { type: String, state: true },
      _loading: { type: Boolean, state: true },
      _error: { type: String, state: true },
    };
  }

  constructor() {
    super();
    this._devices = [];
    this._topology = null;
    this._selectedDevice = null;
    this._activeTab = "devices";
    this._loading = false;
    this._error = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.loadData();
    // Refresh data every 30 seconds
    this._refreshInterval = setInterval(() => this.loadData(), 30000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._refreshInterval) {
      clearInterval(this._refreshInterval);
    }
  }

  async loadData() {
    this._loading = true;
    this._error = null;

    try {
      // Load devices
      const devicesResponse = await this.hass.callApi('GET', '/api/zigsight/devices');
      this._devices = devicesResponse.devices || [];

      // Load topology
      const topologyResponse = await this.hass.callApi('GET', '/api/zigsight/topology');
      this._topology = topologyResponse;
    } catch (error) {
      console.error('Failed to load ZigSight data:', error);
      this._error = error.message || 'Failed to load data';
    } finally {
      this._loading = false;
    }
  }

  _handleTabChange(tab) {
    this._activeTab = tab;
    this._selectedDevice = null;
  }

  _handleDeviceSelect(device) {
    this._selectedDevice = device;
  }

  _handleBack() {
    this._selectedDevice = null;
  }

  render() {
    if (this._loading && this._devices.length === 0) {
      return html`
        <div class="loading-container">
          <ha-circular-progress active></ha-circular-progress>
          <p>Loading ZigSight data...</p>
        </div>
      `;
    }

    if (this._error) {
      return html`
        <div class="error-container">
          <ha-alert alert-type="error">
            <strong>Error:</strong> ${this._error}
          </ha-alert>
          <mwc-button @click=${this.loadData}>Retry</mwc-button>
        </div>
      `;
    }

    if (this._selectedDevice) {
      return this._renderDeviceDetails();
    }

    return html`
      <div class="panel-container">
        <div class="header">
          <h1>ZigSight</h1>
          <div class="header-actions">
            <mwc-button @click=${this.loadData} .disabled=${this._loading}>
              <ha-icon icon="mdi:refresh"></ha-icon>
              Refresh
            </mwc-button>
          </div>
        </div>

        <div class="tabs">
          <button
            class="tab ${this._activeTab === 'devices' ? 'active' : ''}"
            @click=${() => this._handleTabChange('devices')}
          >
            <ha-icon icon="mdi:devices"></ha-icon>
            Devices (${this._devices.length})
          </button>
          <button
            class="tab ${this._activeTab === 'topology' ? 'active' : ''}"
            @click=${() => this._handleTabChange('topology')}
          >
            <ha-icon icon="mdi:graph"></ha-icon>
            Topology
          </button>
          <button
            class="tab ${this._activeTab === 'analytics' ? 'active' : ''}"
            @click=${() => this._handleTabChange('analytics')}
          >
            <ha-icon icon="mdi:chart-line"></ha-icon>
            Analytics
          </button>
          <button
            class="tab ${this._activeTab === 'channel' ? 'active' : ''}"
            @click=${() => this._handleTabChange('channel')}
          >
            <ha-icon icon="mdi:signal"></ha-icon>
            Channel Recommendation
          </button>
        </div>

        <div class="content">
          ${this._activeTab === 'devices' ? this._renderDevices() : ''}
          ${this._activeTab === 'topology' ? this._renderTopology() : ''}
          ${this._activeTab === 'analytics' ? this._renderAnalytics() : ''}
          ${this._activeTab === 'channel' ? this._renderChannelRecommendation() : ''}
        </div>
      </div>
    `;
  }

  _renderDevices() {
    if (this._devices.length === 0) {
      return html`
        <div class="empty-state">
          <ha-icon icon="mdi:devices" class="empty-icon"></ha-icon>
          <h2>No devices discovered</h2>
          <p>ZigSight will automatically discover devices as they connect to your Zigbee network.</p>
        </div>
      `;
    }

    return html`
      <div class="devices-grid">
        ${this._devices.map(device => this._renderDeviceCard(device))}
      </div>
    `;
  }

  _renderDeviceCard(device) {
    const metrics = device.metrics || {};
    const analytics = device.analytics_metrics || {};
    const healthScore = analytics.health_score || 0;
    const hasWarnings = analytics.battery_drain_warning || analytics.connectivity_warning;

    return html`
      <div class="device-card ${hasWarnings ? 'warning' : ''}" @click=${() => this._handleDeviceSelect(device)}>
        <div class="device-header">
          <div class="device-name">${device.friendly_name || device.device_id}</div>
          <div class="device-id">${device.device_id}</div>
        </div>
        <div class="device-metrics">
          <div class="metric">
            <ha-icon icon="mdi:signal"></ha-icon>
            <span>LQ: ${metrics.link_quality ?? 'N/A'}</span>
          </div>
          ${metrics.battery !== undefined ? html`
            <div class="metric">
              <ha-icon icon="mdi:battery"></ha-icon>
              <span>${metrics.battery}%</span>
            </div>
          ` : ''}
          <div class="metric">
            <ha-icon icon="mdi:heart-pulse"></ha-icon>
            <span>Health: ${healthScore.toFixed(1)}</span>
          </div>
        </div>
        ${hasWarnings ? html`
          <div class="device-warnings">
            ${analytics.battery_drain_warning ? html`
              <ha-alert alert-type="warning">Battery drain detected</ha-alert>
            ` : ''}
            ${analytics.connectivity_warning ? html`
              <ha-alert alert-type="warning">Connectivity issues</ha-alert>
            ` : ''}
          </div>
        ` : ''}
      </div>
    `;
  }

  _renderDeviceDetails() {
    const device = this._selectedDevice;
    const metrics = device.metrics || {};
    const analytics = device.analytics_metrics || {};

    return html`
      <div class="device-details">
        <div class="details-header">
          <mwc-button @click=${this._handleBack}>
            <ha-icon icon="mdi:arrow-left"></ha-icon>
            Back
          </mwc-button>
          <h2>${device.friendly_name || device.device_id}</h2>
        </div>

        <div class="details-content">
          <div class="details-section">
            <h3>Device Information</h3>
            <dl>
              <dt>Device ID</dt>
              <dd>${device.device_id}</dd>
              <dt>Friendly Name</dt>
              <dd>${device.friendly_name || 'N/A'}</dd>
              <dt>First Seen</dt>
              <dd>${device.first_seen ? new Date(device.first_seen).toLocaleString() : 'N/A'}</dd>
              <dt>Last Update</dt>
              <dd>${device.last_update ? new Date(device.last_update).toLocaleString() : 'N/A'}</dd>
              <dt>Reconnect Count</dt>
              <dd>${device.reconnect_count || 0}</dd>
            </dl>
          </div>

          <div class="details-section">
            <h3>Current Metrics</h3>
            <dl>
              <dt>Link Quality</dt>
              <dd>${metrics.link_quality ?? 'N/A'}</dd>
              <dt>Battery</dt>
              <dd>${metrics.battery !== undefined ? `${metrics.battery}%` : 'N/A'}</dd>
              <dt>Voltage</dt>
              <dd>${metrics.voltage ?? 'N/A'}</dd>
              <dt>Last Seen</dt>
              <dd>${metrics.last_seen ? new Date(metrics.last_seen).toLocaleString() : 'N/A'}</dd>
            </dl>
          </div>

          <div class="details-section">
            <h3>Analytics</h3>
            <dl>
              <dt>Health Score</dt>
              <dd>${analytics.health_score?.toFixed(1) ?? 'N/A'}</dd>
              <dt>Reconnect Rate</dt>
              <dd>${analytics.reconnect_rate?.toFixed(2) ?? 'N/A'} events/hour</dd>
              <dt>Battery Trend</dt>
              <dd>${analytics.battery_trend !== undefined ? `${analytics.battery_trend > 0 ? '+' : ''}${analytics.battery_trend.toFixed(2)}%/hour` : 'N/A'}</dd>
              <dt>Battery Drain Warning</dt>
              <dd>${analytics.battery_drain_warning ? 'Yes' : 'No'}</dd>
              <dt>Connectivity Warning</dt>
              <dd>${analytics.connectivity_warning ? 'Yes' : 'No'}</dd>
            </dl>
          </div>
        </div>
      </div>
    `;
  }

  _renderTopology() {
    if (!this._topology) {
      return html`
        <div class="empty-state">
          <ha-icon icon="mdi:graph" class="empty-icon"></ha-icon>
          <h2>No topology data</h2>
          <p>Topology visualization will appear here once devices are discovered.</p>
        </div>
      `;
    }

    return html`
      <div class="topology-container">
        <div class="topology-stats">
          <div class="stat">
            <div class="stat-value">${this._topology.device_count || 0}</div>
            <div class="stat-label">Total Devices</div>
          </div>
          <div class="stat">
            <div class="stat-value">${this._topology.coordinator_count || 0}</div>
            <div class="stat-label">Coordinators</div>
          </div>
          <div class="stat">
            <div class="stat-value">${this._topology.router_count || 0}</div>
            <div class="stat-label">Routers</div>
          </div>
          <div class="stat">
            <div class="stat-value">${this._topology.end_device_count || 0}</div>
            <div class="stat-label">End Devices</div>
          </div>
        </div>
        <div class="topology-visualization">
          <p><em>Topology visualization will be implemented in a future update.</em></p>
          <p>Nodes: ${this._topology.nodes?.length || 0}, Edges: ${this._topology.edges?.length || 0}</p>
        </div>
      </div>
    `;
  }

  _renderAnalytics() {
    const devicesWithWarnings = this._devices.filter(d => {
      const analytics = d.analytics_metrics || {};
      return analytics.battery_drain_warning || analytics.connectivity_warning;
    });

    const avgHealthScore = this._devices.length > 0
      ? this._devices.reduce((sum, d) => sum + (d.analytics_metrics?.health_score || 0), 0) / this._devices.length
      : 0;

    return html`
      <div class="analytics-container">
        <div class="analytics-overview">
          <div class="stat-card">
            <div class="stat-value">${this._devices.length}</div>
            <div class="stat-label">Total Devices</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">${avgHealthScore.toFixed(1)}</div>
            <div class="stat-label">Average Health Score</div>
          </div>
          <div class="stat-card warning">
            <div class="stat-value">${devicesWithWarnings.length}</div>
            <div class="stat-label">Devices with Warnings</div>
          </div>
        </div>

        ${devicesWithWarnings.length > 0 ? html`
          <div class="warnings-section">
            <h3>Devices Requiring Attention</h3>
            <div class="warnings-list">
              ${devicesWithWarnings.map(device => html`
                <div class="warning-item">
                  <strong>${device.friendly_name || device.device_id}</strong>
                  ${device.analytics_metrics?.battery_drain_warning ? html`
                    <ha-alert alert-type="warning">Battery drain detected</ha-alert>
                  ` : ''}
                  ${device.analytics_metrics?.connectivity_warning ? html`
                    <ha-alert alert-type="warning">Connectivity issues</ha-alert>
                  ` : ''}
                </div>
              `)}
            </div>
          </div>
        ` : ''}
      </div>
    `;
  }

  _renderChannelRecommendation() {
    return html`
      <div class="channel-recommendation">
        <div class="recommendation-info">
          <h3>Zigbee Channel Recommendation</h3>
          <p>Analyze Wi-Fi interference to recommend the best Zigbee channel for your network.</p>
        </div>
        <div class="recommendation-actions">
          <mwc-button raised @click=${this._runChannelRecommendation}>
            <ha-icon icon="mdi:signal"></ha-icon>
            Analyze & Recommend Channel
          </mwc-button>
        </div>
        <div id="recommendation-result"></div>
      </div>
    `;
  }

  async _runChannelRecommendation() {
    try {
      const result = await this.hass.callService('zigsight', 'recommend_channel', {
        mode: 'manual'
      });

      // Get the result from hass.data
      const recommendation = this.hass.data.zigsight?.last_recommendation;

      if (recommendation) {
        const resultDiv = this.shadowRoot.getElementById('recommendation-result');
        if (resultDiv) {
          const scoresHtml = Object.entries(recommendation.scores || {})
            .map(([channel, score]) => `<li>Channel ${channel}: ${score.toFixed(1)}</li>`)
            .join('');

          resultDiv.innerHTML = `
            <div class="recommendation-result">
              <h4>Recommended Channel: ${recommendation.recommended_channel}</h4>
              <p>${recommendation.explanation}</p>
              <div class="channel-scores">
                <h5>Channel Scores:</h5>
                <ul>${scoresHtml}</ul>
              </div>
            </div>
          `;
        }
      }
    } catch (error) {
      console.error('Channel recommendation failed:', error);
      this._error = 'Failed to get channel recommendation: ' + error.message;
    }
  }

  static get styles() {
    return css`
      :host {
        display: block;
        background-color: var(--primary-background-color, #fafafa);
        min-height: 100vh;
        padding: 16px;
      }

      .panel-container {
        max-width: 1400px;
        margin: 0 auto;
      }

      .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
      }

      .header h1 {
        margin: 0;
        font-size: 32px;
        font-weight: 400;
      }

      .tabs {
        display: flex;
        gap: 8px;
        margin-bottom: 24px;
        border-bottom: 1px solid var(--divider-color);
      }

      .tab {
        padding: 12px 24px;
        background: none;
        border: none;
        border-bottom: 2px solid transparent;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--primary-text-color);
        font-size: 14px;
      }

      .tab:hover {
        background-color: var(--secondary-background-color);
      }

      .tab.active {
        border-bottom-color: var(--primary-color);
        color: var(--primary-color);
      }

      .content {
        background: var(--card-background-color, white);
        border-radius: 4px;
        padding: 24px;
        box-shadow: 0 2px 2px 0 rgba(0,0,0,0.14);
      }

      .loading-container,
      .error-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 400px;
        gap: 16px;
      }

      .devices-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 16px;
      }

      .device-card {
        background: var(--card-background-color, white);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        padding: 16px;
        cursor: pointer;
        transition: all 0.2s;
      }

      .device-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        transform: translateY(-2px);
      }

      .device-card.warning {
        border-color: var(--error-color, #f44336);
      }

      .device-header {
        margin-bottom: 12px;
      }

      .device-name {
        font-size: 18px;
        font-weight: 500;
        margin-bottom: 4px;
      }

      .device-id {
        font-size: 12px;
        color: var(--secondary-text-color);
      }

      .device-metrics {
        display: flex;
        gap: 16px;
        margin-bottom: 8px;
      }

      .metric {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 14px;
      }

      .device-warnings {
        margin-top: 8px;
      }

      .empty-state {
        text-align: center;
        padding: 48px;
      }

      .empty-icon {
        font-size: 64px;
        color: var(--secondary-text-color);
        margin-bottom: 16px;
      }

      .device-details {
        background: var(--card-background-color, white);
        border-radius: 4px;
        padding: 24px;
      }

      .details-header {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 24px;
      }

      .details-section {
        margin-bottom: 24px;
      }

      .details-section h3 {
        margin-bottom: 12px;
        font-size: 18px;
      }

      .details-section dl {
        display: grid;
        grid-template-columns: 200px 1fr;
        gap: 8px;
      }

      .details-section dt {
        font-weight: 500;
        color: var(--secondary-text-color);
      }

      .topology-stats {
        display: flex;
        gap: 16px;
        margin-bottom: 24px;
      }

      .stat {
        flex: 1;
        background: var(--primary-background-color);
        padding: 16px;
        border-radius: 8px;
        text-align: center;
      }

      .stat-value {
        font-size: 32px;
        font-weight: 500;
        margin-bottom: 4px;
      }

      .stat-label {
        font-size: 14px;
        color: var(--secondary-text-color);
      }

      .analytics-overview {
        display: flex;
        gap: 16px;
        margin-bottom: 24px;
      }

      .stat-card {
        flex: 1;
        background: var(--primary-background-color);
        padding: 24px;
        border-radius: 8px;
        text-align: center;
      }

      .stat-card.warning {
        background: var(--warning-color, #ff9800);
        color: white;
      }

      .channel-recommendation {
        text-align: center;
        padding: 48px;
      }

      .recommendation-info {
        margin-bottom: 24px;
      }

      .recommendation-actions {
        margin-bottom: 24px;
      }
    `;
  }
}

customElements.define("zigsight-panel", ZigSightPanel);
