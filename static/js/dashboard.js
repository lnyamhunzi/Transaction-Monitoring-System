/**
 * Banking AML Dashboard - Main JavaScript Module
 * Real-time monitoring and interactive dashboard functionality
 */

// Function to get the authentication token from localStorage
function getAuthToken() {
    return localStorage.getItem('admin_token');
}


class AMLDashboard {
    constructor() {
        this.websocket = null;
        this.charts = {};
        this.alertsTable = null;
        this.transactionsTable = null;
        this.isConnected = false;
        
        // Configuration
        this.config = {
            refreshInterval: 30000, // 30 seconds
            maxAlerts: 100,
            riskThresholds: {
                low: 0.3,
                medium: 0.6,
                high: 0.8,
                critical: 0.9
            }
        };
        
        this.init();
    }
    
    /**
     * Initialize the dashboard
     */
    async init() {
        console.log('Initializing AML Dashboard...');
        
        try {
            await this.setupWebSocket();
            await this.initializeCharts();
            await this.initTransactionsTable();
            await this.loadInitialData();
            await this.setupEventListeners();
            await this.startPeriodicRefresh();
            
            console.log('Dashboard initialized successfully');
        } catch (error) {
            console.error('Error initializing dashboard:', error);
            this.showError('Failed to initialize dashboard');
        }
    }
    
    /**
     * Setup WebSocket connection for real-time updates
     */
    async setupWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.updateConnectionStatus(true);
            };
            
            this.websocket.onmessage = (event) => {
                this.handleWebSocketMessage(JSON.parse(event.data));
            };
            
            this.websocket.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.updateConnectionStatus(false);
                
                // Attempt to reconnect after 5 seconds
                setTimeout(() => this.setupWebSocket(), 5000);
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.showError('Real-time connection error');
            };
            
        } catch (error) {
            console.error('Error setting up WebSocket:', error);
        }
    }
    
    /**
     * Handle incoming WebSocket messages
     */
    handleWebSocketMessage(message) {
        console.log('Received real-time message:', message);
        
        switch (message.type) {
            case 'new_alert':
                this.handleNewAlert(message.alert);
                break;
            case 'transaction_processed':
                this.handleNewTransaction(message.transaction);
                break;
            case 'case_updated':
                this.handleCaseUpdate(message.case);
                break;
            case 'system_status':
                this.handleSystemStatus(message.status);
                break;
            case 'transaction_status_update':
                if (this.transactionsTable) {
                    this.transactionsTable.ajax.reload(null, false);
                }
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    }
    
    /**
     * Get authentication headers
     */
    async getAuthHeaders() {
        const token = await getAuthToken();
        if (!token) {
            window.location.href = '/admin/login';
            return null;
        }
        return {
            'Authorization': `Bearer ${token}`
        };
    }

    /**
     * Load initial dashboard data
     */
    async loadInitialData() {
        try {
            this.showLoading(true);
            const headers = await this.getAuthHeaders();
            if (!headers) {
                return;
            }

            // Load dashboard statistics
            const statsResponse = await fetch('/api/dashboard/stats', { headers });
            if (statsResponse.status === 401) { window.location.href = '/admin/login'; return; }
            if (!statsResponse.ok) throw new Error('Failed to load stats');
            const stats = await statsResponse.json();
            
            this.updateDashboardStats(stats);
            
            // Load AML Control Summary
            const amlSummaryResponse = await fetch('/api/dashboard/aml-control-summary', { headers });
            if (amlSummaryResponse.status === 401) { window.location.href = '/admin/login'; return; }
            if (!amlSummaryResponse.ok) throw new Error('Failed to load AML control summary');
            const amlSummary = await amlSummaryResponse.json();
            this.updateAmlControlSummary(amlSummary);

            // Load charts data
            const chartsDataResponse = await fetch('/api/reports/charts-data', { headers });
            if (chartsDataResponse.status === 401) { window.location.href = '/admin/login'; return; }
            if (!chartsDataResponse.ok) throw new Error('Failed to load charts data');
            const chartsData = await chartsDataResponse.json();
            this.updateTransactionVolumeChartData(chartsData.volume_trends);
            
            // Load recent alerts
            this.loadAlerts();

            // transactions are loaded by datatables ajax
            
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showError('Failed to load dashboard data');
        } finally {
            this.showLoading(false);
        }
    }

    async loadAlerts(queryString = '') {
        try {
            this.showLoading(true);
            const headers = await this.getAuthHeaders();
            if (!headers) return;

            const url = `/api/alerts/?${queryString}`;
            const response = await fetch(url, { headers });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load alerts');
            
            const alerts = await response.json();
            this.updateAlertsTable(alerts);
            
        } catch (error) {
            console.error('Error loading alerts:', error);
            this.showError('Failed to load alerts');
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Update AML Control Summary display
     */
    updateAmlControlSummary(summaryData) {
        const listContainer = document.getElementById('aml-control-summary-list');
        if (!listContainer) return;

        listContainer.innerHTML = ''; // Clear loading message

        if (summaryData.length === 0) {
            listContainer.innerHTML = '<p class="text-muted text-center">No AML controls triggered recently.</p>';
            return;
        }

        summaryData.forEach(item => {
            const listItem = document.createElement('div');
            listItem.className = 'list-group-item d-flex justify-content-between align-items-center';
            listItem.innerHTML = `
                <div>
                    <h6 class="mb-1">${item.control_type.replace(/_/g, ' ')}</h6>
                    <small class="text-muted">Avg. Risk Score: ${item.average_risk_score}</small>
                </div>
                <span class="badge bg-primary rounded-pill">${item.triggered_count}</span>
            `;
            listContainer.appendChild(listItem);
        });
    }
    
    /**
     * Update dashboard statistics
     */
    updateDashboardStats(stats) {
        // Update metric cards
        this.updateMetricCard('today-transactions', stats.today_transactions);
        this.updateMetricCard('open-alerts', stats.open_alerts);
        this.updateMetricCard('high-risk-alerts', stats.high_risk_alerts);
        
        // Update risk distribution chart
        if (this.charts.riskDistribution) {
            this.updateRiskDistributionChart(stats.risk_distribution);
        }
        
        // Update alert trends
        this.updateAlertTrends(stats.alert_trends);
    }
    
    /**
     * Update metric card value
     */
    updateMetricCard(cardId, value, change = null) {
        const card = document.getElementById(cardId);
        if (!card) return;
        
        const valueElement = card.querySelector('.metric-value');
        const changeElement = card.querySelector('.metric-change');
        
        if (valueElement) {
            // Animate the value change
            this.animateNumber(valueElement, parseInt(valueElement.textContent) || 0, value);
        }
        
        if (changeElement && change !== null) {
            changeElement.textContent = `${change > 0 ? '+' : ''}${change}%`;
            changeElement.className = `metric-change ${change > 0 ? 'change-positive' : 'change-negative'}`;
        }
    }
    
    /**
     * Animate number changes
     */
    animateNumber(element, start, end, duration = 1000) {
        const startTime = Date.now();
        const range = end - start;
        
        const timer = setInterval(() => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function
            const easeOutCubic = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + (range * easeOutCubic));
            
            element.textContent = current.toLocaleString();
            
            if (progress === 1) {
                clearInterval(timer);
            }
        }, 16);
    }
    
    /**
     * Initialize charts
     */
    async initializeCharts() {
        try {
            // Risk Distribution Pie Chart
            await this.initRiskDistributionChart();
            
            // Alert Trends Line Chart
            await this.initAlertTrendsChart();
            
            // Transaction Volume Chart
            await this.initTransactionVolumeChart();
            
        } catch (error) {
            console.error('Error initializing charts:', error);
        }
    }
    
    /**
     * Initialize risk distribution chart
     */
    async initRiskDistributionChart() {
        const ctx = document.getElementById('riskDistributionChart');
        if (!ctx) return;
        
        this.charts.riskDistribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Low Risk', 'Medium Risk', 'High Risk', 'Critical Risk'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: [
                        '#28a745', // Green
                        '#ffc107', // Yellow
                        '#fd7e14', // Orange
                        '#dc3545'  // Red
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }
    
    /**
     * Initialize alert trends chart
     */
    async initAlertTrendsChart() {
        const ctx = document.getElementById('alertTrendsChart');
        if (!ctx) return;
        
        this.charts.alertTrends = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'High Risk Alerts',
                    data: [],
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    tension: 0.4,
                    fill: true
                }, {
                    label: 'Medium Risk Alerts',
                    data: [],
                    borderColor: '#ffc107',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Alerts'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    }
                }
            }
        });
    }
    
    /**
     * Initialize transaction volume chart
     */
    async initTransactionVolumeChart() {
        const ctx = document.getElementById('transactionVolumeChart');
        if (!ctx) return;
        
        this.charts.transactionVolume = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Transaction Volume (USD)',
                    data: [],
                    backgroundColor: 'rgba(30, 58, 95, 0.8)',
                    borderColor: '#1e3a5f',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Volume (USD)'
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'Volume: $' + context.parsed.y.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }
    
    /**
     * Update risk distribution chart
     */
    updateRiskDistributionChart(riskData) {
        if (!this.charts.riskDistribution) return;
        
        const chart = this.charts.riskDistribution;
        const newData = [0, 0, 0, 0]; // [low, medium, high, critical]
        
        riskData.forEach(item => {
            const avgRisk = item.avg_risk;
            const count = item.count;
            
            if (avgRisk < this.config.riskThresholds.medium) {
                newData[0] += count;
            } else if (avgRisk < this.config.riskThresholds.high) {
                newData[1] += count;
            } else if (avgRisk < this.config.riskThresholds.critical) {
                newData[2] += count;
            } else {
                newData[3] += count;
            }
        });
        
        chart.data.datasets[0].data = newData;
        chart.update('active');
    }

    /**
     * Update alert trends chart
     */
    updateAlertTrends(alertTrends) {
        if (!this.charts.alertTrends) return;

        const chart = this.charts.alertTrends;
        if (alertTrends) {
            chart.data.labels = alertTrends.labels;
            chart.data.datasets[0].data = alertTrends.high_risk;
            chart.data.datasets[1].data = alertTrends.medium_risk;
            chart.update('active');
        }
    }

    /**
     * Update transaction volume chart data
     */
    updateTransactionVolumeChartData(volumeTrends) {
        if (!this.charts.transactionVolume) return;

        const chart = this.charts.transactionVolume;
        if (volumeTrends) {
            chart.data.labels = volumeTrends.labels;
            chart.data.datasets[0].data = volumeTrends.total_volume;
            // If you have high_risk_volume, you might add another dataset or modify the existing one
            chart.update('active');
        }
    }
    
    /**
     * Handle new alert from WebSocket
     */
    handleNewAlert(alert) {
        console.log('New alert received:', alert);
        
        // Show notification
        this.showNotification(`New ${alert.alert_type} alert`, 'warning'); // Changed alert.type to alert.alert_type
        
        // Refresh the recent alerts table and all dashboard metrics/charts
        this.loadAlerts();
        this.loadInitialData(); // This will refresh all metrics including alert counts
        
        // Play notification sound for high-risk alerts
        if (alert.risk_score >= 0.8) {
            this.playNotificationSound();
        }
    }
    
    /**
     * Handle new transaction from WebSocket
     */
    handleNewTransaction(transaction) {
        console.log('New transaction received:', transaction);
        // Trigger a full dashboard refresh to update all metrics and charts
        this.loadInitialData();
        
        // Add new transaction to table (if applicable, though loadInitialData will refresh this too)
        // if (this.transactionsTable) {
        //     this.transactionsTable.row.add(transaction).draw(false);
        // }
    }
    
    /**
     * Setup event listeners
     */
    async setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refreshDashboard');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshDashboard());
        }
        
        // Export buttons
        const exportBtn = document.getElementById('exportAlerts');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportAlerts());
        }
        
        // Alert filters
        const statusFilter = document.getElementById('alertStatusFilter');
        if (statusFilter) {
            statusFilter.addEventListener('change', () => this.filterAlerts());
        }
        
        const typeFilter = document.getElementById('alertTypeFilter');
        if (typeFilter) {
            typeFilter.addEventListener('change', () => this.filterAlerts());
        }
        
        // Transaction filters
        const applyTransactionFiltersBtn = document.getElementById('applyTransactionFiltersBtn');
        if(applyTransactionFiltersBtn) {
            applyTransactionFiltersBtn.addEventListener('click', () => {
                if (this.transactionsTable) {
                    this.transactionsTable.ajax.reload();
                }
            });
        }

        // Modal triggers
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('view-alert-btn')) {
                const alertId = e.target.dataset.alertId;
                this.showAlertDetails(alertId);
            }
            
            if (e.target.classList.contains('create-case-btn')) {
                const alertId = e.target.dataset.alertId;
                this.showCreateCaseModal(alertId);
            }
        });
        
        // Window resize handler for charts
        window.addEventListener('resize', () => {
            Object.values(this.charts).forEach(chart => {
                if (chart && typeof chart.resize === 'function') {
                    chart.resize();
                }
            });
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 'r':
                        e.preventDefault();
                        this.refreshDashboard();
                        break;
                    case 'e':
                        e.preventDefault();
                        this.exportAlerts();
                        break;
                }
            }
        });
    }
    
    /**
     * Filter alerts based on selected criteria
     */
    filterAlerts() {
        const status = document.getElementById('alertStatusFilter').value;
        const type = document.getElementById('alertTypeFilter').value;
        const timeRange = document.getElementById('timeRangeFilter').value;
        const riskLevel = document.getElementById('riskLevelFilter').value;

        const params = new URLSearchParams();
        if (status) params.append('status', status);
        if (type) params.append('alert_type', type);
        if (timeRange) params.append('time_range', timeRange);
        if (riskLevel) params.append('risk_level', riskLevel);

        this.loadAlerts(params.toString());
    }

    /**
     * Update alerts table
     */
    updateAlertsTable(alerts) {
        if (window.alertsDataTable) {
            window.alertsDataTable.clear();
            window.alertsDataTable.rows.add(alerts.map(alert => this.formatAlertRow(alert)));
            window.alertsDataTable.draw();
        }
    }

    formatAlertRow(alert) {
        return [
            `
            <div class="d-flex align-items-center">
                <div class="risk-score risk-${this.getRiskLevel(alert.risk_score)}">
                    ${(alert.risk_score * 100).toFixed(0)}
                </div>
                <div class="ms-2">
                    <div class="fw-semibold">${alert.id}</div>
                    <small class="text-muted">${new Date(alert.created_at).toLocaleString()}</small>
                </div>
            </div>
            `,
            `<span class="badge bg-secondary">${alert.alert_type}</span>`,
            alert.customer_id,
            `${this.formatCurrency(Number(alert.transaction?.amount) || 0)} ${alert.transaction?.currency || 'USD'}`,
            `<span class="status-badge status-${alert.status.toLowerCase()}">${alert.status}</span>`,
            `
            <div class="btn-group btn-group-sm">
                <button class="btn btn-outline-primary view-alert-btn" data-alert-id="${alert.id}">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="btn btn-outline-success create-case-btn" data-alert-id="${alert.id}">
                    <i class="fas fa-plus"></i>
                </button>
            </div>
            `
        ];
    }

    async initTransactionsTable() {
        this.transactionsTable = $('#transactionsTable').DataTable({
            "processing": true,
            "serverSide": true,
            "ajax": {
                "url": "/api/monitoring/transactions",
                "type": "GET",
                "data": function (d) {
                    d.search_term = $('#transactionSearchInput').val();
                    d.transaction_type = $('#transactionTypeFilter').val();
                    d.status = $('#transactionStatusFilter').val();
                    d.date = $('#transactionDateFilter').val();
                },
                "headers": await this.getAuthHeaders()
            },
            "columns": [
                { "data": "id" },
                { "data": "customer_id" },
                { "data": "transaction_type" },
                { 
                    "data": "amount",
                    "render": function ( data, type, row ) {
                        return `${row.currency} ${data.toFixed(2)}`;
                    }
                },
                { "data": "status" },
                { 
                    "data": "created_at",
                    "render": function ( data, type, row ) {
                        return new Date(data).toLocaleString();
                    }
                },
                {
                    "data": "id",
                    "render": function ( data, type, row ) {
                        return `<a href="/monitoring/transactions/${data}" class="btn btn-sm btn-outline-primary">View</a>`;
                    }
                }
            ],
            "order": [[ 5, "desc" ]],
            "pageLength": 10,
            "responsive": true
        });
    }
    
    /**
     * Get risk level from score
     */
    getRiskLevel(score) {
        if (score >= this.config.riskThresholds.critical) return 'critical';
        if (score >= this.config.riskThresholds.high) return 'high';
        if (score >= this.config.riskThresholds.medium) return 'medium';
        return 'low';
    }
    
    /**
     * Format currency
     */
    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    }
    
    /**
     * Increment metric card value
     */
    incrementMetricCard(cardId) {
        const card = document.getElementById(cardId);
        if (!card) return;
        
        const valueElement = card.querySelector('.metric-value');
        if (valueElement) {
            const currentValue = parseInt(valueElement.textContent.replace(/,/g, '')) || 0;
            this.animateNumber(valueElement, currentValue, currentValue + 1);
        }
    }
    
    /**
     * Start periodic refresh
     */
    startPeriodicRefresh() {
        setInterval(() => {
            if (!this.isConnected) {
                this.loadInitialData();
            }
        }, this.config.refreshInterval);
    }
    
    /**
     * Refresh dashboard manually
     */
    async refreshDashboard() {
        console.log('Refreshing dashboard...');
        await this.loadInitialData();
        if(this.transactionsTable) {
            this.transactionsTable.ajax.reload();
        }
        this.showNotification('Dashboard refreshed', 'success');
    }
    
    /**
     * Update connection status indicator
     */
    updateConnectionStatus(connected) {
        const indicator = document.querySelector('.realtime-indicator');
        if (!indicator) return;
        
        if (connected) {
            indicator.className = 'realtime-indicator';
            indicator.innerHTML = '<span class="realtime-dot"></span>Real-time Connected';
            indicator.style.backgroundColor = '#28a745';
        } else {
            indicator.className = 'realtime-indicator';
            indicator.innerHTML = '<span class="realtime-dot"></span>Connection Lost';
            indicator.style.backgroundColor = '#dc3545';
        }
    }
    
    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Add to notifications container
        const container = document.getElementById('notifications') || document.body;
        container.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
    
    /**
     * Show error message
     */
    showError(message) {
        this.showNotification(message, 'danger');
    }
    
    /**
     * Show/hide loading state
     */
    showLoading(show) {
        const loader = document.getElementById('dashboardLoader');
        if (loader) {
            loader.style.display = show ? 'block' : 'none';
        }
    }
    
    /**
     * Play notification sound
     */
    playNotificationSound() {
        try {
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBl');
            audio.play().catch(() => {
                // Ignore errors if audio cannot be played
            });
        } catch (error) {
            // Ignore errors
        }
    }
    
    /**
     * Show alert details modal
     */
    async showAlertDetails(alertId) {
        try {
            const response = await fetch(`/api/alerts/${alertId}`, { headers: await this.getAuthHeaders() });
            if (!response.ok) throw new Error('Failed to load alert details');
            
            const alert = await response.json();
            
            // Create and show modal
            const modal = this.createAlertDetailsModal(alert);
            document.body.appendChild(modal);
            
            // Show modal with Bootstrap
            if (typeof bootstrap !== 'undefined') {
                new bootstrap.Modal(modal).show();
            }
            
        } catch (error) {
            console.error('Error showing alert details:', error);
            this.showError('Failed to load alert details');
        }
    }
    
    /**
     * Create alert details modal
     */
    createAlertDetailsModal(alert) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Alert Details - ${alert.id}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6>Alert Information</h6>
                                <table class="table table-sm">
                                    <tr><td>Alert Type</td><td>${alert.alert_type}</td></tr>
                                    <tr><td>Risk Score</td><td><span class="risk-score risk-${this.getRiskLevel(alert.risk_score)}">${(alert.risk_score * 100).toFixed(0)}</span></td></tr>
                                    <tr><td>Status</td><td><span class="status-badge status-${alert.status.toLowerCase()}">${alert.status}</span></td></tr>
                                    <tr><td>Priority</td><td>${alert.priority || 'Medium'}</td></tr>
                                    <tr><td>Created</td><td>${new Date(alert.created_at).toLocaleString()}</td></tr>
                                </table>
                            </div>
                            <div class="col-md-6">
                                <h6>Transaction Details</h6>
                                <table class="table table-sm">
                                    <tr><td>Transaction ID</td><td>${alert.transaction_id}</td></tr>
                                    <tr><td>Customer ID</td><td>${alert.customer_id}</td></tr>
                                    <tr><td>Amount</td><td>${this.formatCurrency(alert.transaction?.amount || 0)} ${alert.transaction?.currency || 'USD'}</td></tr>
                                    <tr><td>Channel</td><td>${alert.transaction?.channel || 'N/A'}</td></tr>
                                    <tr><td>Type</td><td>${alert.transaction?.transaction_type || 'N/A'}</td></tr>
                                </table>
                            </div>
                        </div>
                        <div class="mt-3">
                            <h6>Description</h6>
                            <p>${alert.description}</p>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-success create-case-btn" data-alert-id="${alert.id}">Create Case</button>
                    </div>
                </div>
            </div>
        `;
        
        return modal;
    }
    
    /**
     * Export alerts to CSV
     */
    async exportAlerts() {
        try {
            const response = await fetch('/api/alerts/export', { headers: await this.getAuthHeaders() });
            if (!response.ok) throw new Error('Failed to export alerts');
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `alerts_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showNotification('Alerts exported successfully', 'success');
            
        } catch (error) {
            console.error('Error exporting alerts:', error);
            this.showError('Failed to export alerts');
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.amlDashboard = new AMLDashboard();
});
