class AnalystPanel {
    constructor() {
        this.init();
    }

    getAuthHeaders() {
        const token = getAuthToken();
        if (!token) {
            window.location.href = '/admin/login';
            return null;
        }
        return {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }

    async init() {
        console.log('Initializing Analyst Panel...');
        await this.setupEventListeners();
        await this.loadRecentTransactions();
        await this.loadRecentAlerts();
        console.log('Analyst panel initialized successfully');
    }

    async setupEventListeners() {
        const createTransferBtn = document.getElementById('createTransfer');
        if (createTransferBtn) {
            createTransferBtn.addEventListener('click', () => {
                const transferModal = new bootstrap.Modal(document.getElementById('transferModal'));
                transferModal.show();
            });
        }

        const transferForm = document.getElementById('transferForm');
        if (transferForm) {
            transferForm.addEventListener('submit', (e) => this.handleTransferSubmit(e));
        }
    }

    async handleTransferSubmit(e) {
        e.preventDefault();
        const recipientAccount = document.getElementById('recipientAccount').value;
        const amount = document.getElementById('transferAmount').value;
        const currency = document.getElementById('transferCurrency').value;

        try {
            this.showLoading('Submitting transfer...');
            const headers = this.getAuthHeaders();
            if (!headers) return;

            const response = await fetch('/api/analyst/create_self_transaction', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    recipient_account: recipientAccount,
                    amount: parseFloat(amount),
                    currency: currency
                })
            });

            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to submit transfer');

            const result = await response.json();
            this.showSuccess(result.message);
            const transferModal = bootstrap.Modal.getInstance(document.getElementById('transferModal'));
            transferModal.hide();

            this.loadRecentTransactions();
            this.loadRecentAlerts();

        } catch (error) {
            console.error('Error submitting transfer:', error);
            this.showError('Failed to submit transfer');
        } finally {
            this.hideLoading();
        }
    }

    async loadRecentTransactions() {
        try {
            const response = await fetch('/api/monitoring/transactions/recent', { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load recent transactions');

            const transactions = await response.json();
            this.populateRecentTransactions(transactions);

        } catch (error) {
            console.error('Error loading recent transactions:', error);
            this.showError('Failed to load recent transactions');
        }
    }

    populateRecentTransactions(transactions) {
        const tableBody = document.querySelector('#recentTransactionsTable tbody');
        if (!tableBody) return;

        if ($.fn.DataTable.isDataTable('#recentTransactionsTable')) {
            $('#recentTransactionsTable').DataTable().destroy();
        }

        tableBody.innerHTML = '';

        transactions.forEach(t => {
            const row = `
                <tr>
                    <td>${t.id.substring(0, 8)}...</td>
                    <td>${t.customer_id.substring(0, 8)}...</td>
                    <td>${formatCurrency(t.amount, t.currency)}</td>
                    <td>${t.currency}</td>
                    <td>${t.transaction_type}</td>
                    <td>${t.channel}</td>
                    <td><span class="badge bg-${getRiskLevel(t.risk_score)}">${t.risk_score}</span></td>
                    <td><span class="status-badge status-${t.status.toLowerCase()}">${t.status}</span></td>
                    <td>${new Date(t.created_at).toLocaleString()}</td>
                    <td></td>
                </tr>
            `;
            tableBody.insertAdjacentHTML('beforeend', row);
        });

        $('#recentTransactionsTable').DataTable({
            pageLength: 10,
            responsive: true,
            order: [[8, 'desc']]
        });
    }

    async loadRecentAlerts() {
        try {
            const response = await fetch('/api/monitoring/alerts/recent', { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load recent alerts');

            const alerts = await response.json();
            this.populateRecentAlerts(alerts);

        } catch (error) {
            console.error('Error loading recent alerts:', error);
            this.showError('Failed to load recent alerts');
        }
    }

    populateRecentAlerts(alerts) {
        const tableBody = document.querySelector('#recentAlertsTable tbody');
        if (!tableBody) return;

        if ($.fn.DataTable.isDataTable('#recentAlertsTable')) {
            $('#recentAlertsTable').DataTable().destroy();
        }

        tableBody.innerHTML = '';

        alerts.forEach(a => {
            const row = `
                <tr>
                    <td>${a.id.substring(0, 8)}...</td>
                    <td>${a.alert_type}</td>
                    <td><span class="badge bg-${getRiskLevel(a.risk_score)}">${a.risk_score}</span></td>
                    <td>${a.status}</td>
                    <td>${a.description}</td>
                    <td>${new Date(a.created_at).toLocaleString()}</td>
                </tr>
            `;
            tableBody.insertAdjacentHTML('beforeend', row);
        });

        $('#recentAlertsTable').DataTable({
            pageLength: 10,
            responsive: true,
            order: [[5, 'desc']]
        });
    }

    showLoading(message = 'Loading...') {
        const loader = document.getElementById('loadingIndicator');
        if (loader) {
            loader.querySelector('span').textContent = message;
            loader.classList.remove('d-none');
        }
    }

    hideLoading() {
        const loader = document.getElementById('loadingIndicator');
        if (loader) {
            loader.classList.add('d-none');
        }
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'danger');
    }

    showInfo(message) {
        this.showNotification(message, 'info');
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.getElementById('notifications') || document.body;
        container.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AnalystPanel();
});
