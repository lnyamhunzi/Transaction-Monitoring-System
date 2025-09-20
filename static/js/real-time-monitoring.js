/**
 * Real-time Monitoring Module
 * Advanced real-time transaction monitoring and alert management
 */

class RealTimeMonitor {
    constructor() {
        this.websocket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectInterval = 5000;
        
        this.monitoringData = {
            transactions: [],
            alerts: [],
            systemMetrics: {}
        };
        
        this.charts = {
            realTimeFlow: null,
            riskDistribution: null,
            transactionVolume: null,
            alertTrends: null
        };
        
        this.filters = {
            riskLevel: 'all',
            alertType: 'all',
            timeRange: '1h'
        };
        
        this.init();
    }
    
    /**
     * Initialize real-time monitoring
     */
    async init() {
        console.log('Initializing Real-time Monitor...');
        
        try {
            await this.setupWebSocket();
            await this.initializeCharts();
            await this.setupEventListeners();
            await this.loadInitialData();
            
            console.log('Real-time monitor initialized successfully');
        } catch (error) {
            console.error('Error initializing real-time monitor:', error);
        }
    }
    
    /**
     * Setup WebSocket connection
     */
    async setupWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('Real-time WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
                
                // Subscribe to real-time updates
                this.subscribeToUpdates();
            };
            
            this.websocket.onmessage = (event) => {
                const message = JSON.parse(event.data);
                this.handleRealtimeMessage(message);
            };
            
            this.websocket.onclose = () => {
                console.log('Real-time WebSocket disconnected');
                this.isConnected = false;
                this.updateConnectionStatus(false);
                this.attemptReconnect();
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
        } catch (error) {
            console.error('Error setting up WebSocket:', error);
        }
    }
    
    /**
     * Attempt to reconnect WebSocket
     */
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            
            setTimeout(() => {
                this.setupWebSocket();
            }, this.reconnectInterval);
        } else {
            console.error('Max reconnection attempts reached');
            this.showConnectionError();
        }
    }
    
    /**
     * Subscribe to real-time updates
     */
    subscribeToUpdates() {
        if (this.websocket && this.isConnected) {
            this.websocket.send(JSON.stringify({
                type: 'subscribe',
                channels: ['transactions', 'alerts', 'system_metrics', 'ml_predictions']
            }));
        }
    }
    
    /**
     * Handle real-time messages
     */
    handleRealtimeMessage(message) {
        switch (message.type) {
            case 'transaction_stream':
                this.handleTransactionStream(message.data);
                break;
                
            case 'alert_generated':
                this.handleNewAlert(message.data);
                break;
                
            case 'ml_prediction':
                this.handleMLPrediction(message.data);
                break;
                
            case 'system_metrics':
                this.handleSystemMetrics(message.data);
                break;
                
            case 'risk_score_update':
                this.handleRiskScoreUpdate(message.data);
                break;
                
            default:
                console.log('Unknown message type:', message.type);
        }
    }
    
    /**
     * Handle transaction stream
     */
    handleTransactionStream(transactions) {
        transactions.forEach(transaction => {
            this.addTransactionToStream(transaction);
        });
        
        this.updateTransactionFlowChart();
        this.updateVolumeChart();
    }
    
    /**
     * Add transaction to real-time stream
     */
    addTransactionToStream(transaction) {
        // Add to beginning of array
        this.monitoringData.transactions.unshift(transaction);
        
        // Keep only last 100 transactions for performance
        if (this.monitoringData.transactions.length > 100) {
            this.monitoringData.transactions = this.monitoringData.transactions.slice(0, 100);
        }
        
        // Update transaction stream display
        this.updateTransactionStreamDisplay(transaction);
        
        // Check if transaction meets filter criteria
        if (this.matchesFilter(transaction)) {
            // Removed this.addTransactionToTable(transaction);
        }
    }
    
    /**
     * Update transaction stream display
     */
    updateTransactionStreamDisplay(transaction) {
        const streamContainer = document.getElementById('transactionStream');
        if (!streamContainer) return;
        
        const transactionElement = document.createElement('div');
        transactionElement.className = `transaction-item risk-${this.getRiskLevel(transaction.risk_score)}`;
        transactionElement.innerHTML = `
            <div class="transaction-flow">
                <div class="flow-step">
                    <div class="flow-icon">
                        <i class="fas fa-user"></i>
                    </div>
                    <div class="flow-label">${this.maskCustomerId(transaction.customer_id)}</div>
                </div>
                <div class="flow-step">
                    <div class="flow-icon">
                        <i class="fas fa-exchange-alt"></i>
                    </div>
                    <div class="flow-label">${this.formatCurrency(transaction.amount)} ${transaction.currency}</div>
                </div>
                <div class="flow-step">
                    <div class="flow-icon">
                        <i class="fas fa-shield-alt"></i>
                    </div>
                    <div class="flow-label">Risk: ${(transaction.risk_score * 100).toFixed(0)}%</div>
                </div>
            </div>
            <div class="transaction-meta">
                <span class="transaction-time">${new Date(transaction.timestamp).toLocaleTimeString()}</span>
                <span class="transaction-channel">${transaction.channel}</span>
                ${transaction.ml_prediction ? `<span class="ml-prediction">ML: ${transaction.ml_prediction}</span>` : ''}
            </div>
        `;
        
        // Add animation
        transactionElement.style.opacity = '0';
        transactionElement.style.transform = 'translateY(-20px)';
        
        streamContainer.insertBefore(transactionElement, streamContainer.firstChild);
        
        // Animate in
        setTimeout(() => {
            transactionElement.style.transition = 'all 0.3s ease';
            transactionElement.style.opacity = '1';
            transactionElement.style.transform = 'translateY(0)';
        }, 10);
        
        // Remove old items
        const items = streamContainer.children;
        if (items.length > 10) {
            for (let i = 10; i < items.length; i++) {
                streamContainer.removeChild(items[i]);
            }
        }
    }
    
    /**
     * Handle new alert
     */
    handleNewAlert(alert) {
        console.log('New real-time alert:', alert);
        
        // Add to alerts array
        this.monitoringData.alerts.unshift(alert);
        
        // Keep only last 50 alerts
        if (this.monitoringData.alerts.length > 50) {
            this.monitoringData.alerts = this.monitoringData.alerts.slice(0, 50);
        }
        
        // Show alert notification
        this.showAlertNotification(alert);
        
        // Update alert display
        this.updateAlertDisplay(alert);
        
        // Update charts
        this.updateRiskDistributionChart();
        this.updateAlertTrendsChart();
        
        // Play sound for high-risk alerts
        if (alert.risk_score >= 0.8) {
            this.playAlertSound();
        }
    }
    
    /**
     * Handle ML prediction
     */
    handleMLPrediction(prediction) {
        console.log('ML prediction received:', prediction);
        
        // Update ML metrics display
        this.updateMLMetrics(prediction);
        
        // Show ML prediction in transaction stream if applicable
        const transaction = this.monitoringData.transactions.find(t => t.id === prediction.transaction_id);
        if (transaction) {
            transaction.ml_prediction = prediction.prediction;
            transaction.ml_confidence = prediction.confidence;
        }
    }
    
    /**
     * Handle system metrics update
     */
    handleSystemMetrics(metrics) {
        this.monitoringData.systemMetrics = metrics;
        this.updateSystemMetricsDisplay(metrics);
    }
    
    /**
     * Initialize real-time charts
     */
    async initializeCharts() {
        await this.initTransactionFlowChart();
        await this.initRiskDistributionChart();
        await this.initVolumeChart();
        await this.initAlertTrendsChart();
    }
    
    /**
     * Initialize transaction flow chart
     */
    async initTransactionFlowChart() {
        const ctx = document.getElementById('realTimeFlowChart');
        if (!ctx) return;
        
        this.charts.realTimeFlow = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Transactions/min',
                    data: [],
                    borderColor: '#1e3a5f',
                    backgroundColor: 'rgba(30, 58, 95, 0.1)',
                    tension: 0.4,
                    fill: true
                }, {
                    label: 'High Risk Transactions/min',
                    data: [],
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 300
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                minute: 'HH:mm'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Transactions per Minute'
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
     * Initialize risk distribution chart
     */
    async initRiskDistributionChart() {
        const ctx = document.getElementById('realTimeRiskChart');
        if (!ctx) return;
        
        this.charts.riskDistribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Low Risk', 'Medium Risk', 'High Risk', 'Critical Risk'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: ['#28a745', '#ffc107', '#fd7e14', '#dc3545'],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    animateRotate: true,
                    duration: 500
                },
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    /**
     * Update transaction flow chart
     */
    updateTransactionFlowChart() {
        if (!this.charts.realTimeFlow) return;
        
        const chart = this.charts.realTimeFlow;
        const now = new Date();
        
        // Calculate transactions per minute
        const recentTransactions = this.monitoringData.transactions.filter(
            t => new Date(t.timestamp) > new Date(now.getTime() - 60000) // Last minute
        );
        
        const highRiskTransactions = recentTransactions.filter(t => t.risk_score >= 0.8);
        
        // Add data point
        chart.data.labels.push(now);
        chart.data.datasets[0].data.push(recentTransactions.length);
        chart.data.datasets[1].data.push(highRiskTransactions.length);
        
        // Keep only last 20 data points
        if (chart.data.labels.length > 20) {
            chart.data.labels = chart.data.labels.slice(-20);
            chart.data.datasets[0].data = chart.data.datasets[0].data.slice(-20);
            chart.data.datasets[1].data = chart.data.datasets[1].data.slice(-20);
        }
        
        chart.update('none');
    }
    
    /**
     * Setup event listeners
     */
    async setupEventListeners() {
        // Filter controls
        const riskFilter = document.getElementById('riskLevelFilter');
        if (riskFilter) {
            riskFilter.addEventListener('change', (e) => {
                this.filters.riskLevel = e.target.value;
                this.applyFilters();
            });
        }
        
        const alertTypeFilter = document.getElementById('alertTypeFilter');
        if (alertTypeFilter) {
            alertTypeFilter.addEventListener('change', (e) => {
                this.filters.alertType = e.target.value;
                this.applyFilters();
            });
        }
        
        const timeRangeFilter = document.getElementById('timeRangeFilter');
        if (timeRangeFilter) {
            timeRangeFilter.addEventListener('change', (e) => {
                this.filters.timeRange = e.target.value;
                this.applyFilters();
            });
        }
        
        // Control buttons
        const pauseBtn = document.getElementById('pauseMonitoring');
        if (pauseBtn) {
            pauseBtn.addEventListener('click', () => this.toggleMonitoring());
        }
        
        const clearBtn = document.getElementById('clearStream');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearTransactionStream());
        }
        
        const exportBtn = document.getElementById('exportRealTimeData');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportRealTimeData());
        }
        
        // Alert actions
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('acknowledge-alert-btn')) {
                const alertId = e.target.dataset.alertId;
                this.acknowledgeAlert(alertId);
            }
            
            if (e.target.classList.contains('investigate-alert-btn')) {
                const alertId = e.target.dataset.alertId;
                this.startInvestigation(alertId);
            }
        });
    }
    
    /**
     * Apply filters to displayed data
     */
    applyFilters() {
        const filteredTransactions = this.monitoringData.transactions.filter(t => this.matchesFilter(t));
        const filteredAlerts = this.monitoringData.alerts.filter(a => this.matchesAlertFilter(a));
        
        this.updateFilteredDisplay(filteredTransactions, filteredAlerts);
    }
    
    /**
     * Check if transaction matches current filters
     */
    matchesFilter(transaction) {
        // Risk level filter
        if (this.filters.riskLevel !== 'all') {
            const riskLevel = this.getRiskLevel(transaction.risk_score);
            if (riskLevel !== this.filters.riskLevel) return false;
        }
        
        // Time range filter
        const now = new Date();
        const transactionTime = new Date(transaction.timestamp);
        const timeDiff = now.getTime() - transactionTime.getTime();
        
        switch (this.filters.timeRange) {
            case '1h':
                if (timeDiff > 3600000) return false; // 1 hour
                break;
            case '4h':
                if (timeDiff > 14400000) return false; // 4 hours
                break;
            case '24h':
                if (timeDiff > 86400000) return false; // 24 hours
                break;
        }
        
        return true;
    }
    
    /**
     * Show alert notification
     */
    showAlertNotification(alert) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert-notification ${this.getRiskLevel(alert.risk_score)}`;
        notification.innerHTML = `
            <div class="notification-header">
                <i class="fas fa-exclamation-triangle"></i>
                <strong>New ${alert.alert_type} Alert</strong>
                <button class="close-notification" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div class="notification-body">
                <p>Risk Score: <span class="risk-score">${(alert.risk_score * 100).toFixed(0)}%</span></p>
                <p>Customer: ${this.maskCustomerId(alert.customer_id)}</p>
                <p>${alert.description}</p>
            </div>
            <div class="notification-actions">
                <button class="btn btn-sm btn-outline-primary acknowledge-alert-btn" data-alert-id="${alert.id}">
                    Acknowledge
                </button>
                <button class="btn btn-sm btn-primary investigate-alert-btn" data-alert-id="${alert.id}">
                    Investigate
                </button>
            </div>
        `;
        
        // Add to notifications container
        const container = document.getElementById('alertNotifications');
        if (container) {
            container.appendChild(notification);
            
            // Auto-remove after 10 seconds for low-risk alerts
            if (alert.risk_score < 0.6) {
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 10000);
            }
        }
    }
    
    /**
     * Play alert sound
     */
    playAlertSound() {
        // Fallback to system beep
        console.log('\u0007'); // ASCII bell character
    }
    
    /**
     * Update connection status
     */
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connectionStatus');
        if (!statusElement) {
            console.warn('Connection status element (id="connectionStatus") not found. UI will not be updated.');
            return;
        }
        
        if (connected) {
            statusElement.className = 'connection-status connected';
            statusElement.innerHTML = '<i class="fas fa-wifi"></i> Connected';
        } else {
            statusElement.className = 'connection-status disconnected';
            statusElement.innerHTML = '<i class="fas fa-wifi-slash"></i> Disconnected';
        }
    }
    
    /**
     * Get risk level from score
     */
    getRiskLevel(score) {
        if (score >= 0.9) return 'critical';
        if (score >= 0.7) return 'high';
        if (score >= 0.4) return 'medium';
        return 'low';
    }
    
    /**
     * Mask customer ID for privacy
     */
    maskCustomerId(customerId) {
        if (!customerId || customerId.length < 4) return customerId;
        return customerId.slice(0, 2) + '*'.repeat(customerId.length - 4) + customerId.slice(-2);
    }
    
    /**
     * Format currency
     */
    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    }
    
    /**
     * Initialize transaction volume chart
     */
    async initVolumeChart() {
        const ctx = document.getElementById('transactionVolumeChart');
        if (!ctx) return;

        this.charts.transactionVolume = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Transaction Volume (USD)',
                    data: [],
                    backgroundColor: 'rgba(75, 192, 192, 0.6)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'hour',
                            displayFormats: {
                                hour: 'HH:mm'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Volume (USD)'
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
                    label: 'Total Alerts',
                    data: [],
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.4,
                    fill: true
                }, {
                    label: 'High Risk Alerts',
                    data: [],
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'hour',
                            displayFormats: {
                                hour: 'HH:mm'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Alerts'
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
     * Update transaction volume chart
     */
    updateVolumeChart(historicalData = null) {
        if (!this.charts.transactionVolume) return;

        const chart = this.charts.transactionVolume;
        const dataToProcess = historicalData || this.monitoringData.transactions;

        // Clear existing data if historicalData is provided (for initial load)
        if (historicalData) {
            chart.data.labels = [];
            chart.data.datasets[0].data = [];
        }

        // Aggregate volume per minute for the processed data
        const aggregatedVolume = {};
        dataToProcess.forEach(t => {
            const transactionTime = new Date(t.timestamp);
            // Round down to the nearest minute for aggregation
            const minuteKey = new Date(transactionTime.getFullYear(), transactionTime.getMonth(), transactionTime.getDate(), transactionTime.getHours(), transactionTime.getMinutes(), 0, 0).getTime();
            
            if (!aggregatedVolume[minuteKey]) {
                aggregatedVolume[minuteKey] = 0;
            }
            aggregatedVolume[minuteKey] += t.amount;
        });

        // Sort and add aggregated data to chart
        Object.keys(aggregatedVolume).sort().forEach(minuteKey => {
            chart.data.labels.push(new Date(parseInt(minuteKey)));
            chart.data.datasets[0].data.push(aggregatedVolume[minuteKey]);
        });

        // Keep only last 20 data points (or all if less than 20)
        if (chart.data.labels.length > 20) {
            chart.data.labels = chart.data.labels.slice(-20);
            chart.data.datasets[0].data = chart.data.datasets[0].data.slice(-20);
        }

        chart.update('none');
    }

    /**
     * Update alert trends chart
     */
    updateAlertTrendsChart(historicalData = null) {
        if (!this.charts.alertTrends) return;

        const chart = this.charts.alertTrends;
        const dataToProcess = historicalData || this.monitoringData.alerts;

        // Clear existing data if historicalData is provided (for initial load)
        if (historicalData) {
            chart.data.labels = [];
            chart.data.datasets[0].data = [];
            chart.data.datasets[1].data = [];
        }

        // Aggregate alerts per minute for the processed data
        const aggregatedAlerts = {};
        dataToProcess.forEach(a => {
            const alertTime = new Date(a.timestamp);
            // Round down to the nearest minute for aggregation
            const minuteKey = new Date(alertTime.getFullYear(), alertTime.getMonth(), alertTime.getDate(), alertTime.getHours(), alertTime.getMinutes(), 0, 0).getTime();
            
            if (!aggregatedAlerts[minuteKey]) {
                aggregatedAlerts[minuteKey] = { total: 0, highRisk: 0 };
            }
            aggregatedAlerts[minuteKey].total++;
            if (a.risk_score >= 0.8) {
                aggregatedAlerts[minuteKey].highRisk++;
            }
        });

        // Sort and add aggregated data to chart
        Object.keys(aggregatedAlerts).sort().forEach(minuteKey => {
            chart.data.labels.push(new Date(parseInt(minuteKey)));
            chart.data.datasets[0].data.push(aggregatedAlerts[minuteKey].total);
            chart.data.datasets[1].data.push(aggregatedAlerts[minuteKey].highRisk);
        });

        // Keep only last 20 data points (or all if less than 20)
        if (chart.data.labels.length > 20) {
            chart.data.labels = chart.data.labels.slice(-20);
            chart.data.datasets[0].data = chart.data.datasets[0].data.slice(-20);
            chart.data.datasets[1].data = chart.data.datasets[1].data.slice(-20);
        }

        chart.update('none');
    }

    /**
     * Update risk distribution chart
     */
    updateRiskDistributionChart() {
        if (!this.charts.riskDistribution) return;

        const chart = this.charts.riskDistribution;
        const riskCounts = { low: 0, medium: 0, high: 0, critical: 0 };

        this.monitoringData.alerts.forEach(alert => {
            const riskLevel = this.getRiskLevel(alert.risk_score);
            riskCounts[riskLevel]++;
        });

        chart.data.datasets[0].data = [
            riskCounts.low,
            riskCounts.medium,
            riskCounts.high,
            riskCounts.critical
        ];
        chart.update('none');
    }

    /**
     * Update alert display
     */
    updateAlertDisplay(alert) {
        const alertListTableBody = document.querySelector('#alertList tbody');
        if (!alertListTableBody) return;

        // Remove the 'No alerts in queue' row if it exists
        const noAlertsRow = alertListTableBody.querySelector('.no-alerts-row');
        if (noAlertsRow) {
            noAlertsRow.remove();
        }

        const alertRow = document.createElement('tr');
        alertRow.className = `alert-item risk-${this.getRiskLevel(alert.risk_score)}`;
        alertRow.innerHTML = `
            <td>${alert.alert_type}</td>
            <td><span class="badge bg-${this.getRiskLevel(alert.risk_score)}">${(alert.risk_score * 100).toFixed(0)}%</span></td>
            <td>${this.maskCustomerId(alert.customer_id)}</td>
            <td>${alert.description}</td>
            <td>${new Date(alert.timestamp).toLocaleTimeString()}</td>
            <td>
                <button class="btn btn-sm btn-outline-secondary acknowledge-alert-btn" data-alert-id="${alert.id}">Acknowledge</button>
                <button class="btn btn-sm btn-primary investigate-alert-btn" data-alert-id="${alert.id}">Investigate</button>
            </td>
        `;

        alertListTableBody.insertBefore(alertRow, alertListTableBody.firstChild);

        // Keep only a certain number of alerts in the display
        const items = alertListTableBody.children;
        if (items.length > 10) { // Example: keep last 10 alerts
            alertListTableBody.removeChild(items[items.length - 1]);
        }
    }

    /**
     * Update ML metrics display
     */
    updateMLMetrics(prediction) {
        const mlMetricsContainer = document.getElementById('mlMetrics'); // Assuming a container for ML metrics
        if (!mlMetricsContainer) {
            console.warn('ML metrics element (id="mlMetrics") not found. UI will not be updated.');
            return;
        }

        // Example: Update a simple text display
        mlMetricsContainer.innerHTML = `
            <p>Latest ML Prediction: ${prediction.prediction} (Confidence: ${(prediction.confidence * 100).toFixed(1)}%)</p>
            <p>Transaction ID: ${prediction.transaction_id}</p>
        `;
    }

    /**
     * Update system metrics display
     */
    updateSystemMetricsDisplay(metrics) {
        const systemMetricsContainer = document.getElementById('systemMetrics'); // Assuming a container for system metrics
        if (!systemMetricsContainer) {
            console.warn('System metrics element (id="systemMetrics") not found. UI will not be updated.');
            return;
        }

        systemMetricsContainer.innerHTML = `
            <p>CPU Usage: ${metrics.cpu_usage}%</p>
            <p>Memory Usage: ${metrics.memory_usage}%</p>
            <p>Active Connections: ${metrics.active_connections}</p>
        `;
    }

    /**
     * Handle risk score update (if needed for specific UI elements)
     */
    handleRiskScoreUpdate(data) {
        console.log('Risk score update:', data);
        // Potentially update a specific transaction's displayed risk score
    }

    /**
     * Toggle monitoring (pause/resume)
     */
    toggleMonitoring() {
        const pauseBtn = document.getElementById('pauseMonitoring');
        if (!pauseBtn) return;

        if (this.isConnected) {
            this.websocket.close();
            pauseBtn.innerHTML = '<i class="fas fa-play"></i> Resume';
            pauseBtn.classList.remove('btn-outline-secondary');
            pauseBtn.classList.add('btn-success');
        } else {
            this.setupWebSocket();
            pauseBtn.innerHTML = '<i class="fas fa-pause"></i> Pause';
            pauseBtn.classList.remove('btn-success');
            pauseBtn.classList.add('btn-outline-secondary');
        }
    }

    /**
     * Clear transaction stream display
     */
    clearTransactionStream() {
        const streamContainer = document.getElementById('transactionStream');
        if (streamContainer) {
            streamContainer.innerHTML = '<p class="text-muted text-center mt-3">Waiting for real-time transactions...</p>';
            this.monitoringData.transactions = [];
            this.monitoringData.alerts = []; // Clear alerts too for a fresh start
            this.updateTransactionFlowChart(); // Reset charts
            this.updateVolumeChart();
            this.updateRiskDistributionChart();
            this.updateAlertTrendsChart();
        }
    }

    /**
     * Export real-time data
     */
    exportRealTimeData() {
        const dataToExport = {
            transactions: this.monitoringData.transactions,
            alerts: this.monitoringData.alerts,
            systemMetrics: this.monitoringData.systemMetrics
        };
        const jsonString = JSON.stringify(dataToExport, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `real-time-data-${new Date().toISOString()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        console.log('Real-time data exported.');
    }

    /**
     * Acknowledge an alert (client-side only for now)
     */
    acknowledgeAlert(alertId) {
        console.log(`Alert ${alertId} acknowledged.`);
        // In a real app, this would send an API call to update alert status in DB
        const alertElement = document.querySelector(`.alert-notification [data-alert-id="${alertId}"]`).closest('.alert-notification');
        if (alertElement) {
            alertElement.remove();
        }
    }

    /**
     * Start investigation for an alert (client-side only for now)
     */
    startInvestigation(alertId) {
        console.log(`Investigation started for alert ${alertId}.`);
        // In a real app, this would send an API call to create a case or update alert status
        const alertElement = document.querySelector(`.alert-notification [data-alert-id="${alertId}"]`).closest('.alert-notification');
        if (alertElement) {
            alertElement.remove();
        }
        // Redirect to case management or alert details page
        window.location.href = `/cases?alert_id=${alertId}`;
    }

    /**
     * Check if alert matches current filters
     */
    matchesAlertFilter(alert) {
        // Risk level filter
        if (this.filters.riskLevel !== 'all') {
            const riskLevel = this.getRiskLevel(alert.risk_score);
            if (riskLevel !== this.filters.riskLevel) return false;
        }

        // Alert type filter
        if (this.filters.alertType !== 'all') {
            // Assuming alert.alert_type contains values like 'AML_SUSPICIOUS_ACTIVITY', 'ML_ANOMALY', 'SANCTIONS_HIT'
            // Need to map these to 'fraud', 'aml', 'sanction'
            let matchesType = false;
            if (this.filters.alertType === 'fraud' && alert.alert_type.includes('FRAUD')) {
                matchesType = true;
            } else if (this.filters.alertType === 'aml' && alert.alert_type.includes('AML')) {
                matchesType = true;
            } else if (this.filters.alertType === 'sanction' && alert.alert_type.includes('SANCTIONS')) {
                matchesType = true;
            }
            if (!matchesType) return false;
        }

        // Time range filter (same as transaction filter)
        const now = new Date();
        const alertTime = new Date(alert.timestamp);
        const timeDiff = now.getTime() - alertTime.getTime();

        switch (this.filters.timeRange) {
            case '1h':
                if (timeDiff > 3600000) return false; // 1 hour
                break;
            case '4h':
                if (timeDiff > 14400000) return false; // 4 hours
                break;
            case '24h':
                if (timeDiff > 86400000) return false; // 24 hours
                break;
        }

        return true;
    }

    /**
     * Update filtered display (for both transactions and alerts)
     */
    updateFilteredDisplay(filteredTransactions, filteredAlerts) {
        const streamContainer = document.getElementById('transactionStream');
        if (streamContainer) {
            streamContainer.innerHTML = ''; // Clear current display
            if (filteredTransactions.length === 0) {
                streamContainer.innerHTML = '<p class="text-muted text-center mt-3">No transactions match the current filters.</p>';
            } else {
                filteredTransactions.forEach(transaction => {
                    this.updateTransactionStreamDisplay(transaction);
                });
            }
        }

        const alertListTableBody = document.querySelector('#alertList tbody');
        if (alertListTableBody) {
            alertListTableBody.innerHTML = ''; // Clear current display
            if (filteredAlerts.length === 0) {
                alertListTableBody.innerHTML = '<tr class="no-alerts-row"><td colspan="6" class="text-center text-muted mt-3">No alerts match the current filters.</td></tr>';
            } else {
                filteredAlerts.forEach(alert => {
                    this.updateAlertDisplay(alert);
                });
            }
        }
    }

    /**
     * Load initial data
     */
    async loadInitialData() {
        try {
            // Load recent transactions
            const transactionsResponse = await fetch('/api/monitoring/transactions/recent');
            if (transactionsResponse.ok) {
                const transactions = await transactionsResponse.json();
                this.monitoringData.transactions = transactions;
            }
            
            // Load recent alerts
            const alertsResponse = await fetch('/api/monitoring/alerts/recent');
            if (alertsResponse.ok) {
                const alerts = await alertsResponse.json();
                this.monitoringData.alerts = alerts;
                // Populate the alert list with initial alerts
                alerts.forEach(alert => this.updateAlertDisplay(alert));
            }
            
            // Initial chart updates
            this.updateRiskDistributionChart();
            this.updateAlertTrendsChart(this.monitoringData.alerts);
            this.updateVolumeChart(this.monitoringData.transactions);
            this.updateTransactionFlowChart(); // Ensure transaction flow chart is updated on initial load
            
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }
}

// Explicitly register the date-fns adapter with Chart.js


// Initialize real-time monitor when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.realTimeMonitor = new RealTimeMonitor();
});
