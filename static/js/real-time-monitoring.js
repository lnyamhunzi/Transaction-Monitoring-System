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
            this.addTransactionToTable(transaction);
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
        try {
            const audio = new Audio('/static/sounds/alert.mp3');
            audio.volume = 0.5;
            audio.play().catch(() => {
                // Fallback to system beep
                console.log('\u0007'); // ASCII bell character
            });
        } catch (error) {
            console.log('Could not play alert sound');
        }
    }
    
    /**
     * Update connection status
     */
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connectionStatus');
        if (!statusElement) return;
        
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
            }
            
            // Initial chart updates
            this.updateRiskDistributionChart();
            this.updateAlertTrendsChart();
            
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }
}

// Initialize real-time monitor when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.realTimeMonitor = new RealTimeMonitor();
});
