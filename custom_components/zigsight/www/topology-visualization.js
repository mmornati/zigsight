/**
 * ZigSight Interactive Network Topology Visualization
 * 
 * An advanced network topology visualizer with interactive graph features,
 * multiple layout options, and performance optimization for large networks.
 * 
 * Features:
 * - Interactive graph with zoom, pan, and click
 * - Multiple layout algorithms (hierarchical, force-directed)
 * - Device type filtering and highlighting
 * - Link quality visualization
 * - Device health status indicators
 * - Performance optimized for 100+ devices
 */

class ZigSightTopologyVisualization extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._topology = null;
    this._hass = null;
    this._network = null;
    this._selectedLayout = 'hierarchical';
    this._showLinkQuality = true;
    this._visibleDeviceTypes = new Set(['coordinator', 'router', 'end_device']);
    this._highlightProblematic = false;
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
      this.renderVisualization();
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
    this.renderVisualization();
  }

  renderVisualization() {
    if (!this._topology) {
      this.renderLoading();
      return;
    }

    const title = this._config.title || 'Network Topology';

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          width: 100%;
        }
        
        .card {
          background: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 4px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 2px 0 rgba(0,0,0,0.14));
        }
        
        .card-header {
          font-size: 24px;
          font-weight: 400;
          padding: 16px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--divider-color);
        }
        
        .controls {
          display: flex;
          gap: 8px;
          align-items: center;
          flex-wrap: wrap;
        }
        
        .toolbar {
          padding: 12px 16px;
          background: var(--primary-background-color);
          display: flex;
          gap: 16px;
          flex-wrap: wrap;
          align-items: center;
          border-bottom: 1px solid var(--divider-color);
        }
        
        .toolbar-group {
          display: flex;
          gap: 8px;
          align-items: center;
        }
        
        .toolbar-label {
          font-size: 12px;
          color: var(--secondary-text-color);
          font-weight: 500;
        }
        
        button {
          background: var(--primary-color);
          color: white;
          border: none;
          padding: 6px 12px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          transition: opacity 0.2s;
        }
        
        button:hover {
          opacity: 0.9;
        }
        
        button.secondary {
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
        }
        
        button.active {
          background: var(--primary-color);
          color: white;
        }
        
        button.toggle {
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
        }
        
        button.toggle.active {
          background: var(--primary-color);
          color: white;
          border-color: var(--primary-color);
        }
        
        select {
          padding: 6px 12px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
          cursor: pointer;
        }
        
        .stats {
          display: flex;
          gap: 16px;
          padding: 12px 16px;
          background: var(--primary-background-color);
          flex-wrap: wrap;
          border-bottom: 1px solid var(--divider-color);
        }
        
        .stat {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        
        .stat-label {
          color: var(--secondary-text-color);
          font-size: 11px;
          font-weight: 500;
          text-transform: uppercase;
        }
        
        .stat-value {
          font-size: 18px;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        
        .graph-container {
          position: relative;
          width: 100%;
          height: 600px;
          background: var(--card-background-color);
        }
        
        #network-graph {
          width: 100%;
          height: 100%;
        }
        
        .legend {
          display: flex;
          gap: 16px;
          padding: 12px 16px;
          background: var(--primary-background-color);
          flex-wrap: wrap;
          font-size: 12px;
          border-top: 1px solid var(--divider-color);
        }
        
        .legend-item {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        
        .legend-color {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          border: 2px solid var(--divider-color);
        }
        
        .legend-line {
          width: 30px;
          height: 3px;
          border-radius: 2px;
        }
        
        .loading {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 400px;
          color: var(--secondary-text-color);
        }
        
        .error {
          color: var(--error-color);
          padding: 16px;
          text-align: center;
        }
        
        .device-info {
          position: absolute;
          top: 16px;
          right: 16px;
          background: var(--card-background-color);
          padding: 16px;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.2);
          max-width: 300px;
          z-index: 10;
          display: none;
        }
        
        .device-info.visible {
          display: block;
        }
        
        .device-info-header {
          font-size: 16px;
          font-weight: 500;
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid var(--divider-color);
        }
        
        .device-info-row {
          display: flex;
          justify-content: space-between;
          padding: 6px 0;
          font-size: 13px;
        }
        
        .device-info-label {
          color: var(--secondary-text-color);
        }
        
        .close-info {
          position: absolute;
          top: 8px;
          right: 8px;
          background: transparent;
          color: var(--secondary-text-color);
          font-size: 18px;
          padding: 4px 8px;
          min-width: auto;
        }
      </style>
      
      <div class="card">
        <div class="card-header">
          <span>${title}</span>
          <div class="controls">
            <button class="secondary" id="refresh-btn">Refresh</button>
            <button class="secondary" id="fit-btn">Fit to Screen</button>
          </div>
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
          <div class="stat">
            <div class="stat-label">Connections</div>
            <div class="stat-value">${this._topology.edges.length}</div>
          </div>
        </div>
        
        <div class="toolbar">
          <div class="toolbar-group">
            <span class="toolbar-label">Layout:</span>
            <select id="layout-select">
              <option value="hierarchical" ${this._selectedLayout === 'hierarchical' ? 'selected' : ''}>Hierarchical Tree</option>
              <option value="force" ${this._selectedLayout === 'force' ? 'selected' : ''}>Force-Directed</option>
            </select>
          </div>
          
          <div class="toolbar-group">
            <span class="toolbar-label">Show:</span>
            <button class="toggle ${this._visibleDeviceTypes.has('coordinator') ? 'active' : ''}" data-type="coordinator">Coordinator</button>
            <button class="toggle ${this._visibleDeviceTypes.has('router') ? 'active' : ''}" data-type="router">Routers</button>
            <button class="toggle ${this._visibleDeviceTypes.has('end_device') ? 'active' : ''}" data-type="end_device">End Devices</button>
          </div>
          
          <div class="toolbar-group">
            <button class="toggle ${this._showLinkQuality ? 'active' : ''}" id="toggle-lqi">Link Quality</button>
            <button class="toggle ${this._highlightProblematic ? 'active' : ''}" id="toggle-problems">Highlight Issues</button>
          </div>
        </div>
        
        <div class="graph-container">
          <div id="network-graph"></div>
          <div class="device-info" id="device-info">
            <button class="close-info" id="close-info">×</button>
            <div id="device-info-content"></div>
          </div>
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
            <div class="legend-color" style="background: #f44336; border-color: #f44336;"></div>
            <span>Problematic</span>
          </div>
          <div class="legend-item">
            <div class="legend-line" style="background: #4CAF50;"></div>
            <span>Excellent (200-255)</span>
          </div>
          <div class="legend-item">
            <div class="legend-line" style="background: #8BC34A;"></div>
            <span>Good (150-199)</span>
          </div>
          <div class="legend-item">
            <div class="legend-line" style="background: #FF9800;"></div>
            <span>Fair (100-149)</span>
          </div>
          <div class="legend-item">
            <div class="legend-line" style="background: #f44336;"></div>
            <span>Poor (0-99)</span>
          </div>
        </div>
      </div>
    `;

    this.attachEventListeners();
    this.initializeNetwork();
  }

  attachEventListeners() {
    const refreshBtn = this.shadowRoot.getElementById('refresh-btn');
    const fitBtn = this.shadowRoot.getElementById('fit-btn');
    const layoutSelect = this.shadowRoot.getElementById('layout-select');
    const toggleLqi = this.shadowRoot.getElementById('toggle-lqi');
    const toggleProblems = this.shadowRoot.getElementById('toggle-problems');
    const closeInfo = this.shadowRoot.getElementById('close-info');
    const typeToggles = this.shadowRoot.querySelectorAll('.toggle[data-type]');

    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.loadTopology());
    }

    if (fitBtn) {
      fitBtn.addEventListener('click', () => {
        if (this._network) {
          this._network.fit({ animation: true });
        }
      });
    }

    if (layoutSelect) {
      layoutSelect.addEventListener('change', (e) => {
        this._selectedLayout = e.target.value;
        this.updateNetworkLayout();
      });
    }

    if (toggleLqi) {
      toggleLqi.addEventListener('click', () => {
        this._showLinkQuality = !this._showLinkQuality;
        toggleLqi.classList.toggle('active', this._showLinkQuality);
        this.updateEdgeLabels();
      });
    }

    if (toggleProblems) {
      toggleProblems.addEventListener('click', () => {
        this._highlightProblematic = !this._highlightProblematic;
        toggleProblems.classList.toggle('active', this._highlightProblematic);
        this.updateNodeHighlighting();
      });
    }

    if (closeInfo) {
      closeInfo.addEventListener('click', () => {
        this.hideDeviceInfo();
      });
    }

    typeToggles.forEach(toggle => {
      toggle.addEventListener('click', () => {
        const type = toggle.dataset.type;
        if (this._visibleDeviceTypes.has(type)) {
          this._visibleDeviceTypes.delete(type);
          toggle.classList.remove('active');
        } else {
          this._visibleDeviceTypes.add(type);
          toggle.classList.add('active');
        }
        this.updateNodeVisibility();
      });
    });
  }

  initializeNetwork() {
    const container = this.shadowRoot.getElementById('network-graph');
    if (!container || !this._topology) return;

    // Prepare nodes data
    const nodes = this._topology.nodes.map(device => {
      const nodeData = {
        id: device.id,
        label: device.label,
        group: device.type,
        title: this.getNodeTooltip(device),
        device: device,
        hidden: !this._visibleDeviceTypes.has(device.type)
      };

      // Set node appearance based on type
      nodeData.color = this.getNodeColor(device);
      nodeData.shape = this.getNodeShape(device.type);
      nodeData.size = this.getNodeSize(device.type);
      nodeData.font = {
        size: 12,
        color: 'var(--primary-text-color, #000)'
      };

      return nodeData;
    });

    // Prepare edges data
    const edges = this._topology.edges.map(edge => {
      const edgeData = {
        from: edge.from,
        to: edge.to,
        value: edge.link_quality || 1,
        title: `Link Quality: ${edge.link_quality || 'N/A'}`,
        color: {
          color: this.getLinkQualityColor(edge.link_quality),
          opacity: 0.8
        },
        width: this.getLinkWidth(edge.link_quality),
        smooth: {
          type: 'continuous'
        }
      };

      if (this._showLinkQuality && edge.link_quality !== null) {
        edgeData.label = String(edge.link_quality);
        edgeData.font = {
          size: 10,
          align: 'middle',
          strokeWidth: 0
        };
      }

      return edgeData;
    });

    const data = {
      nodes: nodes,
      edges: edges
    };

    const options = this.getNetworkOptions();

    // Destroy existing network if it exists
    if (this._network) {
      this._network.destroy();
    }

    // Create network using inline vis-network implementation
    this._network = this.createVisNetwork(container, data, options);

    // Add event listeners
    this._network.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const device = this._topology.nodes.find(n => n.id === nodeId);
        if (device) {
          this.showDeviceInfo(device);
        }
      } else {
        this.hideDeviceInfo();
      }
    });

    this._network.on('stabilizationIterationsDone', () => {
      this._network.setOptions({ physics: false });
    });
  }

  getNetworkOptions() {
    const layoutOptions = this._selectedLayout === 'hierarchical' 
      ? {
          enabled: true,
          direction: 'UD',
          sortMethod: 'directed',
          nodeSpacing: 150,
          levelSeparation: 200
        }
      : false;

    return {
      layout: {
        hierarchical: layoutOptions
      },
      physics: {
        enabled: this._selectedLayout !== 'hierarchical',
        stabilization: {
          iterations: 200,
          updateInterval: 25
        },
        barnesHut: {
          gravitationalConstant: -2000,
          springConstant: 0.001,
          springLength: 200
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
        zoomView: true,
        dragView: true,
        navigationButtons: true,
        keyboard: {
          enabled: true
        }
      },
      nodes: {
        borderWidth: 2,
        borderWidthSelected: 4,
        font: {
          size: 12
        }
      },
      edges: {
        arrows: {
          to: {
            enabled: true,
            scaleFactor: 0.5
          }
        },
        smooth: {
          type: 'continuous'
        }
      }
    };
  }

  getNodeColor(device) {
    // Check if highlighting problematic devices
    if (this._highlightProblematic) {
      const hasIssues = device.analytics?.connectivity_warning || 
                       device.analytics?.battery_drain_warning ||
                       (device.health_score !== null && device.health_score < 50);
      if (hasIssues) {
        return {
          background: '#f44336',
          border: '#c62828',
          highlight: {
            background: '#ff5252',
            border: '#d32f2f'
          }
        };
      }
    }

    // Default colors based on device type
    const typeColors = {
      coordinator: { bg: '#2196F3', border: '#1976D2' },
      router: { bg: '#4CAF50', border: '#388E3C' },
      end_device: { bg: '#FF9800', border: '#F57C00' }
    };

    const colors = typeColors[device.type] || typeColors.end_device;
    return {
      background: colors.bg,
      border: colors.border,
      highlight: {
        background: colors.bg,
        border: colors.border
      }
    };
  }

  getNodeShape(type) {
    const shapes = {
      coordinator: 'diamond',
      router: 'box',
      end_device: 'circle'
    };
    return shapes[type] || 'circle';
  }

  getNodeSize(type) {
    const sizes = {
      coordinator: 30,
      router: 25,
      end_device: 20
    };
    return sizes[type] || 20;
  }

  getLinkQualityColor(lqi) {
    if (lqi === null || lqi === undefined) return '#999';
    if (lqi >= 200) return '#4CAF50';
    if (lqi >= 150) return '#8BC34A';
    if (lqi >= 100) return '#FF9800';
    return '#f44336';
  }

  getLinkWidth(lqi) {
    if (lqi === null || lqi === undefined) return 1;
    if (lqi >= 200) return 3;
    if (lqi >= 150) return 2.5;
    if (lqi >= 100) return 2;
    return 1;
  }

  getNodeTooltip(device) {
    let tooltip = `${device.label}\nType: ${device.type.replace('_', ' ')}`;
    if (device.link_quality !== null) {
      tooltip += `\nLink Quality: ${device.link_quality}`;
    }
    if (device.battery !== null) {
      tooltip += `\nBattery: ${device.battery}%`;
    }
    if (device.health_score !== null) {
      tooltip += `\nHealth: ${Math.round(device.health_score)}`;
    }
    return tooltip;
  }

  updateNetworkLayout() {
    if (!this._network) return;
    const options = this.getNetworkOptions();
    this._network.setOptions(options);
    this._network.fit({ animation: true });
  }

  updateEdgeLabels() {
    if (!this._network || !this._topology) return;

    const edges = this._topology.edges.map(edge => {
      const edgeData = {
        id: `${edge.from}-${edge.to}`,
        from: edge.from,
        to: edge.to,
        value: edge.link_quality || 1,
        color: {
          color: this.getLinkQualityColor(edge.link_quality),
          opacity: 0.8
        },
        width: this.getLinkWidth(edge.link_quality)
      };

      if (this._showLinkQuality && edge.link_quality !== null) {
        edgeData.label = String(edge.link_quality);
        edgeData.font = {
          size: 10,
          align: 'middle',
          strokeWidth: 0
        };
      }

      return edgeData;
    });

    this._network.body.data.edges.update(edges);
  }

  updateNodeHighlighting() {
    if (!this._network || !this._topology) return;

    const nodes = this._topology.nodes.map(device => ({
      id: device.id,
      color: this.getNodeColor(device)
    }));

    this._network.body.data.nodes.update(nodes);
  }

  updateNodeVisibility() {
    if (!this._network || !this._topology) return;

    const nodes = this._topology.nodes.map(device => ({
      id: device.id,
      hidden: !this._visibleDeviceTypes.has(device.type)
    }));

    this._network.body.data.nodes.update(nodes);
  }

  showDeviceInfo(device) {
    const infoPanel = this.shadowRoot.getElementById('device-info');
    const infoContent = this.shadowRoot.getElementById('device-info-content');
    
    if (!infoPanel || !infoContent) return;

    const healthStatus = this.getHealthStatus(device.health_score);
    const hasWarnings = device.analytics?.connectivity_warning || device.analytics?.battery_drain_warning;

    infoContent.innerHTML = `
      <div class="device-info-header">${device.label}</div>
      <div class="device-info-row">
        <span class="device-info-label">Type</span>
        <span>${device.type.replace('_', ' ')}</span>
      </div>
      ${device.link_quality !== null ? `
        <div class="device-info-row">
          <span class="device-info-label">Link Quality</span>
          <span>${device.link_quality}</span>
        </div>
      ` : ''}
      ${device.battery !== null ? `
        <div class="device-info-row">
          <span class="device-info-label">Battery</span>
          <span>${device.battery}%</span>
        </div>
      ` : ''}
      ${device.health_score !== null ? `
        <div class="device-info-row">
          <span class="device-info-label">Health Score</span>
          <span>${Math.round(device.health_score)} (${healthStatus})</span>
        </div>
      ` : ''}
      ${device.analytics?.reconnect_rate != null ? `
        <div class="device-info-row">
          <span class="device-info-label">Reconnect Rate</span>
          <span>${device.analytics.reconnect_rate.toFixed(2)}/hr</span>
        </div>
      ` : ''}
      ${device.last_seen ? `
        <div class="device-info-row">
          <span class="device-info-label">Last Seen</span>
          <span>${new Date(device.last_seen).toLocaleString()}</span>
        </div>
      ` : ''}
      ${hasWarnings ? `
        <div class="device-info-row" style="color: var(--error-color);">
          <span class="device-info-label">Warnings</span>
          <span>⚠️ Issues Detected</span>
        </div>
      ` : ''}
    `;

    infoPanel.classList.add('visible');
  }

  hideDeviceInfo() {
    const infoPanel = this.shadowRoot.getElementById('device-info');
    if (infoPanel) {
      infoPanel.classList.remove('visible');
    }
  }

  getHealthStatus(score) {
    if (score === null || score === undefined) return 'Unknown';
    if (score >= 80) return 'Healthy';
    if (score >= 50) return 'Warning';
    return 'Critical';
  }

  // Simplified vis-network implementation
  createVisNetwork(container, data, options) {
    // This is a simplified implementation. For production, we would use the full vis-network library.
    // Since we can't easily bundle the full library inline, we'll use a CDN-loaded version
    // or provide instructions to include it separately.
    
    // Check if vis is available globally
    if (typeof window.vis !== 'undefined' && window.vis.Network) {
      return new window.vis.Network(container, data, options);
    }
    
    // Fallback: Load vis-network dynamically
    return this.loadVisNetworkAndCreate(container, data, options);
  }

  async loadVisNetworkAndCreate(container, data, options) {
    // Load vis-network from CDN if not already loaded
    if (!window.vis || !window.vis.Network) {
      await this.loadScript('https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js');
    }
    
    return new window.vis.Network(container, data, options);
  }

  loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  renderLoading() {
    this.shadowRoot.innerHTML = `
      <style>
        .loading {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 400px;
          color: var(--secondary-text-color);
        }
      </style>
      <div class="card">
        <div class="loading">Loading topology visualization...</div>
      </div>
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
      <div class="card">
        <div class="error">${message}</div>
      </div>
    `;
  }

  getCardSize() {
    return 8;
  }

  static getStubConfig() {
    return {
      title: 'Network Topology Visualization',
    };
  }
}

customElements.define('zigsight-topology-visualization', ZigSightTopologyVisualization);

// Register the card with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'zigsight-topology-visualization',
  name: 'ZigSight Interactive Network Topology',
  description: 'Interactive network topology with graph visualization, multiple layouts, and advanced filtering',
  preview: true,
});

console.info(
  '%c ZigSight Topology Visualization %c v1.0.0 ',
  'background-color: #2196F3; color: #fff; font-weight: bold;',
  'background-color: #333; color: #fff; font-weight: bold;'
);
