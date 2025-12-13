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
      this._devices = response.nodes || [];
      this.applyFiltersAndSort();
    } catch (error) {
      console.error('Failed to load devices:', error);
      this.renderError('Failed to load devices. Please check that ZigSight is configured correctly.');
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
          <span>ZigSight Device List</span>
          <button @click="${() => this.loadDevices()}">Refresh</button>
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
              <select>
                <option value="all" ${this._filters.deviceType === 'all' ? 'selected' : ''}>All Types</option>
                <option value="coordinator" ${this._filters.deviceType === 'coordinator' ? 'selected' : ''}>Coordinator</option>
                <option value="router" ${this._filters.deviceType === 'router' ? 'selected' : ''}>Router</option>
                <option value="end_device" ${this._filters.deviceType === 'end_device' ? 'selected' : ''}>End Device</option>
              </select>
            </div>
            
            <div class="filter-group">
              <label class="filter-label">Health Status</label>
              <select>
                <option value="all" ${this._filters.healthStatus === 'all' ? 'selected' : ''}>All Status</option>
                <option value="healthy" ${this._filters.healthStatus === 'healthy' ? 'selected' : ''}>Healthy</option>
                <option value="warning" ${this._filters.healthStatus === 'warning' ? 'selected' : ''}>Warning</option>
                <option value="critical" ${this._filters.healthStatus === 'critical' ? 'selected' : ''}>Critical</option>
              </select>
            </div>
            
            <div class="filter-group">
              <label class="filter-label">Integration Source</label>
              <select>
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
            <button class="secondary" ${this._selectedDevices.size === 0 ? 'disabled' : ''}>
              Export Selected (${this._selectedDevices.size})
            </button>
            <button class="secondary">Export All</button>
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
                  <input type="checkbox" ${allSelected ? 'checked' : ''} />
                </th>
                <th class="sortable ${this._sortBy === 'name' ? 'sorted-' + this._sortDirection : ''}">Device</th>
                <th class="sortable ${this._sortBy === 'health' ? 'sorted-' + this._sortDirection : ''}">Health</th>
                <th>Type</th>
                <th class="sortable ${this._sortBy === 'battery' ? 'sorted-' + this._sortDirection : ''}">Battery</th>
                <th class="sortable ${this._sortBy === 'linkQuality' ? 'sorted-' + this._sortDirection : ''}">Link Quality</th>
                <th class="sortable ${this._sortBy === 'lastSeen' ? 'sorted-' + this._sortDirection : ''}">Last Seen</th>
                <th class="sortable ${this._sortBy === 'reconnectCount' ? 'sorted-' + this._sortDirection : ''}">Reconnects</th>
              </tr>
            </thead>
            <tbody>
              ${this.renderDeviceRows(paginatedDevices)}
            </tbody>
          </table>
          
          ${totalPages > 1 ? `
            <div class="pagination">
              <button ${this._currentPage === 1 ? 'disabled' : ''}>First</button>
              <button ${this._currentPage === 1 ? 'disabled' : ''}>Previous</button>
              <span class="page-info">Page ${this._currentPage} of ${totalPages}</span>
              <button ${this._currentPage === totalPages ? 'disabled' : ''}>Next</button>
              <button ${this._currentPage === totalPages ? 'disabled' : ''}>Last</button>
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
    // Search input
    const searchInput = this.shadowRoot.querySelector('input[type="search"]');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.handleFilterChange('searchQuery', e.target.value);
      });
    }
    
    // Filter selects
    const selects = this.shadowRoot.querySelectorAll('select');
    selects.forEach((select, index) => {
      select.addEventListener('change', (e) => {
        const filterMap = ['deviceType', 'healthStatus', 'integrationSource'];
        this.handleFilterChange(filterMap[index], e.target.value);
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
    
    // Table header sorting
    const headers = this.shadowRoot.querySelectorAll('.device-table th.sortable');
    headers.forEach((header, index) => {
      header.addEventListener('click', () => {
        const sortMap = ['name', 'health', 'battery', 'linkQuality', 'lastSeen', 'reconnectCount'];
        // Skip first column (checkbox)
        this.handleSortChange(sortMap[index]);
      });
    });
    
    // Checkbox selection
    const selectAllCheckbox = this.shadowRoot.querySelector('thead input[type="checkbox"]');
    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener('change', () => {
        this.toggleSelectAll();
      });
    }
    
    const deviceCheckboxes = this.shadowRoot.querySelectorAll('tbody input[type="checkbox"]');
    deviceCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        this.toggleDeviceSelection(e.target.dataset.deviceId);
      });
    });
    
    // Bulk action buttons
    const buttons = this.shadowRoot.querySelectorAll('.bulk-actions button');
    if (buttons[0]) {
      buttons[0].addEventListener('click', () => {
        this.exportSelectedDevices();
      });
    }
    if (buttons[1]) {
      buttons[1].addEventListener('click', () => {
        this.exportAllDevices();
      });
    }
    
    // Pagination buttons
    const paginationButtons = this.shadowRoot.querySelectorAll('.pagination button');
    if (paginationButtons.length > 0) {
      paginationButtons[0].addEventListener('click', () => {
        this._currentPage = 1;
        this.render();
      });
      paginationButtons[1].addEventListener('click', () => {
        if (this._currentPage > 1) {
          this._currentPage--;
          this.render();
        }
      });
      paginationButtons[2].addEventListener('click', () => {
        if (this._currentPage < this.getTotalPages()) {
          this._currentPage++;
          this.render();
        }
      });
      paginationButtons[3].addEventListener('click', () => {
        this._currentPage = this.getTotalPages();
        this.render();
      });
    }
    
    // Refresh button
    const refreshBtn = this.shadowRoot.querySelector('.panel-header button');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.loadDevices());
    }
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
