// Staff Dashboard JavaScript
document.addEventListener('DOMContentLoaded', () => {
    const staffAlertsTableBody = document.querySelector('#staffAlertsTable tbody');
    const staffCasesTableBody = document.querySelector('#staffCasesTable tbody');
    const realtimeTransactionStream = document.getElementById('realtime-transaction-stream');
    const alertPriorityFilter = document.getElementById('alertPriorityFilter');
    const alertStatusFilter = document.getElementById('alertStatusFilter');
    const generateSarReportBtn = document.getElementById('generateSarReportBtn');

    let staffWebSocket;

    // Function to initialize WebSocket for real-time transactions
    function initStaffWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        staffWebSocket = new WebSocket(wsUrl);

        staffWebSocket.onopen = () => {
            console.log('Staff WebSocket connected');
            realtimeTransactionStream.innerHTML = '<p class="text-muted text-center">Connected to real-time stream...</p>';
        };

        staffWebSocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'transaction_stream') {
                message.data.forEach(transaction => {
                    const transactionElement = document.createElement('div');
                    transactionElement.className = `alert alert-info alert-sm`;
                    transactionElement.innerHTML = `
                        <strong>New Transaction:</strong> ${transaction.customer_id.substring(0, 8)}... | Amount: ${AMLBase.formatCurrency(transaction.amount, transaction.currency)} | Channel: ${transaction.channel} | Risk: <span class="badge bg-${AMLBase.getRiskLevel(transaction.risk_score)}">${transaction.risk_score}</span>
                    `;
                    realtimeTransactionStream.prepend(transactionElement);
                    // Keep only a certain number of transactions
                    while (realtimeTransactionStream.children.length > 20) {
                        realtimeTransactionStream.removeChild(realtimeTransactionStream.lastChild);
                    }
                });
            } else if (message.type === 'alert_generated') {
                // Refresh alerts when a new one is generated
                loadRecentAlerts();
            }
        };

        staffWebSocket.onclose = () => {
            console.log('Staff WebSocket disconnected. Attempting to reconnect...');
            realtimeTransactionStream.innerHTML = '<p class="text-danger text-center">Disconnected from real-time stream. Reconnecting...</p>';
            setTimeout(initStaffWebSocket, 3000); // Attempt to reconnect after 3 seconds
        };

        staffWebSocket.onerror = (error) => {
            console.error('Staff WebSocket error:', error);
            AMLBase.showToast('Real-time connection error.', 'danger');
        };
    }

    // Function to load recent alerts for staff dashboard
    async function loadRecentAlerts() {
        try {
            const token = getAuthToken('staff_token'); // Get staff token
            if (!token) { window.location.href = '/staff/login'; return; }

            const priority = alertPriorityFilter.value;
            const status = alertStatusFilter.value;

            let url = '/api/alerts/?limit=20';
            if (priority !== 'all') url += `&priority=${priority}`;
            if (status !== 'all') url += `&status=${status}`;

            const response = await fetch(url, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.status === 401) { window.location.href = '/staff/login'; return; }
            if (!response.ok) throw new Error('Failed to load recent alerts');

            const alerts = await response.json();
            staffAlertsTableBody.innerHTML = ''; // Clear existing alerts

            if (alerts.length === 0) {
                staffAlertsTableBody.innerHTML = '<tr><td colspan="7" class="text-center">No recent alerts found.</td></tr>';
                return;
            }

            alerts.forEach(alert => {
                const row = `
                    <tr>
                        <td>${alert.id.substring(0, 8)}...</td>
                        <td>${alert.alert_type}</td>
                        <td><span class="badge bg-${AMLBase.getRiskLevel(alert.risk_score)}">${alert.risk_score}</span></td>
                        <td>${alert.status}</td>
                        <td>${alert.description}</td>
                        <td>${new Date(alert.created_at).toLocaleString()}</td>
                        <td>
                            <button class="btn btn-sm btn-info view-alert-btn" data-alert-id="${alert.id}">View</button>
                            <button class="btn btn-sm btn-primary create-case-btn" data-alert-id="${alert.id}">Create Case</button>
                        </td>
                    </tr>
                `;
                staffAlertsTableBody.insertAdjacentHTML('beforeend', row);
            });

        } catch (error) {
            console.error('Error loading recent alerts:', error);
            staffAlertsTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Failed to load alerts.</td></tr>';
        }
    }

    // Function to load recent cases for staff dashboard
    async function loadRecentCases() {
        try {
            const token = getAuthToken('staff_token');
            if (!token) { window.location.href = '/staff/login'; return; }

            const response = await fetch('/api/cases/?limit=10', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.status === 401) { window.location.href = '/staff/login'; return; }
            if (!response.ok) throw new Error('Failed to load recent cases');

            const cases = await response.json();
            staffCasesTableBody.innerHTML = ''; // Clear existing cases

            if (cases.length === 0) {
                staffCasesTableBody.innerHTML = '<tr><td colspan="7" class="text-center">No recent cases found.</td></tr>';
                return;
            }

            cases.forEach(caseItem => {
                const row = `
                    <tr>
                        <td>${caseItem.case_number}</td>
                        <td>${caseItem.title}</td>
                        <td>${caseItem.status}</td>
                        <td>${caseItem.priority}</td>
                        <td>${caseItem.assigned_to || 'Unassigned'}</td>
                        <td>${new Date(caseItem.created_at).toLocaleString()}</td>
                        <td>
                            <button class="btn btn-sm btn-info view-case-btn" data-case-id="${caseItem.id}">View</button>
                        </td>
                    </tr>
                `;
                staffCasesTableBody.insertAdjacentHTML('beforeend', row);
            });

        } catch (error) {
            console.error('Error loading recent cases:', error);
            staffCasesTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Failed to load cases.</td></tr>';
        }
    }

    // Handle SAR Report Generation
    generateSarReportBtn.addEventListener('click', async () => {
        try {
            AMLBase.showToast('Generating SAR Report...', 'info');
            const token = getAuthToken('staff_token');
            if (!token) { window.location.href = '/staff/login'; return; }

            // For simplicity, generate SAR for last 30 days of high-risk alerts
            const endDate = new Date().toISOString().split('T')[0];
            const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

            const response = await fetch('/api/reports/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    report_type: 'SAR',
                    start_date: startDate,
                    end_date: endDate,
                    risk_level: 'high' // Only high-risk alerts for SAR
                })
            });

            if (response.status === 401) { window.location.href = '/staff/login'; return; }
            if (!response.ok) throw new Error('Failed to generate SAR report.');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `SAR_Report_${startDate}_to_${endDate}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            AMLBase.showToast('SAR Report generated and downloaded.', 'success');

        } catch (error) {
            console.error('Error generating SAR report:', error);
            AMLBase.showToast(`Failed to generate SAR report: ${error.message}`, 'danger');
        }
    });

    // Event listeners for alert filters
    alertPriorityFilter.addEventListener('change', loadRecentAlerts);
    alertStatusFilter.addEventListener('change', loadRecentAlerts);

    // Initial loads
    initStaffWebSocket();
    loadRecentAlerts();
    loadRecentCases();

    // Logout functionality
    const staffLogoutButton = document.getElementById('logout-button');
    if (staffLogoutButton) {
        staffLogoutButton.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/staff/logout', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                if (response.ok) {
                    localStorage.removeItem('staff_token');
                    window.location.href = '/staff/login';
                } else {
                    console.error('Logout failed');
                }
            } catch (error) {
                console.error('Error during logout:', error);
            }
        });
    }
});