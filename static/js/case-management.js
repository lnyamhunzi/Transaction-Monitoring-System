/**
 * Case Management JavaScript
 * Handles case listing, creation, updates, and related modals.
 */
class CaseManagement {
    constructor() {
        this.casesTable = null;
        this.currentCaseId = null;
        this.users = []; // To store users for assignment dropdowns
    }

    getAuthHeaders() {
        const token = localStorage.getItem('admin_token');
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
        this.setupDataTable();
        this.setupEventListeners();
        const headers = this.getAuthHeaders();
        if (!headers) {
            return;
        }
        await this.loadCases();
        await this.loadCaseMetrics(headers);
        this.initCaseDistributionChart(headers);
        await this.loadUsersForAssignment(headers);
    }
    
    setupDataTable() {
        // Check if the table element exists before initializing DataTable
        const casesTableElement = document.getElementById('casesTable');
        if (casesTableElement) {
            this.casesTable = $(casesTableElement).DataTable({
                pageLength: 25,
                responsive: true,
                order: [[0, 'desc']],
                columnDefs: [
                    {
                        targets: [7], // Actions column
                        orderable: false,
                        searchable: false
                    }
                ]
            });
        } else {
            console.warn('casesTable element not found. DataTable not initialized.');
        }
    }
    
    setupEventListeners() {
        // Filter change handlers
        const caseStatusFilter = document.getElementById('caseStatusFilter');
        if (caseStatusFilter) caseStatusFilter.addEventListener('change', () => this.applyFilters());
        
        const casePriorityFilter = document.getElementById('casePriorityFilter');
        if (casePriorityFilter) casePriorityFilter.addEventListener('change', () => this.applyFilters());
        
        const assigneeFilter = document.getElementById('assigneeFilter');
        if (assigneeFilter) assigneeFilter.addEventListener('change', () => this.applyFilters());
        
        const slaFilter = document.getElementById('slaFilter');
        if (slaFilter) slaFilter.addEventListener('change', () => this.applyFilters());
        
        // Button handlers
        const refreshCasesBtn = document.getElementById('refreshCases');
        if (refreshCasesBtn) refreshCasesBtn.addEventListener('click', () => this.loadCases());
        
        const exportCasesBtn = document.getElementById('exportCases');
        if (exportCasesBtn) exportCasesBtn.addEventListener('click', () => this.exportCases());
        
        const createCaseFromAlertBtn = document.getElementById('createCaseFromAlert');
        if (createCaseFromAlertBtn) createCaseFromAlertBtn.addEventListener('click', () => this.showCreateCaseModal(false));
        
        const createManualCaseBtn = document.getElementById('createManualCase');
        if (createManualCaseBtn) createManualCaseBtn.addEventListener('click', () => this.showCreateCaseModal(true));
        
        // Form handlers
        const createCaseForm = document.getElementById('createCaseForm');
        if (createCaseForm) createCaseForm.addEventListener('submit', (e) => this.handleCreateCase(e));
        
        const updateCaseForm = document.getElementById('updateCaseForm');
        if (updateCaseForm) updateCaseForm.addEventListener('submit', (e) => this.handleUpdateCase(e));
        
        const escalateCaseForm = document.getElementById('escalateCaseForm');
        if (escalateCaseForm) escalateCaseForm.addEventListener('submit', (e) => this.handleEscalateCase(e));
        
        const closeCaseForm = document.getElementById('closeCaseForm');
        if (closeCaseForm) closeCaseForm.addEventListener('submit', (e) => this.handleCloseCase(e));
        
        // Case type radio buttons
        document.querySelectorAll('input[name="case_type"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                const isManual = e.target.value === 'manual';
                const alertIdRow = document.getElementById('alertIdRow');
                const manualCaseFields = document.getElementById('manualCaseFields');
                const alertIdInput = document.querySelector('#createCaseForm [name="alert_id"]');
                const titleInput = document.querySelector('#createCaseForm [name="title"]');
                const descriptionInput = document.querySelector('#createCaseForm [name="description"]');

                if (alertIdRow) alertIdRow.style.display = isManual ? 'none' : 'flex';
                if (manualCaseFields) manualCaseFields.style.display = isManual ? 'block' : 'none';
                if (alertIdInput) alertIdInput.required = !isManual;
                if (titleInput) titleInput.required = isManual;
                if (descriptionInput) descriptionInput.required = isManual;
            });
        });

        // Dynamic event handlers
        document.addEventListener('click', (e) => {
            if (e.target.closest('.view-case-btn')) {
                const caseId = e.target.closest('.view-case-btn').dataset.caseId;
                console.log('View Case button clicked for caseId:', caseId);
                this.viewCaseDetails(caseId);
            }
            
            if (e.target.closest('.update-case-btn')) {
                const caseId = e.target.closest('.update-case-btn').dataset.caseId;
                console.log('Update Case button clicked for caseId:', caseId);
                this.showUpdateCaseModal(caseId);
            }
            
            if (e.target.closest('.close-case-btn')) {
                const caseId = e.target.closest('.close-case-btn').dataset.caseId;
                console.log('Close Case button clicked for caseId:', caseId);
                this.showCloseCaseModal(caseId);
            }

            if (e.target.closest('.escalate-case-btn')) {
                const caseId = e.target.closest('.escalate-case-btn').dataset.caseId;
                console.log('Escalate Case button clicked for caseId:', caseId);
                this.showEscalateCaseModal(caseId);
            }
        });

        // Buttons inside Case Details Modal
        const updateCaseDetailsBtn = document.getElementById('updateCaseBtn');
        if (updateCaseDetailsBtn) updateCaseDetailsBtn.addEventListener('click', () => this.showUpdateCaseModal(this.currentCaseId));

        const closeCaseDetailsBtn = document.getElementById('closeCaseBtn');
        if (closeCaseDetailsBtn) closeCaseDetailsBtn.addEventListener('click', () => this.showCloseCaseModal(this.currentCaseId));

        const escalateCaseDetailsBtn = document.getElementById('escalateCaseBtn');
        if (escalateCaseDetailsBtn) escalateCaseDetailsBtn.addEventListener('click', () => this.showEscalateCaseModal(this.currentCaseId));
    }
    
    async loadCases(queryString = '') {
        try {
            const url = `/api/cases/?limit=1000&${queryString}`;
            const response = await fetch(url, { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load cases');
            
            const cases = await response.json();
            this.updateCasesTable(cases);
            
        } catch (error) {
            console.error('Error loading cases:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Failed to load cases', 'danger');
            }
        }
    }
    
    updateCasesTable(cases) {
        if (!this.casesTable) {
            console.warn('DataTable not initialized, cannot update cases table.');
            return;
        }
        this.casesTable.clear();
        
        cases.forEach(caseData => {
            const slaStatus = this.calculateSLAStatus(caseData.target_completion_date);
            
            this.casesTable.row.add([
                `<div class="d-flex align-items-center">
                    <div class="me-3">
                        <div class="fw-semibold">${caseData.case_number}</div>
                        <small class="text-muted">${typeof AMLBase !== 'undefined' && AMLBase.formatDate ? AMLBase.formatDate(caseData.created_at) : caseData.created_at}</small>
                    </div>
                </div>`,
                `<span class="badge bg-warning">${caseData.alert?.alert_type || 'N/A'}</span>`,
                caseData.alert?.customer_id || 'N/A',
                `<span class="status-badge status-${caseData.priority.toLowerCase()}">${caseData.priority}</span>`,
                `<span class="status-badge status-${caseData.status.toLowerCase().replace('_', '-')}}">${caseData.status.replace('_', ' ')}</span>`,
                caseData.assigned_to || 'Unassigned',
                `<div class="sla-indicator sla-${slaStatus.class}">
                    <i class="fas fa-clock me-1"></i>${slaStatus.text}
                </div>`,
                `<div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary view-case-btn" data-case-id="${caseData.id}">
                        <i class="fas fa-eye" style="pointer-events: none;"></i>
                    </button>
                    <button class="btn btn-outline-secondary update-case-btn" data-case-id="${caseData.id}">
                        <i class="fas fa-edit" style="pointer-events: none;"></i>
                    </button>
                    <button class="btn btn-outline-success close-case-btn" data-case-id="${caseData.id}">
                        <i class="fas fa-check" style="pointer-events: none;"></i>
                    </button>
                    <button class="btn btn-outline-info escalate-case-btn" data-case-id="${caseData.id}">
                        <i class="fas fa-arrow-up" style="pointer-events: none;"></i>
                    </button>
                </div>`
            ]);
        });
        
        this.casesTable.draw();
    }
    
    calculateSLAStatus(targetDate) {
        if (!targetDate) return { class: 'unknown', text: 'No SLA' };
        
        const now = new Date();
        const target = new Date(targetDate);
        const diffHours = (target - now) / (1000 * 60 * 60);
        
        if (diffHours < 0) {
            return { class: 'overdue', text: 'Overdue' };
        } else if (diffHours < 24) {
            return { class: 'due-soon', text: 'Due Soon' };
        } else {
            return { class: 'on-track', text: 'On Track' };
        }
    }
    
    async loadCaseMetrics(headers) {
        try {
            const url = '/api/cases/metrics';
            console.log('Fetching case metrics from:', url);
            const response = await fetch(url, { headers: headers });
            console.log('Response status for case metrics:', response.status);
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to load metrics: ${response.status} - ${errorText}`);
            }
            
            const metrics = await response.json();
            console.log('Received case metrics:', metrics);
            
            const totalCasesElement = document.getElementById('totalCases');
            if (totalCasesElement) totalCasesElement.textContent = metrics.total_cases;
            
            const openCasesElement = document.getElementById('openCases');
            if (openCasesElement) openCasesElement.textContent = metrics.open_cases;
            
            const overdueCasesElement = document.getElementById('overdueCases');
            if (overdueCasesElement) overdueCasesElement.textContent = metrics.overdue_cases;
            
            const avgResolutionTimeElement = document.getElementById('avgResolutionTime');
            if (avgResolutionTimeElement) avgResolutionTimeElement.textContent = metrics.avg_resolution_days.toFixed(1);
            
        } catch (error) {
            console.error('Error loading case metrics:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Failed to load case metrics', 'danger');
            }
        }
    }
    
    async initCaseDistributionChart(headers) {
        const ctx = document.getElementById('caseDistributionChart');
        if (!ctx) return;

        try {
            const response = await fetch('/api/cases/distribution', { headers: headers });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) {
                const errorText = await response.text();
                console.error('API Error:', errorText);
                throw new Error(`Failed to load case distribution data: ${response.status} - ${errorText}`);
            }
            const data = await response.json();

            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.data,
                        backgroundColor: [
                            '#17a2b8', // Open
                            '#ffc107', // Investigating
                            '#fd7e14', // Pending Review
                            '#dc3545', // Escalated
                            '#28a745'  // Closed
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error loading case distribution chart:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Failed to load case distribution chart', 'danger');
            }
        }
    }
    
    async loadUsersForAssignment(headers) {
        try {
            const response = await fetch('/api/admin/users', { headers: headers });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load users');
            
            const users = await response.json();
            this.users = users;
            
            const createCaseAssignedTo = document.querySelector('#createCaseModal [name="assigned_to"]');
            const updateCaseAssignedTo = document.querySelector('#updateCaseModal [name="assigned_to"]');
            const escalateCaseAssignedTo = document.querySelector('#escalateCaseModal [name="escalated_to"]');

            // Clear existing options except the first one ("Select Assignee")
            if (createCaseAssignedTo) createCaseAssignedTo.innerHTML = '<option value="">Select Assignee</option>';
            if (updateCaseAssignedTo) updateCaseAssignedTo.innerHTML = '<option value="">Select Assignee</option>';
            if (escalateCaseAssignedTo) escalateCaseAssignedTo.innerHTML = '<option value="">Select User</option>';

            users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.username;
                option.textContent = user.full_name;
                if (createCaseAssignedTo) createCaseAssignedTo.appendChild(option.cloneNode(true));
                if (updateCaseAssignedTo) updateCaseAssignedTo.appendChild(option.cloneNode(true));
                if (escalateCaseAssignedTo) escalateCaseAssignedTo.appendChild(option.cloneNode(true));
            });
            
        } catch (error) {
            console.error('Error loading users for assignment:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Failed to load users for assignment', 'danger');
            }
        }
    }
    
    showCreateCaseModal(manual = false, alertId = null) {
        const createCaseModalElement = document.getElementById('createCaseModal');
        if (!createCaseModalElement) {
            console.error('Create Case Modal element not found.');
            return;
        }
        const modal = new bootstrap.Modal(createCaseModalElement);
        const form = document.getElementById('createCaseForm');
        if (form) form.reset();

        const caseTypeAlertRadio = document.getElementById('caseTypeAlert');
        const caseTypeManualRadio = document.getElementById('caseTypeManual');
        
        if (manual) {
            if (caseTypeManualRadio) caseTypeManualRadio.checked = true;
        } else {
            if (caseTypeAlertRadio) caseTypeAlertRadio.checked = true;
        }

        // Trigger change event to set initial state
        const event = new Event('change');
        if (manual && caseTypeManualRadio) caseTypeManualRadio.dispatchEvent(event);
        else if (!manual && caseTypeAlertRadio) caseTypeAlertRadio.dispatchEvent(event);

        if (alertId) {
            const alertIdInput = document.querySelector('#createCaseForm [name="alert_id"]');
            if (alertIdInput) alertIdInput.value = alertId;
        }

        modal.show();
    }
    
    async handleCreateCase(e) {
        e.preventDefault();
        
        try {
            const formData = new FormData(e.target);
            const caseData = Object.fromEntries(formData.entries());

            const headers = this.getAuthHeaders();
            if (!headers) return;

            const response = await fetch('/api/cases/', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(caseData)
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || 'Failed to create case');
            }
            
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Case created successfully', 'success');
            }
            
            const createCaseModalElement = document.getElementById('createCaseModal');
            if (createCaseModalElement) {
                const modalInstance = bootstrap.Modal.getInstance(createCaseModalElement);
                if (modalInstance) modalInstance.hide();
            }
            this.loadCases();
            this.loadCaseMetrics();
            
        } catch (error) {
            console.error('Error creating case:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast(error.message, 'danger');
            }
        }
    }
    
    async showUpdateCaseModal(caseId) {
        const updateCaseModalElement = document.getElementById('updateCaseModal');
        if (!updateCaseModalElement) {
            console.error('Update Case Modal element not found.');
            return;
        }
        const modal = new bootstrap.Modal(updateCaseModalElement);
        const form = document.getElementById('updateCaseForm');
        if (form) form.reset();

        this.viewCaseDetails(caseId).then(caseData => {
            if (caseData) {
                if (form) {
                    const statusInput = form.querySelector('[name="status"]');
                    if (statusInput) statusInput.value = caseData.status;
                    
                    const assignedToInput = form.querySelector('[name="assigned_to"]');
                    if (assignedToInput) assignedToInput.value = caseData.assigned_to || '';
                }
                
                this.currentCaseId = caseId;
                modal.show();
            } else {
                if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                    AMLBase.showToast('Failed to load case details for update. Case not found or an error occurred.', 'danger');
                }
            }
        }).catch(error => {
            console.error('Error fetching case details for update modal:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Error loading case details for update.', 'danger');
            }
        });
    }

    async showCloseCaseModal(caseId) {
        const closeCaseModalElement = document.getElementById('closeCaseModal');
        if (!closeCaseModalElement) {
            console.error('Close Case Modal element not found.');
            return;
        }
        const modal = new bootstrap.Modal(closeCaseModalElement);
        const form = document.getElementById('closeCaseForm');
        if (form) form.reset();

        this.currentCaseId = caseId;
        modal.show();
    }

    async handleCloseCase(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(`/api/cases/${this.currentCaseId}/close` , {
                method: 'PUT',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(data)
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to close case');

            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Case closed successfully', 'success');
            }
            const closeCaseModalElement = document.getElementById('closeCaseModal');
            if (closeCaseModalElement) {
                const modalInstance = bootstrap.Modal.getInstance(closeCaseModalElement);
                if (modalInstance) modalInstance.hide();
            }
            this.loadCases();
        } catch (error) {
            console.error('Error closing case:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Failed to close case', 'danger');
            }
        }
    }

    async showEscalateCaseModal(caseId) {
        const escalateCaseModalElement = document.getElementById('escalateCaseModal');
        if (!escalateCaseModalElement) {
            console.error('Escalate Case Modal element not found.');
            return;
        }
        const modal = new bootstrap.Modal(escalateCaseModalElement);
        const form = document.getElementById('escalateCaseForm');
        if (form) form.reset();

        const escalatedToSelect = form ? form.querySelector('[name="escalated_to"]') : null;
        if (escalatedToSelect) {
            escalatedToSelect.innerHTML = '<option value="">Select User</option>';
            if (this.users) {
                this.users.forEach(user => {
                    const option = document.createElement('option');
                    option.value = user.username;
                    option.textContent = user.full_name;
                    escalatedToSelect.appendChild(option);
                });
            }
        }

        this.currentCaseId = caseId;
        modal.show();
    }

    async handleEscalateCase(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(`/api/cases/${this.currentCaseId}/escalate` , {
                method: 'PUT',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(data)
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to escalate case');

            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Case escalated successfully', 'success');
            }
            const escalateCaseModalElement = document.getElementById('escalateCaseModal');
            if (escalateCaseModalElement) {
                const modalInstance = bootstrap.Modal.getInstance(escalateCaseModalElement);
                if (modalInstance) modalInstance.hide();
            }
            this.loadCases();
        } catch (error) {
            console.error('Error escalating case:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Failed to escalate case', 'danger');
            }
        }
    }
    
    async viewCaseDetails(caseId) {
        try {
            const response = await fetch(`/api/cases/${caseId}`, { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load case details');
            
            const caseData = await response.json();
            this.displayCaseDetails(caseData);
            
            const caseDetailsModalElement = document.getElementById('caseDetailsModal');
            if (caseDetailsModalElement) {
                const modal = new bootstrap.Modal(caseDetailsModalElement);
                modal.show();
            }
            return caseData;
            
        } catch (error) {
            console.error('Error loading case details:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Failed to load case details', 'danger');
            }
            return null;
        }
    }
    
    displayCaseDetails(caseData) {
        const content = document.getElementById('caseDetailsContent');
        if (!content) return;

        content.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Case Information</h6>
                    <table class="table table-sm">
                        <tr><td>Case Number</td><td>${caseData.case_number}</td></tr>
                        <tr><td>Status</td><td><span class="status-badge status-${caseData.status.toLowerCase()}">${caseData.status}</span></td></tr>
                        <tr><td>Priority</td><td><span class="status-badge status-${caseData.priority.toLowerCase()}">${caseData.priority}</span></td></tr>
                        <tr><td>Assigned To</td><td>${caseData.assigned_to || 'Unassigned'}</td></tr>
                        <tr><td>Created</td><td>${typeof AMLBase !== 'undefined' && AMLBase.formatDate ? AMLBase.formatDate(caseData.created_at) : caseData.created_at}</td></tr>
                        <tr><td>Target Completion</td><td>${caseData.target_completion_date ? (typeof AMLBase !== 'undefined' && AMLBase.formatDate ? AMLBase.formatDate(caseData.target_completion_date) : caseData.target_completion_date) : 'Not set'}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Alert Information</h6>
                    <table class="table table-sm">
                        <tr><td>Alert ID</td><td>${caseData.alert?.id || 'N/A'}</td></tr>
                        <tr><td>Alert Type</td><td>${caseData.alert?.alert_type || 'N/A'}</td></tr>
                        <tr><td>Risk Score</td><td>${caseData.alert?.risk_score ? (caseData.alert.risk_score * 100).toFixed(0) + '%' : 'N/A'}</td></tr>
                        <tr><td>Customer ID</td><td>${caseData.alert?.customer_id || 'N/A'}</td></tr>
                        <tr><td>Transaction ID</td><td>${caseData.alert?.transaction_id || 'N/A'}</td></tr>
                    </table>
                </div>
            </div>
            
            <div class="mt-4">
                <h6>Case Description</h6>
                <p>${caseData.description || 'No description provided'}</p>
            </div>
            
            <div class="mt-4">
                <h6>Investigation Notes</h6>
                <div class="bg-light p-3 rounded">
                    ${caseData.investigation_notes || 'No investigation notes yet'}
                </div>
            </div>
            
            <div class="mt-4">
                <h6>Case Activity Timeline</h6>
                <div id="caseTimeline">
                    ${this.generateCaseTimeline(caseData.activities || [])}
                </div>
            </div>
        `;
        
        this.currentCaseId = caseData.id;
    }
    
    generateCaseTimeline(activities) {
        if (!activities.length) {
            return '<p class="text-muted">No activity recorded</p>';
        }
        
        return activities.map(activity => `
            <div class="timeline-item">
                <div class="timeline-marker">
                    <i class="fas fa-circle"></i>
                </div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <strong>${activity.activity_type.replace('_', ' ')}</strong>
                        <span class="text-muted ms-2">${typeof AMLBase !== 'undefined' && AMLBase.formatDate ? AMLBase.formatDate(activity.performed_at) : activity.performed_at}</span>
                    </div>
                    <div class="timeline-body">
                        <p>${activity.description}</p>
                        <small class="text-muted">by ${activity.performed_by}</small>
                    </div>
                </div>
            </div>
        `).join('');
    }
    
    applyFilters() {
        const status = document.getElementById('caseStatusFilter')?.value;
        const priority = document.getElementById('casePriorityFilter')?.value;
        const assigned_to = document.getElementById('assigneeFilter')?.value;

        const params = new URLSearchParams();
        if (status) params.append('status', status);
        if (priority) params.append('priority', priority);
        if (assigned_to) params.append('assigned_to', assigned_to);

        this.loadCases(params.toString());
    }
    
    async exportCases() {
        try {
            const response = await fetch('/api/cases/export', { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to export cases');
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `cases_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Cases exported successfully', 'success');
            }
            
        } catch (error) {
            console.error('Error exporting cases:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Failed to export cases', 'danger');
            }
        }
    }

    async handleUpdateCase(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(`/api/cases/${this.currentCaseId}` , {
                method: 'PUT',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(data)
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to update case');

            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Case updated successfully', 'success');
            }
            const updateCaseModalElement = document.getElementById('updateCaseModal');
            if (updateCaseModalElement) {
                const modalInstance = bootstrap.Modal.getInstance(updateCaseModalElement);
                if (modalInstance) modalInstance.hide();
            }
            this.loadCases();
        } catch (error) {
            console.error('Error updating case:', error);
            if (typeof AMLBase !== 'undefined' && AMLBase.showToast) {
                AMLBase.showToast('Failed to update case', 'danger');
            }
        }
    }
}

// Initialize case management when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.caseManagement = new CaseManagement();
    window.caseManagement.init();
});
