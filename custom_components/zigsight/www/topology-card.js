/**
 * ZigSight Network Topology Card
 * 
 * A custom Lovelace card for visualizing Zigbee network topology
 * with link quality color-coding and interactive device details.
 */

class ZigSightTopologyCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._topology = null;
    this._hass = null;
  }

  setConfig(config) {
    if (!config) {
      throw new Error('Invalid configuration');
    }
    this._config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.loadTopology();
  }

  async loadTopology() {
    try {
      const response = await this._hass.callApi('GET', '/api/zigsight/topology');
      this._topology = response;
      this.render();
    } catch (error) {
      console.error('Failed to load topology:', error);
      this.renderError('Failed to load network topology. Please check that ZigSight is configured correctly.');
    }
  }

  render() {
    if (!this._topology) {
      this.renderLoading();
      return;
    }

    const title = this._config.title || 'Zigbee Network Topology';
    
    this.shadowRoot.innerHTML = `
      <style>
        .card {
          padding: 16px;
          background: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 4px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 2px 0 rgba(0,0,0,0.14));
        }
        
        .card-header {
          font-size: 24px;
          font-weight: 400;
          padding-bottom: 16px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        
        .stats {
          display: flex;
          gap: 16px;
          margin-bottom: 16px;
          flex-wrap: wrap;
        }
        
        .stat {
          background: var(--primary-background-color);
          padding: 8px 12px;
          border-radius: 8px;
          font-size: 14px;
        }
        
        .stat-label {
          color: var(--secondary-text-color);
          font-size: 12px;
        }
        
        .stat-value {
          font-size: 18px;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        
        .topology-container {
          position: relative;
          min-height: 400px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          overflow: hidden;
        }
        
        .device-list {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
          gap: 12px;
          margin-top: 16px;
        }
        
        .device-card {
          background: var(--primary-background-color);
          padding: 12px;
          border-radius: 8px;
          border-left: 4px solid var(--divider-color);
          cursor: pointer;
          transition: all 0.2s;
        }
        
        .device-card:hover {
          background: var(--secondary-background-color);
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .device-card.coordinator {
          border-left-color: #2196F3;
        }
        
        .device-card.router {
          border-left-color: #4CAF50;
        }
        
        .device-card.end_device {
          border-left-color: #FF9800;
        }
        
        .device-card.warning {
          border-left-color: #f44336;
        }
        
        .device-name {
          font-weight: 500;
          margin-bottom: 4px;
          font-size: 14px;
        }
        
        .device-type {
          font-size: 12px;
          color: var(--secondary-text-color);
          text-transform: capitalize;
          margin-bottom: 8px;
        }
        
        .device-metrics {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          font-size: 12px;
        }
        
        .metric {
          display: flex;
          align-items: center;
          gap: 4px;
        }
        
        .metric-icon {
          width: 16px;
          height: 16px;
        }
        
        .link-quality-excellent { color: #4CAF50; }
        .link-quality-good { color: #8BC34A; }
        .link-quality-fair { color: #FF9800; }
        .link-quality-poor { color: #f44336; }
        
        .legend {
          display: flex;
          gap: 16px;
          margin-top: 16px;
          padding: 12px;
          background: var(--primary-background-color);
          border-radius: 8px;
          font-size: 12px;
          flex-wrap: wrap;
        }
        
        .legend-item {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        
        .legend-color {
          width: 20px;
          height: 3px;
          border-radius: 2px;
        }
        
        .refresh-button {
          background: var(--primary-color);
          color: white;
          border: none;
          padding: 6px 12px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
        }
        
        .refresh-button:hover {
          opacity: 0.9;
        }
        
        .loading {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 200px;
          color: var(--secondary-text-color);
        }
        
        .error {
          color: var(--error-color);
          padding: 16px;
          text-align: center;
        }
      </style>
      
      <ha-card>
        <div class="card">
          <div class="card-header">
            <span>${title}</span>
            <button class="refresh-button" @click="${() => this.loadTopology()}">
              Refresh
            </button>
          </div>
          
          <div class="stats">
            <div class="stat">
              <div class="stat-label">Total Devices</div>
              <div class="stat-value">${this._topology.device_count}</div>
            </div>
            <div class="stat">
              <div class="stat-label">Coordinator</div>
              <div class="stat-value">${this._topology.coordinator_count}</div>
            </div>
            <div class="stat">
              <div class="stat-label">Routers</div>
              <div class="stat-value">${this._topology.router_count}</div>
            </div>
            <div class="stat">
              <div class="stat-label">End Devices</div>
              <div class="stat-value">${this._topology.end_device_count}</div>
            </div>
          </div>
          
          <div class="device-list">
            ${this.renderDeviceCards()}
          </div>
          
          <div class="legend">
            <div class="legend-item">
              <div class="legend-color" style="background: #2196F3;"></div>
              <span>Coordinator</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #4CAF50;"></div>
              <span>Router</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #FF9800;"></div>
              <span>End Device</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #f44336;"></div>
              <span>Warning</span>
            </div>
          </div>
        </div>
      </ha-card>
    `;
    
    // Add event listeners to device cards
    this.shadowRoot.querySelectorAll('.device-card').forEach(card => {
      card.addEventListener('click', (e) => {
        const deviceId = e.currentTarget.dataset.deviceId;
        this.showDeviceDialog(deviceId);
      });
    });
    
    // Add refresh button listener
    const refreshBtn = this.shadowRoot.querySelector('.refresh-button');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.loadTopology());
    }
  }

  renderDeviceCards() {
    if (!this._topology || !this._topology.nodes) {
      return '';
    }
    
    return this._topology.nodes.map(device => {
      const hasWarning = device.analytics?.connectivity_warning || device.analytics?.battery_drain_warning;
      const warningClass = hasWarning ? 'warning' : '';
      const linkQualityClass = this.getLinkQualityClass(device.link_quality);
      
      return `
        <div class="device-card ${device.type} ${warningClass}" data-device-id="${device.id}">
          <div class="device-name">${device.label}</div>
          <div class="device-type">${device.type.replace('_', ' ')}</div>
          <div class="device-metrics">
            ${device.link_quality !== null ? `
              <div class="metric">
                <span class="${linkQualityClass}">●</span>
                <span>LQI: ${device.link_quality}</span>
              </div>
            ` : ''}
            ${device.battery !== null ? `
              <div class="metric">
                <span>🔋</span>
                <span>${device.battery}%</span>
              </div>
            ` : ''}
            ${device.health_score !== null ? `
              <div class="metric">
                <span>❤️</span>
                <span>${Math.round(device.health_score)}</span>
              </div>
            ` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  getLinkQualityClass(lqi) {
    if (lqi === null) return '';
    if (lqi >= 200) return 'link-quality-excellent';
    if (lqi >= 150) return 'link-quality-good';
    if (lqi >= 100) return 'link-quality-fair';
    return 'link-quality-poor';
  }

  showDeviceDialog(deviceId) {
    const device = this._topology.nodes.find(n => n.id === deviceId);
    if (!device) return;
    
    // Create a more-info dialog
    const event = new Event('hass-more-info', {
      bubbles: true,
      composed: true,
    });
    event.detail = {
      entityId: `sensor.zigsight_${deviceId}_health_score`.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
    };
    
    // Show custom dialog with device details
    this.showCustomDialog(device);
  }

  showCustomDialog(device) {
    const dialog = document.createElement('div');
    dialog.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: var(--card-background-color);
      padding: 24px;
      border-radius: 8px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      z-index: 9999;
      max-width: 400px;
      width: 90%;
    `;
    
    dialog.innerHTML = `
      <style>
        .dialog-header {
          font-size: 20px;
          font-weight: 500;
          margin-bottom: 16px;
        }
        .dialog-row {
          display: flex;
          justify-content: space-between;
          padding: 8px 0;
          border-bottom: 1px solid var(--divider-color);
        }
        .dialog-label {
          color: var(--secondary-text-color);
        }
        .dialog-close {
          background: var(--primary-color);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
          margin-top: 16px;
          width: 100%;
        }
      </style>
      <div class="dialog-header">${device.label}</div>
      <div class="dialog-row">
        <span class="dialog-label">Type</span>
        <span>${device.type.replace('_', ' ')}</span>
      </div>
      ${device.link_quality !== null ? `
        <div class="dialog-row">
          <span class="dialog-label">Link Quality</span>
          <span>${device.link_quality}</span>
        </div>
      ` : ''}
      ${device.battery !== null ? `
        <div class="dialog-row">
          <span class="dialog-label">Battery</span>
          <span>${device.battery}%</span>
        </div>
      ` : ''}
      ${device.health_score !== null ? `
        <div class="dialog-row">
          <span class="dialog-label">Health Score</span>
          <span>${Math.round(device.health_score)}</span>
        </div>
      ` : ''}
      ${device.analytics?.reconnect_rate !== null ? `
        <div class="dialog-row">
          <span class="dialog-label">Reconnect Rate</span>
          <span>${device.analytics.reconnect_rate.toFixed(2)}/hr</span>
        </div>
      ` : ''}
      ${device.last_seen ? `
        <div class="dialog-row">
          <span class="dialog-label">Last Seen</span>
          <span>${new Date(device.last_seen).toLocaleString()}</span>
        </div>
      ` : ''}
      <button class="dialog-close">Close</button>
    `;
    
    // Add overlay
    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.5);
      z-index: 9998;
    `;
    
    document.body.appendChild(overlay);
    document.body.appendChild(dialog);
    
    const closeDialog = () => {
      document.body.removeChild(dialog);
      document.body.removeChild(overlay);
    };
    
    dialog.querySelector('.dialog-close').addEventListener('click', closeDialog);
    overlay.addEventListener('click', closeDialog);
  }

  renderLoading() {
    this.shadowRoot.innerHTML = `
      <style>
        .loading {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 200px;
          color: var(--secondary-text-color);
        }
      </style>
      <ha-card>
        <div class="loading">Loading topology...</div>
      </ha-card>
    `;
  }

  renderError(message) {
    this.shadowRoot.innerHTML = `
      <style>
        .error {
          color: var(--error-color);
          padding: 16px;
          text-align: center;
        }
      </style>
      <ha-card>
        <div class="error">${message}</div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 6;
  }

  static getStubConfig() {
    return {
      title: 'Zigbee Network Topology',
    };
  }
}

customElements.define('zigsight-topology-card', ZigSightTopologyCard);

// Register the card with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'zigsight-topology-card',
  name: 'ZigSight Network Topology',
  description: 'Visualize your Zigbee network topology with device details and link quality',
  preview: true,
});

console.info(
  '%c ZigSight Topology Card %c v1.0.0 ',
  'background-color: #2196F3; color: #fff; font-weight: bold;',
  'background-color: #333; color: #fff; font-weight: bold;'
);
