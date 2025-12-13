/**
 * ZigSight Device List Panel
 * 
 * A comprehensive device management panel with filtering, sorting, search,
 * bulk actions, and pagination for managing Zigbee devices.
 */

class ZigSightPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._devices = [];
    this._filteredDevices = [];
    this._selectedDevices = new Set();
    this._topology = null;
    this._network = null;
    
    // View mode state
    this._viewMode = 'list'; // 'list', 'topology', or 'analytics'
    this._selectedLayout = 'hierarchical';
    this._showLinkQuality = true;
    this._visibleDeviceTypes = new Set(['coordinator', 'router', 'end_device']);
    this._highlightProblematic = false;
    
    // Analytics state
    this._analyticsOverview = null;
    this._selectedDevicesForComparison = new Set();
    this._analyticsTimeRange = 24; // hours
    
    // Filter state
    this._filters = {
      deviceType: 'all',
      healthStatus: 'all',
      batteryRange: [0, 100],
      linkQualityRange: [0, 255],
      integrationSource: 'all',
      searchQuery: ''
    };
    
    // Sort state
    this._sortBy = 'name';
    this._sortDirection = 'asc';
    
    // Pagination state
    this._currentPage = 1;
    this._itemsPerPage = 20;
  }

  set hass(hass) {
    this._hass = hass;
    this.loadDevices();
  }

  async loadDevices() {
    try {
      const response = await this._hass.callApi('GET', '/api/zigsight/topology');
      this._topology = response;
      this._devices = response.nodes || [];
      this.applyFiltersAndSort();
      
      // Load analytics overview if in analytics mode
      if (this._viewMode === 'analytics') {
        await this.loadAnalyticsOverview();
      }
    } catch (error) {
      console.error('Failed to load devices:', error);
      this.renderError('Failed to load devices. Please check that ZigSight is configured correctly.');
    }
  }
  
  async loadAnalyticsOverview() {
    try {
      const response = await this._hass.callApi('GET', '/api/zigsight/analytics/overview');
      this._analyticsOverview = response;
      if (this._viewMode === 'analytics') {
        this.render();
      }
    } catch (error) {
      console.error('Failed to load analytics overview:', error);
    }
  }

  applyFiltersAndSort() {
    let filtered = [...this._devices];
    
    // Apply filters
    if (this._filters.deviceType !== 'all') {
      filtered = filtered.filter(d => d.type === this._filters.deviceType);
    }
    
    if (this._filters.healthStatus !== 'all') {
      filtered = filtered.filter(d => this.getHealthStatus(d) === this._filters.healthStatus);
    }
    
    // Battery range filter
    filtered = filtered.filter(d => {
      if (d.battery === null || d.battery === undefined) return true;
      return d.battery >= this._filters.batteryRange[0] && 
             d.battery <= this._filters.batteryRange[1];
    });
    
    // Link quality range filter
    filtered = filtered.filter(d => {
      if (d.link_quality === null || d.link_quality === undefined) return true;
      return d.link_quality >= this._filters.linkQualityRange[0] && 
             d.link_quality <= this._filters.linkQualityRange[1];
    });
    
    // Integration source filter
    if (this._filters.integrationSource !== 'all') {
      filtered = filtered.filter(d => {
        const source = this.getDeviceSource(d);
        return source === this._filters.integrationSource;
      });
    }
    
    // Search filter
    if (this._filters.searchQuery) {
      const query = this._filters.searchQuery.toLowerCase();
      filtered = filtered.filter(d => 
        d.label.toLowerCase().includes(query) || 
        d.id.toLowerCase().includes(query)
      );
    }
    
    // Apply sorting
    filtered.sort((a, b) => {
      let aVal, bVal;
      
      switch (this._sortBy) {
        case 'name':
          aVal = a.label.toLowerCase();
          bVal = b.label.toLowerCase();
          break;
        case 'health':
          aVal = a.health_score ?? -1;
          bVal = b.health_score ?? -1;
          break;
        case 'battery':
          aVal = a.battery ?? -1;
          bVal = b.battery ?? -1;
          break;
        case 'linkQuality':
          aVal = a.link_quality ?? -1;
          bVal = b.link_quality ?? -1;
          break;
        case 'lastSeen':
          aVal = a.last_seen ? new Date(a.last_seen).getTime() : 0;
          bVal = b.last_seen ? new Date(b.last_seen).getTime() : 0;
          break;
        case 'reconnectCount':
          aVal = a.analytics?.reconnect_rate ?? 0;
          bVal = b.analytics?.reconnect_rate ?? 0;
          break;
        default:
          return 0;
      }
      
      if (aVal < bVal) return this._sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return this._sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
    
    this._filteredDevices = filtered;
    this._currentPage = 1; // Reset to first page when filters change
    this.render();
  }

  getHealthStatus(device) {
    const score = device.health_score;
    if (score === null || score === undefined) return 'unknown';
    if (score >= 80) return 'healthy';
    if (score >= 50) return 'warning';
    return 'critical';
  }

  getDeviceSource(device) {
    // Try to determine source from device data
    // This is a simplified approach - adjust based on actual data structure
    if (device.source) return device.source;
    // Default to unknown if not specified
    return 'unknown';
  }

  getPaginatedDevices() {
    const start = (this._currentPage - 1) * this._itemsPerPage;
    const end = start + this._itemsPerPage;
    return this._filteredDevices.slice(start, end);
  }

  getTotalPages() {
    return Math.ceil(this._filteredDevices.length / this._itemsPerPage);
  }

  handleFilterChange(filterName, value) {
    this._filters[filterName] = value;
    this.applyFiltersAndSort();
  }

  handleSortChange(sortBy) {
    if (this._sortBy === sortBy) {
      this._sortDirection = this._sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this._sortBy = sortBy;
      this._sortDirection = 'asc';
    }
    this.applyFiltersAndSort();
  }

  toggleDeviceSelection(deviceId) {
    if (this._selectedDevices.has(deviceId)) {
      this._selectedDevices.delete(deviceId);
    } else {
      this._selectedDevices.add(deviceId);
    }
    this.render();
  }

  toggleSelectAll() {
    const paginatedDevices = this.getPaginatedDevices();
    const allSelected = paginatedDevices.every(d => this._selectedDevices.has(d.id));
    
    if (allSelected) {
      paginatedDevices.forEach(d => this._selectedDevices.delete(d.id));
    } else {
      paginatedDevices.forEach(d => this._selectedDevices.add(d.id));
    }
    this.render();
  }

  exportSelectedDevices() {
    const selectedData = this._devices.filter(d => this._selectedDevices.has(d.id));
    const dataStr = JSON.stringify(selectedData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `zigsight-devices-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  exportAllDevices() {
    const dataStr = JSON.stringify(this._filteredDevices, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `zigsight-all-devices-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  render() {
    if (!this._devices || this._devices.length === 0) {
      this.renderLoading();
      return;
    }

    // Render based on view mode
    if (this._viewMode === 'topology' && this._topology) {
      this.renderTopologyView();
      return;
    } else if (this._viewMode === 'analytics') {
      this.renderAnalyticsView();
      return;
    }

    // Otherwise render list view
    this.renderListView();
  }

  renderListView() {
    const paginatedDevices = this.getPaginatedDevices();
    const totalPages = this.getTotalPages();
    const allSelected = paginatedDevices.length > 0 && 
                        paginatedDevices.every(d => this._selectedDevices.has(d.id));

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          width: 100%;
        }
        
        .panel {
          background: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 4px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 2px 0 rgba(0,0,0,0.14));
          padding: 16px;
        }
        
        .panel-header {
          font-size: 24px;
          font-weight: 400;
          margin-bottom: 24px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        
        .header-controls {
          display: flex;
          gap: 8px;
          align-items: center;
        }
        
        .view-toggle {
          display: flex;
          gap: 0;
          background: var(--primary-background-color);
          border-radius: 4px;
          overflow: hidden;
          border: 1px solid var(--divider-color);
        }
        
        .view-toggle button {
          background: transparent;
          color: var(--primary-text-color);
          border: none;
          padding: 6px 12px;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }
        
        .view-toggle button:hover {
          background: var(--secondary-background-color);
        }
        
        .view-toggle button.active {
          background: var(--primary-color);
          color: white;
        }
        
        .stats {
          display: flex;
          gap: 16px;
          margin-bottom: 24px;
          flex-wrap: wrap;
        }
        
        .stat {
          background: var(--primary-background-color);
          padding: 12px 16px;
          border-radius: 8px;
          font-size: 14px;
          flex: 1;
          min-width: 150px;
        }
        
        .stat-label {
          color: var(--secondary-text-color);
          font-size: 12px;
          margin-bottom: 4px;
        }
        
        .stat-value {
          font-size: 24px;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        
        .filters {
          background: var(--primary-background-color);
          padding: 16px;
          border-radius: 8px;
          margin-bottom: 16px;
        }
        
        .filter-row {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 12px;
          margin-bottom: 12px;
        }
        
        .filter-group {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        
        .filter-label {
          font-size: 12px;
          color: var(--secondary-text-color);
          font-weight: 500;
        }
        
        select, input[type="search"], input[type="range"] {
          width: 100%;
          padding: 8px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
        }
        
        input[type="search"] {
          padding-left: 32px;
          background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="gray" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>');
          background-repeat: no-repeat;
          background-position: 8px center;
        }
        
        .range-display {
          font-size: 11px;
          color: var(--secondary-text-color);
          margin-top: 2px;
        }
        
        .actions-bar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          padding: 12px;
          background: var(--primary-background-color);
          border-radius: 8px;
        }
        
        .bulk-actions {
          display: flex;
          gap: 8px;
        }
        
        button {
          background: var(--primary-color);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          transition: opacity 0.2s;
        }
        
        button:hover {
          opacity: 0.9;
        }
        
        button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        button.secondary {
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
        }
        
        .device-table {
          width: 100%;
          border-collapse: collapse;
          background: var(--card-background-color);
          border-radius: 8px;
          overflow: hidden;
        }
        
        .device-table thead {
          background: var(--primary-background-color);
        }
        
        .device-table th {
          text-align: left;
          padding: 12px;
          font-weight: 500;
          font-size: 12px;
          color: var(--secondary-text-color);
          text-transform: uppercase;
          cursor: pointer;
          user-select: none;
        }
        
        .device-table th:hover {
          background: var(--secondary-background-color);
        }
        
        .device-table th.sortable::after {
          content: '⇅';
          margin-left: 4px;
          opacity: 0.3;
        }
        
        .device-table th.sorted-asc::after {
          content: '↑';
          opacity: 1;
        }
        
        .device-table th.sorted-desc::after {
          content: '↓';
          opacity: 1;
        }
        
        .device-table td {
          padding: 12px;
          border-top: 1px solid var(--divider-color);
        }
        
        .device-table tr:hover {
          background: var(--secondary-background-color);
        }
        
        .device-name {
          font-weight: 500;
          font-size: 14px;
        }
        
        .device-id {
          font-size: 12px;
          color: var(--secondary-text-color);
        }
        
        .device-type {
          display: inline-block;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 500;
          text-transform: capitalize;
        }
        
        .device-type.coordinator {
          background: #2196F3;
          color: white;
        }
        
        .device-type.router {
          background: #4CAF50;
          color: white;
        }
        
        .device-type.end_device {
          background: #FF9800;
          color: white;
        }
        
        .health-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 500;
        }
        
        .health-badge.healthy {
          background: #e8f5e9;
          color: #2e7d32;
        }
        
        .health-badge.warning {
          background: #fff3e0;
          color: #f57c00;
        }
        
        .health-badge.critical {
          background: #ffebee;
          color: #c62828;
        }
        
        .health-badge.unknown {
          background: var(--secondary-background-color);
          color: var(--secondary-text-color);
        }
        
        .metric {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 13px;
        }
        
        .link-quality-excellent { color: #4CAF50; }
        .link-quality-good { color: #8BC34A; }
        .link-quality-fair { color: #FF9800; }
        .link-quality-poor { color: #f44336; }
        
        .pagination {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 8px;
          margin-top: 16px;
          padding: 16px;
        }
        
        .pagination button {
          padding: 6px 12px;
          min-width: 36px;
        }
        
        .pagination .page-info {
          margin: 0 16px;
          color: var(--secondary-text-color);
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
        
        input[type="checkbox"] {
          width: 18px;
          height: 18px;
          cursor: pointer;
        }
        
        .empty-state {
          text-align: center;
          padding: 48px 16px;
          color: var(--secondary-text-color);
        }
        
        .empty-state-icon {
          font-size: 48px;
          margin-bottom: 16px;
          opacity: 0.3;
        }
      </style>
      
      <div class="panel">
        <div class="panel-header">
          <span>ZigSight Device Management</span>
          <div class="header-controls">
            <div class="view-toggle">
              <button class="${this._viewMode === 'list' ? 'active' : ''}" data-view="list">📋 List</button>
              <button class="${this._viewMode === 'topology' ? 'active' : ''}" data-view="topology">🔗 Topology</button>
              <button class="${this._viewMode === 'analytics' ? 'active' : ''}" data-view="analytics">📊 Analytics</button>
            </div>
            <button id="refresh-devices">Refresh</button>
          </div>
        </div>
        
        <div class="stats">
          <div class="stat">
            <div class="stat-label">Total Devices</div>
            <div class="stat-value">${this._devices.length}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Filtered</div>
            <div class="stat-value">${this._filteredDevices.length}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Selected</div>
            <div class="stat-value">${this._selectedDevices.size}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Healthy</div>
            <div class="stat-value">${this._devices.filter(d => this.getHealthStatus(d) === 'healthy').length}</div>
          </div>
        </div>
        
        <div class="filters">
          <div class="filter-row">
            <div class="filter-group">
              <label class="filter-label">Search</label>
              <input 
                type="search" 
                placeholder="Search by name or ID..." 
                value="${this._filters.searchQuery}"
              />
            </div>
            
            <div class="filter-group">
              <label class="filter-label">Device Type</label>
              <select data-filter="deviceType">
                <option value="all" ${this._filters.deviceType === 'all' ? 'selected' : ''}>All Types</option>
                <option value="coordinator" ${this._filters.deviceType === 'coordinator' ? 'selected' : ''}>Coordinator</option>
                <option value="router" ${this._filters.deviceType === 'router' ? 'selected' : ''}>Router</option>
                <option value="end_device" ${this._filters.deviceType === 'end_device' ? 'selected' : ''}>End Device</option>
              </select>
            </div>
            
            <div class="filter-group">
              <label class="filter-label">Health Status</label>
              <select data-filter="healthStatus">
                <option value="all" ${this._filters.healthStatus === 'all' ? 'selected' : ''}>All Status</option>
                <option value="healthy" ${this._filters.healthStatus === 'healthy' ? 'selected' : ''}>Healthy</option>
                <option value="warning" ${this._filters.healthStatus === 'warning' ? 'selected' : ''}>Warning</option>
                <option value="critical" ${this._filters.healthStatus === 'critical' ? 'selected' : ''}>Critical</option>
              </select>
            </div>
            
            <div class="filter-group">
              <label class="filter-label">Integration Source</label>
              <select data-filter="integrationSource">
                <option value="all" ${this._filters.integrationSource === 'all' ? 'selected' : ''}>All Sources</option>
                <option value="zha" ${this._filters.integrationSource === 'zha' ? 'selected' : ''}>ZHA</option>
                <option value="zigbee2mqtt" ${this._filters.integrationSource === 'zigbee2mqtt' ? 'selected' : ''}>Zigbee2MQTT</option>
                <option value="deconz" ${this._filters.integrationSource === 'deconz' ? 'selected' : ''}>deCONZ</option>
              </select>
            </div>
          </div>
          
          <div class="filter-row">
            <div class="filter-group">
              <label class="filter-label">Battery Level: ${this._filters.batteryRange[0]}% - ${this._filters.batteryRange[1]}%</label>
              <input type="range" min="0" max="100" value="${this._filters.batteryRange[0]}" data-range="battery-min" />
              <input type="range" min="0" max="100" value="${this._filters.batteryRange[1]}" data-range="battery-max" />
            </div>
            
            <div class="filter-group">
              <label class="filter-label">Link Quality: ${this._filters.linkQualityRange[0]} - ${this._filters.linkQualityRange[1]}</label>
              <input type="range" min="0" max="255" value="${this._filters.linkQualityRange[0]}" data-range="lqi-min" />
              <input type="range" min="0" max="255" value="${this._filters.linkQualityRange[1]}" data-range="lqi-max" />
            </div>
          </div>
        </div>
        
        <div class="actions-bar">
          <div class="bulk-actions">
            <button class="secondary" ${this._selectedDevices.size === 0 ? 'disabled="disabled"' : ''} data-action="export-selected">
              Export Selected (${this._selectedDevices.size})
            </button>
            <button class="secondary" data-action="export-all">Export All</button>
          </div>
          <div>
            ${this._filteredDevices.length} devices
          </div>
        </div>
        
        ${this._filteredDevices.length === 0 ? this.renderEmptyState() : `
          <table class="device-table">
            <thead>
              <tr>
                <th style="width: 40px;">
                  <input type="checkbox" ${allSelected ? 'checked' : ''} id="select-all" />
                </th>
                <th class="sortable ${this._sortBy === 'name' ? 'sorted-' + this._sortDirection : ''}" data-sort="name">Device</th>
                <th class="sortable ${this._sortBy === 'health' ? 'sorted-' + this._sortDirection : ''}" data-sort="health">Health</th>
                <th>Type</th>
                <th class="sortable ${this._sortBy === 'battery' ? 'sorted-' + this._sortDirection : ''}" data-sort="battery">Battery</th>
                <th class="sortable ${this._sortBy === 'linkQuality' ? 'sorted-' + this._sortDirection : ''}" data-sort="linkQuality">Link Quality</th>
                <th class="sortable ${this._sortBy === 'lastSeen' ? 'sorted-' + this._sortDirection : ''}" data-sort="lastSeen">Last Seen</th>
                <th class="sortable ${this._sortBy === 'reconnectCount' ? 'sorted-' + this._sortDirection : ''}" data-sort="reconnectCount">Reconnects</th>
              </tr>
            </thead>
            <tbody>
              ${this.renderDeviceRows(paginatedDevices)}
            </tbody>
          </table>
          
          ${totalPages > 1 ? `
            <div class="pagination">
              <button ${this._currentPage === 1 ? 'disabled="disabled"' : ''} data-page="first">First</button>
              <button ${this._currentPage === 1 ? 'disabled="disabled"' : ''} data-page="prev">Previous</button>
              <span class="page-info">Page ${this._currentPage} of ${totalPages}</span>
              <button ${this._currentPage === totalPages ? 'disabled="disabled"' : ''} data-page="next">Next</button>
              <button ${this._currentPage === totalPages ? 'disabled="disabled"' : ''} data-page="last">Last</button>
            </div>
          ` : ''}
        `}
      </div>
    `;
    
    this.attachEventListeners();
  }

  renderDeviceRows(devices) {
    return devices.map(device => {
      const isSelected = this._selectedDevices.has(device.id);
      const healthStatus = this.getHealthStatus(device);
      const linkQualityClass = this.getLinkQualityClass(device.link_quality);
      
      return `
        <tr>
          <td>
            <input type="checkbox" ${isSelected ? 'checked' : ''} data-device-id="${device.id}" />
          </td>
          <td>
            <div class="device-name">${device.label}</div>
            <div class="device-id">${device.id}</div>
          </td>
          <td>
            <div class="health-badge ${healthStatus}">
              ${device.health_score !== null && device.health_score !== undefined 
                ? Math.round(device.health_score) 
                : 'N/A'}
            </div>
          </td>
          <td>
            <span class="device-type ${device.type}">${device.type.replace('_', ' ')}</span>
          </td>
          <td>
            ${device.battery !== null && device.battery !== undefined 
              ? `<div class="metric">🔋 ${device.battery}%</div>` 
              : '<span style="color: var(--secondary-text-color);">N/A</span>'}
          </td>
          <td>
            ${device.link_quality !== null && device.link_quality !== undefined 
              ? `<div class="metric"><span class="${linkQualityClass}">●</span> ${device.link_quality}</div>` 
              : '<span style="color: var(--secondary-text-color);">N/A</span>'}
          </td>
          <td>
            ${device.last_seen 
              ? new Date(device.last_seen).toLocaleString() 
              : '<span style="color: var(--secondary-text-color);">Never</span>'}
          </td>
          <td>
            ${device.analytics?.reconnect_rate !== null && device.analytics?.reconnect_rate !== undefined 
              ? device.analytics.reconnect_rate.toFixed(2) + '/hr' 
              : '<span style="color: var(--secondary-text-color);">N/A</span>'}
          </td>
        </tr>
      `;
    }).join('');
  }

  renderEmptyState() {
    return `
      <div class="empty-state">
        <div class="empty-state-icon">📭</div>
        <div>No devices found matching your filters</div>
        <div style="margin-top: 8px; font-size: 14px;">Try adjusting your filter criteria</div>
      </div>
    `;
  }

  getLinkQualityClass(lqi) {
    if (lqi === null || lqi === undefined) return '';
    if (lqi >= 200) return 'link-quality-excellent';
    if (lqi >= 150) return 'link-quality-good';
    if (lqi >= 100) return 'link-quality-fair';
    return 'link-quality-poor';
  }

  attachEventListeners() {
    // View toggle buttons
    const viewToggles = this.shadowRoot.querySelectorAll('.view-toggle button[data-view]');
    viewToggles.forEach(button => {
      button.addEventListener('click', async () => {
        this._viewMode = button.dataset.view;
        if (this._viewMode === 'analytics') {
          await this.loadAnalyticsOverview();
        }
        this.render();
      });
    });
    
    // Refresh button
    const refreshBtn = this.shadowRoot.querySelector('#refresh-devices');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.loadDevices());
    }
    
    // Search input
    const searchInput = this.shadowRoot.querySelector('input[type="search"]');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.handleFilterChange('searchQuery', e.target.value);
      });
    }
    
    // Filter selects - using data attributes
    const selects = this.shadowRoot.querySelectorAll('select[data-filter]');
    selects.forEach(select => {
      select.addEventListener('change', (e) => {
        const filterName = e.target.dataset.filter;
        this.handleFilterChange(filterName, e.target.value);
      });
    });
    
    // Range inputs
    const rangeInputs = this.shadowRoot.querySelectorAll('input[type="range"]');
    rangeInputs.forEach(input => {
      input.addEventListener('input', (e) => {
        const rangeType = e.target.dataset.range;
        if (rangeType === 'battery-min') {
          this._filters.batteryRange[0] = parseInt(e.target.value);
        } else if (rangeType === 'battery-max') {
          this._filters.batteryRange[1] = parseInt(e.target.value);
        } else if (rangeType === 'lqi-min') {
          this._filters.linkQualityRange[0] = parseInt(e.target.value);
        } else if (rangeType === 'lqi-max') {
          this._filters.linkQualityRange[1] = parseInt(e.target.value);
        }
        this.applyFiltersAndSort();
      });
    });
    
    // Table header sorting - using data attributes
    const headers = this.shadowRoot.querySelectorAll('.device-table th[data-sort]');
    headers.forEach(header => {
      header.addEventListener('click', () => {
        const sortBy = header.dataset.sort;
        this.handleSortChange(sortBy);
      });
    });
    
    // Checkbox selection - using event delegation on table
    const selectAllCheckbox = this.shadowRoot.querySelector('#select-all');
    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener('change', () => {
        this.toggleSelectAll();
      });
    }
    
    // Event delegation for device checkboxes
    const tbody = this.shadowRoot.querySelector('tbody');
    if (tbody) {
      tbody.addEventListener('change', (e) => {
        if (e.target.type === 'checkbox' && e.target.dataset.deviceId) {
          this.toggleDeviceSelection(e.target.dataset.deviceId);
        }
      });
    }
    
    // Bulk action buttons - using data attributes
    const bulkActions = this.shadowRoot.querySelector('.bulk-actions');
    if (bulkActions) {
      bulkActions.addEventListener('click', (e) => {
        if (e.target.tagName === 'BUTTON') {
          const action = e.target.dataset.action;
          if (action === 'export-selected') {
            this.exportSelectedDevices();
          } else if (action === 'export-all') {
            this.exportAllDevices();
          }
        }
      });
    }
    
    // Pagination buttons - using data attributes
    const pagination = this.shadowRoot.querySelector('.pagination');
    if (pagination) {
      pagination.addEventListener('click', (e) => {
        if (e.target.tagName === 'BUTTON') {
          const page = e.target.dataset.page;
          if (page === 'first') {
            this._currentPage = 1;
          } else if (page === 'prev' && this._currentPage > 1) {
            this._currentPage--;
          } else if (page === 'next' && this._currentPage < this.getTotalPages()) {
            this._currentPage++;
          } else if (page === 'last') {
            this._currentPage = this.getTotalPages();
          }
          this.render();
        }
      });
    }
    
    // Note: Refresh button listener added at the top of this method
  }

  renderTopologyView() {
    if (!this._topology) {
      this.renderLoading();
      return;
    }

    this.shadowRoot.innerHTML = `
      <style>
        ${this.getCommonStyles()}
        ${this.getTopologyStyles()}
      </style>
      
      <div class="panel">
        <div class="panel-header">
          <span>ZigSight Device Management</span>
          <div class="header-controls">
            <div class="view-toggle">
              <button class="${this._viewMode === 'list' ? 'active' : ''}" data-view="list">📋 List</button>
              <button class="${this._viewMode === 'topology' ? 'active' : ''}" data-view="topology">🔗 Topology</button>
              <button class="${this._viewMode === 'analytics' ? 'active' : ''}" data-view="analytics">📊 Analytics</button>
            </div>
            <button id="refresh-devices">Refresh</button>
            <button id="fit-topology">Fit to Screen</button>
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
        
        <div class="topology-toolbar">
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
        
        <div class="topology-container">
          <div id="network-graph"></div>
          <div class="device-info" id="device-info">
            <button class="close-info" id="close-info">×</button>
            <div id="device-info-content"></div>
          </div>
        </div>
        
        <div class="topology-legend">
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
    this.attachTopologyEventListeners();
    this.initializeNetwork();
  }

  renderAnalyticsView() {
    if (!this._analyticsOverview) {
      this.renderLoading();
      return;
    }

    const overview = this._analyticsOverview;
    
    this.shadowRoot.innerHTML = `
      <style>
        ${this.getCommonStyles()}
        ${this.getAnalyticsStyles()}
      </style>
      
      <div class="panel">
        <div class="panel-header">
          <span>ZigSight Analytics Dashboard</span>
          <div class="header-controls">
            <div class="view-toggle">
              <button class="${this._viewMode === 'list' ? 'active' : ''}" data-view="list">📋 List</button>
              <button class="${this._viewMode === 'topology' ? 'active' : ''}" data-view="topology">🔗 Topology</button>
              <button class="${this._viewMode === 'analytics' ? 'active' : ''}" data-view="analytics">📊 Analytics</button>
            </div>
            <button id="refresh-devices">Refresh</button>
          </div>
        </div>
        
        <!-- Network Overview Section -->
        <div class="analytics-section">
          <h2 class="section-title">Network Overview</h2>
          <div class="stats">
            <div class="stat">
              <div class="stat-label">Total Devices</div>
              <div class="stat-value">${overview.total_devices}</div>
            </div>
            <div class="stat">
              <div class="stat-label">Average Health Score</div>
              <div class="stat-value">${overview.average_health_score}</div>
            </div>
            <div class="stat">
              <div class="stat-label">Devices with Warnings</div>
              <div class="stat-value ${overview.devices_with_warnings > 0 ? 'warning' : ''}">${overview.devices_with_warnings}</div>
            </div>
          </div>
        </div>
        
        <!-- Distribution Charts Section -->
        <div class="analytics-section">
          <h2 class="section-title">Distribution Analysis</h2>
          <div class="charts-grid">
            <div class="chart-card">
              <h3 class="chart-title">Battery Level Distribution</h3>
              <canvas id="battery-chart"></canvas>
              <div class="chart-legend">
                ${this.renderDistributionLegend(overview.battery_distribution)}
              </div>
            </div>
            <div class="chart-card">
              <h3 class="chart-title">Link Quality Distribution</h3>
              <canvas id="lqi-chart"></canvas>
              <div class="chart-legend">
                ${this.renderDistributionLegend(overview.link_quality_distribution)}
              </div>
            </div>
          </div>
        </div>
        
        <!-- Device Alerts Section -->
        <div class="analytics-section">
          <h2 class="section-title">Alerts & Insights</h2>
          <div class="alerts-container">
            ${this.renderDeviceAlerts()}
          </div>
        </div>
        
        <!-- Device Comparison Section -->
        <div class="analytics-section">
          <h2 class="section-title">Device Comparison</h2>
          <div class="comparison-controls">
            <p>Select devices from the list below to compare their performance metrics:</p>
            <div class="device-selector">
              ${this.renderDeviceSelector()}
            </div>
          </div>
          ${this._selectedDevicesForComparison.size > 0 ? `
            <div class="comparison-table">
              ${this.renderComparisonTable()}
            </div>
          ` : `
            <div class="empty-state">
              <div class="empty-state-icon">📊</div>
              <div>Select 2 or more devices to compare</div>
            </div>
          `}
        </div>
        
        <!-- Export Section -->
        <div class="analytics-section">
          <h2 class="section-title">Export Analytics</h2>
          <div class="export-controls">
            <button id="export-json" class="secondary">📄 Export as JSON</button>
            <button id="export-csv" class="secondary">📊 Export as CSV</button>
          </div>
        </div>
      </div>
    `;
    
    this.attachEventListeners();
    this.attachAnalyticsEventListeners();
    this.initializeCharts();
  }

  renderDistributionLegend(distribution) {
    return Object.entries(distribution)
      .map(([label, count]) => `
        <div class="legend-item">
          <span class="legend-label">${label}</span>
          <span class="legend-value">${count} devices</span>
        </div>
      `).join('');
  }

  renderDeviceAlerts() {
    const devicesNeedingAttention = this._devices.filter(d => {
      const analytics = d.analytics || {};
      const metrics = d.metrics || {};
      return analytics.battery_drain_warning || 
             analytics.connectivity_warning ||
             (metrics.battery !== null && metrics.battery < 20) ||
             (d.health_score !== null && d.health_score < 50);
    });

    if (devicesNeedingAttention.length === 0) {
      return `
        <div class="alert-item success">
          <span class="alert-icon">✅</span>
          <div>
            <div class="alert-title">All Systems Healthy</div>
            <div class="alert-desc">No devices require immediate attention</div>
          </div>
        </div>
      `;
    }

    return devicesNeedingAttention.map(device => {
      const analytics = device.analytics || {};
      const metrics = device.metrics || {};
      const warnings = [];
      
      if (metrics.battery !== null && metrics.battery < 20) {
        warnings.push('Low battery');
      }
      if (analytics.battery_drain_warning) {
        warnings.push('Rapid battery drain detected');
      }
      if (analytics.connectivity_warning) {
        warnings.push('Connectivity issues');
      }
      if (device.health_score !== null && device.health_score < 50) {
        warnings.push('Critical health score');
      }

      return `
        <div class="alert-item warning">
          <span class="alert-icon">⚠️</span>
          <div>
            <div class="alert-title">${device.label}</div>
            <div class="alert-desc">${warnings.join(', ')}</div>
          </div>
        </div>
      `;
    }).join('');
  }

  renderDeviceSelector() {
    return `
      <div class="device-list-compact">
        ${this._devices.slice(0, 20).map(device => `
          <label class="device-checkbox">
            <input 
              type="checkbox" 
              value="${device.id}"
              ${this._selectedDevicesForComparison.has(device.id) ? 'checked' : ''}
              data-comparison-device
            />
            <span>${device.label}</span>
          </label>
        `).join('')}
        ${this._devices.length > 20 ? `<div class="more-devices">... and ${this._devices.length - 20} more devices</div>` : ''}
      </div>
    `;
  }

  renderComparisonTable() {
    const selectedDevices = this._devices.filter(d => 
      this._selectedDevicesForComparison.has(d.id)
    );

    if (selectedDevices.length === 0) return '';

    return `
      <table class="comparison-table-element">
        <thead>
          <tr>
            <th>Metric</th>
            ${selectedDevices.map(d => `<th>${d.label}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Health Score</td>
            ${selectedDevices.map(d => `<td class="${this.getHealthClass(d.health_score)}">${d.health_score !== null ? d.health_score.toFixed(1) : 'N/A'}</td>`).join('')}
          </tr>
          <tr>
            <td>Battery Level</td>
            ${selectedDevices.map(d => {
              const battery = d.battery || d.metrics?.battery;
              return `<td>${battery !== null && battery !== undefined ? battery + '%' : 'N/A'}</td>`;
            }).join('')}
          </tr>
          <tr>
            <td>Link Quality</td>
            ${selectedDevices.map(d => {
              const lqi = d.link_quality || d.metrics?.link_quality;
              return `<td class="${this.getLinkQualityClass(lqi)}">${lqi !== null && lqi !== undefined ? lqi : 'N/A'}</td>`;
            }).join('')}
          </tr>
          <tr>
            <td>Reconnect Rate</td>
            ${selectedDevices.map(d => {
              const rate = d.analytics?.reconnect_rate;
              return `<td>${rate !== null && rate !== undefined ? rate.toFixed(2) + '/hr' : 'N/A'}</td>`;
            }).join('')}
          </tr>
          <tr>
            <td>Last Seen</td>
            ${selectedDevices.map(d => {
              const lastSeen = d.last_seen || d.metrics?.last_seen;
              return `<td>${lastSeen ? new Date(lastSeen).toLocaleString() : 'Never'}</td>`;
            }).join('')}
          </tr>
        </tbody>
      </table>
    `;
  }

  getHealthClass(score) {
    if (score === null || score === undefined) return '';
    if (score >= 80) return 'health-good';
    if (score >= 50) return 'health-warning';
    return 'health-critical';
  }

  attachAnalyticsEventListeners() {
    // Export buttons
    const exportJson = this.shadowRoot.getElementById('export-json');
    const exportCsv = this.shadowRoot.getElementById('export-csv');

    if (exportJson) {
      exportJson.addEventListener('click', () => this.exportAnalytics('json'));
    }

    if (exportCsv) {
      exportCsv.addEventListener('click', () => this.exportAnalytics('csv'));
    }

    // Device comparison checkboxes
    const comparisonCheckboxes = this.shadowRoot.querySelectorAll('[data-comparison-device]');
    comparisonCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        const deviceId = e.target.value;
        if (e.target.checked) {
          this._selectedDevicesForComparison.add(deviceId);
        } else {
          this._selectedDevicesForComparison.delete(deviceId);
        }
        this.render();
      });
    });
  }

  async exportAnalytics(format) {
    try {
      const url = `/api/zigsight/analytics/export?format=${format}`;
      
      if (format === 'csv') {
        // For CSV, we need to handle it differently since it's not JSON
        const response = await fetch(url, {
          headers: {
            'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          },
        });
        
        const blob = await response.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `zigsight-analytics-${new Date().toISOString().split('T')[0]}.csv`;
        link.click();
        URL.revokeObjectURL(downloadUrl);
      } else {
        const data = await this._hass.callApi('GET', url);
        const dataStr = JSON.stringify(data, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const downloadUrl = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `zigsight-analytics-${new Date().toISOString().split('T')[0]}.json`;
        link.click();
        URL.revokeObjectURL(downloadUrl);
      }
    } catch (error) {
      console.error('Failed to export analytics:', error);
      alert('Failed to export analytics data. Please try again.');
    }
  }

  async initializeCharts() {
    // Load Chart.js from CDN if not already loaded
    if (!window.Chart) {
      await this.loadScript('https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js');
    }

    const overview = this._analyticsOverview;
    
    // Battery Distribution Chart
    const batteryCtx = this.shadowRoot.getElementById('battery-chart');
    if (batteryCtx) {
      new window.Chart(batteryCtx, {
        type: 'doughnut',
        data: {
          labels: Object.keys(overview.battery_distribution),
          datasets: [{
            data: Object.values(overview.battery_distribution),
            backgroundColor: [
              '#f44336',
              '#FF9800',
              '#FFC107',
              '#8BC34A',
              '#4CAF50',
            ],
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              display: false
            }
          }
        }
      });
    }

    // Link Quality Distribution Chart
    const lqiCtx = this.shadowRoot.getElementById('lqi-chart');
    if (lqiCtx) {
      new window.Chart(lqiCtx, {
        type: 'doughnut',
        data: {
          labels: Object.keys(overview.link_quality_distribution),
          datasets: [{
            data: Object.values(overview.link_quality_distribution),
            backgroundColor: [
              '#f44336',
              '#FF9800',
              '#8BC34A',
              '#4CAF50',
            ],
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              display: false
            }
          }
        }
      });
    }
  }

  getAnalyticsStyles() {
    return `
      .analytics-section {
        margin-bottom: 32px;
      }
      
      .section-title {
        font-size: 18px;
        font-weight: 500;
        margin-bottom: 16px;
        color: var(--primary-text-color);
        border-bottom: 2px solid var(--divider-color);
        padding-bottom: 8px;
      }
      
      .charts-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 24px;
        margin-top: 16px;
      }
      
      .chart-card {
        background: var(--primary-background-color);
        padding: 16px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
      }
      
      .chart-title {
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 12px;
        color: var(--primary-text-color);
      }
      
      .chart-legend {
        margin-top: 12px;
        font-size: 12px;
      }
      
      .legend-item {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
      }
      
      .legend-label {
        color: var(--secondary-text-color);
      }
      
      .legend-value {
        color: var(--primary-text-color);
        font-weight: 500;
      }
      
      .alerts-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      
      .alert-item {
        display: flex;
        gap: 12px;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--primary-background-color);
      }
      
      .alert-item.warning {
        background: #fff3e0;
        border-color: #FF9800;
      }
      
      .alert-item.success {
        background: #e8f5e9;
        border-color: #4CAF50;
      }
      
      .alert-icon {
        font-size: 24px;
      }
      
      .alert-title {
        font-weight: 500;
        color: var(--primary-text-color);
        margin-bottom: 4px;
      }
      
      .alert-desc {
        font-size: 12px;
        color: var(--secondary-text-color);
      }
      
      .stat-value.warning {
        color: #f57c00;
      }
      
      .comparison-controls {
        margin-bottom: 16px;
      }
      
      .device-list-compact {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 8px;
        margin-top: 12px;
        max-height: 300px;
        overflow-y: auto;
        padding: 12px;
        background: var(--primary-background-color);
        border-radius: 8px;
      }
      
      .device-checkbox {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        cursor: pointer;
        border-radius: 4px;
        transition: background 0.2s;
      }
      
      .device-checkbox:hover {
        background: var(--secondary-background-color);
      }
      
      .device-checkbox input[type="checkbox"] {
        width: 16px;
        height: 16px;
      }
      
      .more-devices {
        grid-column: 1 / -1;
        text-align: center;
        color: var(--secondary-text-color);
        font-size: 12px;
        padding: 8px;
      }
      
      .comparison-table-element {
        width: 100%;
        border-collapse: collapse;
        background: var(--card-background-color);
        border-radius: 8px;
        overflow: hidden;
      }
      
      .comparison-table-element th,
      .comparison-table-element td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid var(--divider-color);
      }
      
      .comparison-table-element th {
        background: var(--primary-background-color);
        font-weight: 500;
        font-size: 12px;
        text-transform: uppercase;
        color: var(--secondary-text-color);
      }
      
      .comparison-table-element tbody tr:hover {
        background: var(--secondary-background-color);
      }
      
      .health-good {
        color: #4CAF50;
        font-weight: 500;
      }
      
      .health-warning {
        color: #FF9800;
        font-weight: 500;
      }
      
      .health-critical {
        color: #f44336;
        font-weight: 500;
      }
      
      .export-controls {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }
      
      canvas {
        max-height: 300px;
      }
    `;
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
      <div class="loading">Loading devices...</div>
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
      <div class="error">${message}</div>
    `;
  }

  getCardSize() {
    return 10;
  }

  // Topology view methods
  getCommonStyles() {
    return `
      :host {
        display: block;
        width: 100%;
      }
      
      .panel {
        background: var(--ha-card-background, var(--card-background-color, white));
        border-radius: var(--ha-card-border-radius, 4px);
        box-shadow: var(--ha-card-box-shadow, 0 2px 2px 0 rgba(0,0,0,0.14));
        padding: 16px;
      }
      
      .panel-header {
        font-size: 24px;
        font-weight: 400;
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      
      .header-controls {
        display: flex;
        gap: 8px;
        align-items: center;
      }
      
      .view-toggle {
        display: flex;
        gap: 0;
        background: var(--primary-background-color);
        border-radius: 4px;
        overflow: hidden;
        border: 1px solid var(--divider-color);
      }
      
      .view-toggle button {
        background: transparent;
        color: var(--primary-text-color);
        border: none;
        padding: 6px 12px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s;
      }
      
      .view-toggle button:hover {
        background: var(--secondary-background-color);
      }
      
      .view-toggle button.active {
        background: var(--primary-color);
        color: white;
      }
      
      .stats {
        display: flex;
        gap: 16px;
        margin-bottom: 24px;
        flex-wrap: wrap;
      }
      
      .stat {
        background: var(--primary-background-color);
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 14px;
        flex: 1;
        min-width: 150px;
      }
      
      .stat-label {
        color: var(--secondary-text-color);
        font-size: 12px;
        margin-bottom: 4px;
      }
      
      .stat-value {
        font-size: 24px;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      
      button {
        background: var(--primary-color);
        color: white;
        border: none;
        padding: 8px 16px;
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
    `;
  }

  getTopologyStyles() {
    return `
      .topology-toolbar {
        background: var(--primary-background-color);
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        align-items: center;
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
      
      button.toggle {
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
        border: 1px solid var(--divider-color);
        padding: 6px 12px;
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
      
      .topology-container {
        position: relative;
        width: 100%;
        height: 600px;
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 16px;
      }
      
      #network-graph {
        width: 100%;
        height: 100%;
      }
      
      .device-info {
        position: absolute;
        top: 16px;
        right: 16px;
        background: var(--card-background-color);
        padding: 16px;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
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
      
      .topology-legend {
        display: flex;
        gap: 16px;
        padding: 12px 16px;
        background: var(--primary-background-color);
        border-radius: 8px;
        flex-wrap: wrap;
        font-size: 12px;
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
    `;
  }

  attachTopologyEventListeners() {
    const fitBtn = this.shadowRoot.getElementById('fit-topology');
    const layoutSelect = this.shadowRoot.getElementById('layout-select');
    const toggleLqi = this.shadowRoot.getElementById('toggle-lqi');
    const toggleProblems = this.shadowRoot.getElementById('toggle-problems');
    const closeInfo = this.shadowRoot.getElementById('close-info');
    const typeToggles = this.shadowRoot.querySelectorAll('.toggle[data-type]');

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

      nodeData.color = this.getNodeColor(device);
      nodeData.shape = this.getNodeShape(device.type);
      nodeData.size = this.getNodeSize(device.type);
      nodeData.font = {
        size: 12,
        color: getComputedStyle(document.documentElement).getPropertyValue('--primary-text-color') || '#000'
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
          color: this.getLinkQualityColorForEdge(edge.link_quality),
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
      this._network = null;
    }

    // Create network using vis-network
    this.createVisNetwork(container, data, options).then(network => {
      this._network = network;
      
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

  getLinkQualityColorForEdge(lqi) {
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
          color: this.getLinkQualityColorForEdge(edge.link_quality),
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

    const healthStatus = this.getHealthStatusLabel(device.health_score);
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

  getHealthStatusLabel(score) {
    if (score === null || score === undefined) return 'Unknown';
    if (score >= 80) return 'Healthy';
    if (score >= 50) return 'Warning';
    return 'Critical';
  }

  async createVisNetwork(container, data, options) {
    // Load vis-network from CDN if not already loaded
    if (!window.vis || !window.vis.Network) {
      await this.loadScript('https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js');
    }
    
    return new window.vis.Network(container, data, options);
  }

  loadScript(src) {
    return new Promise((resolve, reject) => {
      // Check if script is already loading or loaded
      const existing = document.querySelector(`script[src="${src}"]`);
      if (existing) {
        if (window.vis && window.vis.Network) {
          resolve();
        } else {
          existing.addEventListener('load', resolve);
          existing.addEventListener('error', reject);
        }
        return;
      }

      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
}

customElements.define('zigsight-panel', ZigSightPanel);

// Register the panel with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'zigsight-panel',
  name: 'ZigSight Device List Panel',
  description: 'Comprehensive device management with filtering, sorting, search, and bulk actions',
  preview: true,
});

console.info(
  '%c ZigSight Device List Panel %c v1.0.0 ',
  'background-color: #2196F3; color: #fff; font-weight: bold;',
  'background-color: #333; color: #fff; font-weight: bold;'
);
