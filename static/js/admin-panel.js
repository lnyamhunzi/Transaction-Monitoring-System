/**
 * AML Admin Panel - Administrative Interface
 * System configuration, user management, and monitoring controls
 */

class AMLAdminPanel {
    constructor() {
        this.config = {
            refreshInterval: 60000, // 1 minute
            maxLogEntries: 1000
        };
        
        this.init();
    }

    getAuthHeaders() {
        const token = localStorage.getItem('admin_token');
        return {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }
    
    /**
     * Initialize admin panel
     */
    async init() {
        console.log('Initializing AML Admin Panel...');
        
        try {
            await this.loadSystemStatus();
            await this.loadSystemConfiguration();
            await this.loadUsers();
            await this.loadMLModelsStatus();
            await this.loadSanctionsLists();
            await this.setupEventListeners();
            await this.startSystemMonitoring();
            
            console.log('Admin panel initialized successfully');
        } catch (error) {
            console.error('Error initializing admin panel:', error);
            this.showError('Failed to initialize admin panel');
        }
    }
    
    /**
     * Load system status and metrics
     */
    async loadSystemStatus() {
        try {
            const response = await fetch('/api/admin/system-status', { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load system status');
            
            const status = await response.json();
            this.updateSystemStatus(status);
            
        } catch (error) {
            console.error('Error loading system status:', error);
            this.showError('Failed to load system status');
        }
    }
    
    /**
     * Update system status display
     */
    updateSystemStatus(status) {
        // Update system health indicators
        this.updateHealthIndicator('database', status.database_status);
        this.updateHealthIndicator('ml-engine', status.ml_engine_status);
        this.updateHealthIndicator('websocket', status.websocket_status);
        this.updateHealthIndicator('email-service', status.email_service_status);
        
        // Update system metrics
        this.updateMetric('cpu-usage', status.cpu_usage, '%');
        this.updateMetric('memory-usage', status.memory_usage, '%');
        this.updateMetric('disk-usage', status.disk_usage, '%');
        this.updateMetric('active-connections', status.active_connections);
        
        // Update processing stats
        this.updateMetric('transactions-processed', status.transactions_processed_today);
        this.updateMetric('alerts-generated', status.alerts_generated_today);
        this.updateMetric('cases-opened', status.cases_opened_today);
        this.updateMetric('ml-predictions', status.ml_predictions_today);
    }
    
    /**
     * Update health indicator
     */
    updateHealthIndicator(component, status) {
        const indicator = document.getElementById(`${component}-status`);
        if (!indicator) return;
        
        indicator.className = `health-indicator ${status.toLowerCase()}`;
        indicator.innerHTML = `
            <div class="status-dot status-${status.toLowerCase()}"></div>
            <span class="status-text">${status}</span>
        `;
    }
    
    /**
     * Update metric display
     */
    updateMetric(metricId, value, unit = '') {
        const element = document.getElementById(metricId);
        if (!element) return;
        
        const valueElement = element.querySelector('.metric-value');
        if (valueElement) {
            valueElement.textContent = value + unit;
        }
    }
    
    /**
     * Load system configuration
     */
    async loadSystemConfiguration() {
        try {
            const response = await fetch('/api/admin/configuration', { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load configuration');
            
            const config = await response.json();
            this.populateConfigurationForm(config);
            
        } catch (error) {
            console.error('Error loading configuration:', error);
            this.showError('Failed to load system configuration');
        }
    }
    
    /**
     * Populate configuration form
     */
    populateConfigurationForm(config) {
        // Risk thresholds
        this.setFormValue('risk-threshold-low', config.risk_threshold_low);
        this.setFormValue('risk-threshold-medium', config.risk_threshold_medium);
        this.setFormValue('risk-threshold-high', config.risk_threshold_high);
        
        // Alert settings
        this.setFormValue('email-notifications', config.email_notifications_enabled);
        this.setFormValue('sms-notifications', config.sms_notifications_enabled);
        this.setFormValue('alert-retention-days', config.alert_retention_days);
        
        // ML settings
        this.setFormValue('ml-enabled', config.ml_scoring_enabled);
        this.setFormValue('anomaly-threshold', config.anomaly_threshold);
        this.setFormValue('model-retrain-interval', config.model_retrain_interval_days);
        
        // Transaction limits
        Object.keys(config.transaction_limits || {}).forEach(currency => {
            const limits = config.transaction_limits[currency];
            this.setFormValue(`limit-${currency.toLowerCase()}-low`, limits.low_risk);
            this.setFormValue(`limit-${currency.toLowerCase()}-medium`, limits.medium_risk);
            this.setFormValue(`limit-${currency.toLowerCase()}-high`, limits.high_risk);
        });
    }
    
    /**
     * Set form field value
     */
    setFormValue(fieldId, value) {
        const field = document.getElementById(fieldId);
        if (!field) return;
        
        if (field.type === 'checkbox') {
            field.checked = value;
        } else {
            field.value = value;
        }
    }
    
    /**
     * Setup event listeners
     */
    async setupEventListeners() {
        // Configuration form submission
        const configForm = document.getElementById('configurationForm');
        if (configForm) {
            configForm.addEventListener('submit', (e) => this.handleConfigurationSubmit(e));
        }
        
        // User management buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('create-user-btn')) {
                this.showCreateUserModal();
            }
            
            if (e.target.classList.contains('edit-user-btn')) {
                const userId = e.target.dataset.userId;
                this.showEditUserModal(userId);
            }
            
            if (e.target.classList.contains('delete-user-btn')) {
                const userId = e.target.dataset.userId;
                this.confirmDeleteUser(userId);
            }
            
            if (e.target.classList.contains('view-audit-btn')) {
                const userId = e.target.dataset.userId;
                this.showUserAuditLog(userId);
            }
        });
        
        // System actions
        const restartBtn = document.getElementById('restartSystem');
        if (restartBtn) {
            restartBtn.addEventListener('click', () => this.confirmSystemRestart());
        }
        
        const backupBtn = document.getElementById('createBackup');
        if (backupBtn) {
            backupBtn.addEventListener('click', () => this.createSystemBackup());
        }
        
        const updateModelsBtn = document.getElementById('updateModels');
        if (updateModelsBtn) {
            updateModelsBtn.addEventListener('click', () => this.updateMLModels());
        }
        
        const exportLogsBtn = document.getElementById('exportLogs');
        if (exportLogsBtn) {
            exportLogsBtn.addEventListener('click', () => this.exportSystemLogs());
        }
        
        // Sanctions list management
        const updateSanctionsBtn = document.getElementById('updateSanctions');
        if (updateSanctionsBtn) {
            updateSanctionsBtn.addEventListener('click', () => this.updateSanctionsLists());
        }
        
        const uploadSanctionsBtn = document.getElementById('uploadSanctions');
        if (uploadSanctionsBtn) {
            uploadSanctionsBtn.addEventListener('click', () => this.showUploadSanctionsModal());
        }
    }
    
    /**
     * Handle configuration form submission
     */
    async handleConfigurationSubmit(e) {
        e.preventDefault();
        
        try {
            const formData = new FormData(e.target);
            const config = {};
            
            // Convert form data to configuration object
            for (let [key, value] of formData.entries()) {
                if (value === 'on') {
                    config[key] = true;
                } else if (value === 'off' || value === '') {
                    config[key] = false;
                } else if (!isNaN(value) && value !== '') {
                    config[key] = parseFloat(value);
                } else {
                    config[key] = value;
                }
            }
            
            const response = await fetch('/api/admin/configuration', {
                method: 'PUT',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(config)
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to update configuration');
            
            this.showSuccess('Configuration updated successfully');
            
        } catch (error) {
            console.error('Error updating configuration:', error);
            this.showError('Failed to update configuration');
        }
    }
    
    /**
     * Show create user modal
     */
    showCreateUserModal() {
        const modal = this.createUserModal();
        document.body.appendChild(modal);
        
        if (typeof bootstrap !== 'undefined') {
            new bootstrap.Modal(modal).show();
        }
    }
    
    /**
     * Create user management modal
     */
    createUserModal(userData = null) {
        const isEdit = userData !== null;
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${isEdit ? 'Edit' : 'Create'} User</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <form id="userForm">
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label">Username</label>
                                <input type="text" class="form-control" name="username" required 
                                       value="${userData?.username || ''}" ${isEdit ? 'readonly' : ''}>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Full Name</label>
                                <input type="text" class="form-control" name="full_name" required 
                                       value="${userData?.full_name || ''}">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Email</label>
                                <input type="email" class="form-control" name="email" required 
                                       value="${userData?.email || ''}">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Role</label>
                                <select class="form-control" name="role" required>
                                    <option value="compliance_officer" ${userData?.role === 'compliance_officer' ? 'selected' : ''}>Compliance Officer</option>
                                    <option value="aml_analyst" ${userData?.role === 'aml_analyst' ? 'selected' : ''}>AML Analyst</option>
                                    <option value="supervisor" ${userData?.role === 'supervisor' ? 'selected' : ''}>Supervisor</option>
                                    <option value="admin" ${userData?.role === 'admin' ? 'selected' : ''}>Administrator</option>
                                </select>
                            </div>
                            ${!isEdit ? `
                            <div class="mb-3">
                                <label class="form-label">Password</label>
                                <input type="password" class="form-control" name="password" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Confirm Password</label>
                                <input type="password" class="form-control" name="confirm_password" required>
                            </div>
                            ` : ''}
                            <div class="mb-3">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" name="is_active" 
                                           ${userData?.is_active !== false ? 'checked' : ''}>
                                    <label class="form-check-label">Active</label>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="submit" class="btn btn-primary">${isEdit ? 'Update' : 'Create'} User</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
        
        // Add form submission handler
        const form = modal.querySelector('#userForm');
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            if (isEdit) {
                this.updateUser(userData.id, new FormData(form));
            } else {
                this.createUser(new FormData(form));
            }
        });
        
        return modal;
    }
    
    /**
     * Create new user
     */
    async createUser(formData) {
        try {
            const userData = {};
            for (let [key, value] of formData.entries()) {
                userData[key] = value;
            }
            
            // Validate passwords match
            if (userData.password !== userData.confirm_password) {
                this.showError('Passwords do not match');
                return;
            }
            
            delete userData.confirm_password;
            
            const response = await fetch('/api/admin/users', {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(userData)
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to create user');
            
            this.showSuccess('User created successfully');
            this.loadUsers();
            
            // Close modal
            const modal = document.querySelector('.modal.show');
            if (modal && typeof bootstrap !== 'undefined') {
                bootstrap.Modal.getInstance(modal).hide();
            }
            
        } catch (error) {
            console.error('Error creating user:', error);
            this.showError('Failed to create user');
        }
    }

    /**
     * Load users
     */
    async loadUsers() {
        try {
            const response = await fetch('/api/admin/users', { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load users');
            
            const users = await response.json();
            this.populateUsersTable(users);
            
        } catch (error) {
            console.error('Error loading users:', error);
            this.showError('Failed to load users');
        }
    }

    /**
     * Populate users table
     */
    populateUsersTable(users) {
        const tableBody = document.querySelector('#usersTable tbody');
        if (!tableBody) return;

        // Destroy existing DataTable instance
        if ($.fn.DataTable.isDataTable('#usersTable')) {
            $('#usersTable').DataTable().destroy();
        }

        tableBody.innerHTML = '';

        users.forEach(user => {
            const row = `
                <tr>
                    <td>${user.username}</td>
                    <td>${user.full_name}</td>
                    <td>${user.email}</td>
                    <td><span class="badge bg-danger">${user.role}</span></td>
                    <td><span class="status-badge status-${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Active' : 'Inactive'}</span></td>
                    <td>${user.last_login ? new Date(user.last_login).toLocaleString() : 'N/A'}</td>
                    <td>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-primary edit-user-btn" data-user-id="${user.id}">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-outline-danger delete-user-btn" data-user-id="${user.id}">
                                <i class="fas fa-trash"></i>
                            </button>
                            <button class="btn btn-outline-info view-audit-btn" data-user-id="${user.id}">
                                <i class="fas fa-history"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
            tableBody.insertAdjacentHTML('beforeend', row);
        });

        // Re-initialize DataTable
        $('#usersTable').DataTable({
            pageLength: 25,
            responsive: true,
            order: [[0, 'asc']]
        });
    }

    /**
     * Show edit user modal
     */
    async showEditUserModal(userId) {
        try {
            const response = await fetch(`/api/admin/users/${userId}`, { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load user data');
            
            const userData = await response.json();
            const modal = this.createUserModal(userData);
            document.body.appendChild(modal);
            
            if (typeof bootstrap !== 'undefined') {
                new bootstrap.Modal(modal).show();
            }
            
        } catch (error) {
            console.error('Error loading user data:', error);
            this.showError('Failed to load user data');
        }
    }

    /**
     * Update user
     */
    async updateUser(userId, formData) {
        try {
            const userData = {};
            for (let [key, value] of formData.entries()) {
                userData[key] = value;
            }

            const response = await fetch(`/api/admin/users/${userId}`, {
                method: 'PUT',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(userData)
            });

            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to update user');

            this.showSuccess('User updated successfully');
            this.loadUsers();

            // Close modal
            const modal = document.querySelector('.modal.show');
            if (modal && typeof bootstrap !== 'undefined') {
                bootstrap.Modal.getInstance(modal).hide();
            }

        } catch (error) {
            console.error('Error updating user:', error);
            this.showError('Failed to update user');
        }
    }

    /**
     * Confirm delete user
     */
    confirmDeleteUser(userId) {
        if (confirm('Are you sure you want to delete this user?')) {
            this.deleteUser(userId);
        }
    }

    /**
     * Delete user
     */
    async deleteUser(userId) {
        try {
            const response = await fetch(`/api/admin/users/${userId}`, {
                method: 'DELETE',
                headers: this.getAuthHeaders()
            });

            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to delete user');

            this.showSuccess('User deleted successfully');
            this.loadUsers();

        } catch (error) {
            console.error('Error deleting user:', error);
            this.showError('Failed to delete user');
        }
    }

    /**
     * Show user audit log
     */
    async showUserAuditLog(userId) {
        try {
            const response = await fetch(`/api/admin/users/${userId}/audit`, { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load user audit log');
            
            const auditLog = await response.json();
            // Display the audit log in a modal or a dedicated view
            console.log(auditLog);
            this.showInfo('User audit log loaded. See console for details.');

        } catch (error) {
            console.error('Error loading user audit log:', error);
            this.showError('Failed to load user audit log');
        }
    }
    
    /**
     * Update ML models
     */
    async showUserAuditLog(userId) {
        try {
            const response = await fetch(`/api/admin/users/${userId}/audit`, { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load user audit log');
            
            const auditLog = await response.json();
            // Display the audit log in a modal or a dedicated view
            console.log(auditLog);
            this.showInfo('User audit log loaded. See console for details.');

        } catch (error) {
            console.error('Error loading user audit log:', error);
            this.showError('Failed to load user audit log');
        }
    }
    
    /**
     * Load ML models status
     */
    async loadMLModelsStatus() {
        try {
            const response = await fetch('/api/admin/ml-models', { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load ML models status');
            
            const models = await response.json();
            this.populateMLModels(models);
            
        } catch (error) {
            console.error('Error loading ML models status:', error);
            this.showError('Failed to load ML models status');
        }
    }

    /**
     * Populate ML models display
     */
    populateMLModels(models) {
        models.forEach(model => {
            const modelCard = document.getElementById(`${model.model_name.toLowerCase().replace(/ /g, '-')}-model-card`);
            if (modelCard) {
                modelCard.querySelector('.model-status .status-dot').className = `status-dot status-${model.is_active ? 'healthy' : 'inactive'}`;
                modelCard.querySelector('.model-status span').textContent = model.is_active ? 'Active' : 'Inactive';
                modelCard.querySelector('.model-info p:nth-child(1)').innerHTML = `<strong>Version:</strong> ${model.version}`;
                modelCard.querySelector('.model-info p:nth-child(2)').innerHTML = `<strong>Accuracy:</strong> ${model.accuracy ? (model.accuracy * 100).toFixed(1) + '%' : 'N/A'}`;
                modelCard.querySelector('.model-info p:nth-child(3)').innerHTML = `<strong>Last Trained:</strong> ${model.last_trained ? new Date(model.last_trained).toLocaleDateString() : 'N/A'}`;
                modelCard.querySelector('.model-info p:nth-child(4)').innerHTML = `<strong>Training Data:</strong> ${model.training_data_period || 'N/A'}`;
            }
        });
    }

    /**
     * Load sanctions lists summary
     */
    async loadSanctionsLists() {
        try {
            const response = await fetch('/api/admin/sanctions/lists', { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to load sanctions lists');
            
            const lists = await response.json();
            this.populateSanctionsLists(lists);
            
        } catch (error) {
            console.error('Error loading sanctions lists:', error);
            this.showError('Failed to load sanctions lists');
        }
    }

    /**
     * Populate sanctions lists display
     */
    populateSanctionsLists(lists) {
        lists.forEach(list => {
            const listCard = document.getElementById(`${list.list_name.toLowerCase().replace(/ /g, '-')}-list-card`);
            if (listCard) {
                listCard.querySelector('p:nth-child(1)').innerHTML = `<strong>Entries:</strong> ${list.entries.toLocaleString()}`;
                listCard.querySelector('p:nth-child(2)').innerHTML = `<strong>Last Updated:</strong> ${new Date(list.last_updated).toLocaleDateString()}`;
                listCard.querySelector('p:nth-child(3)').innerHTML = `<strong>Status:</strong> <span class="text-success">${list.status}</span>`;
            }
        });
    }

    /**
     * Update ML models
     */
    async updateMLModels() {
        try {
            this.showLoading('Updating ML models...');
            
            const response = await fetch('/api/admin/ml-models/retrain', {
                method: 'POST',
                headers: this.getAuthHeaders()
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to update ML models');
            
            const result = await response.json();
            this.showSuccess('ML models updated successfully');
            this.loadMLModelsStatus(); // Refresh status after update
            
        } catch (error) {
            console.error('Error updating ML models:', error);
            this.showError('Failed to update ML models');
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * Update sanctions lists
     */
    async updateSanctionsLists() {
        try {
            this.showLoading('Updating sanctions lists...');
            
            const response = await fetch('/api/admin/sanctions/update', {
                method: 'POST',
                headers: this.getAuthHeaders()
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to update sanctions lists');
            
            const result = await response.json();
            this.showSuccess(`Updated ${result.updated_entries} sanctions entries`);
            
        } catch (error) {
            console.error('Error updating sanctions lists:', error);
            this.showError('Failed to update sanctions lists');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Show upload sanctions modal
     */
    showUploadSanctionsModal() {
        const modal = this.createUploadSanctionsModal();
        document.body.appendChild(modal);
        
        if (typeof bootstrap !== 'undefined') {
            new bootstrap.Modal(modal).show();
        }
    }

    /**
     * Create upload sanctions modal
     */
    createUploadSanctionsModal() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Upload Sanctions List</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <form id="uploadSanctionsForm">
                        <div class="modal-body">
                            <div class="mb-3">
                                <label for="sanctionsFile" class="form-label">Select file</label>
                                <input class="form-control" type="file" id="sanctionsFile" name="file" accept=".csv,.json">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="submit" class="btn btn-primary">Upload</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        const form = modal.querySelector('#uploadSanctionsForm');
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const fileInput = modal.querySelector('#sanctionsFile');
            if (fileInput.files.length > 0) {
                this.uploadSanctionsList(fileInput.files[0]);
            }
        });

        return modal;
    }

    /**
     * Upload sanctions list
     */
    async uploadSanctionsList(file) {
        try {
            this.showLoading('Uploading sanctions list...');
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/admin/sanctions/upload', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('admin_token')}` },
                body: formData
            });

            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to upload sanctions list');

            const result = await response.json();
            this.showSuccess(result.message);

            // Close modal
            const modal = document.querySelector('.modal.show');
            if (modal && typeof bootstrap !== 'undefined') {
                bootstrap.Modal.getInstance(modal).hide();
            }

        } catch (error) {
            console.error('Error uploading sanctions list:', error);
            this.showError('Failed to upload sanctions list');
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * Create system backup
     */
    async createSystemBackup() {
        try {
            this.showLoading('Creating system backup...');
            
            const response = await fetch('/api/admin/backup', {
                method: 'POST',
                headers: this.getAuthHeaders()
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to create backup');
            
            // Download the backup file
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `aml_backup_${new Date().toISOString().split('T')[0]}.sql`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showSuccess('System backup created successfully');
            
        } catch (error) {
            console.error('Error creating backup:', error);
            this.showError('Failed to create system backup');
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * Export system logs
     */
    async exportSystemLogs() {
        try {
            const response = await fetch('/api/admin/logs/export', { headers: this.getAuthHeaders() });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to export logs');
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `system_logs_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showSuccess('System logs exported successfully');
            
        } catch (error) {
            console.error('Error exporting logs:', error);
            this.showError('Failed to export system logs');
        }
    }

    /**
     * Confirm system restart
     */
    confirmSystemRestart() {
        if (confirm('Are you sure you want to restart the system?')) {
            this.restartSystem();
        }
    }

    /**
     * Restart system
     */
    async restartSystem() {
        try {
            this.showLoading('Restarting system...');
            
            const response = await fetch('/api/admin/system/restart', {
                method: 'POST',
                headers: this.getAuthHeaders()
            });
            if (response.status === 401) { window.location.href = '/admin/login'; return; }
            if (!response.ok) throw new Error('Failed to restart system');
            
            this.showSuccess('System is restarting...');
            
        } catch (error) {
            console.error('Error restarting system:', error);
            this.showError('Failed to restart system');
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * Start system monitoring
     */
    startSystemMonitoring() {
        setInterval(() => {
            this.loadSystemStatus();
        }, this.config.refreshInterval);
    }
    
    /**
     * Show loading state
     */
    showLoading(message = 'Loading...') {
        const loader = document.getElementById('adminLoader');
        if (loader) {
            loader.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                    <span>${message}</span>
                </div>
            `;
            loader.style.display = 'block';
        }
    }
    
    /**
     * Hide loading state
     */
    hideLoading() {
        const loader = document.getElementById('adminLoader');
        if (loader) {
            loader.style.display = 'none';
        }
    }
    
    /**
     * Show success message
     */
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    /**
     * Show error message
     */
    showError(message) {
        this.showNotification(message, 'danger');
    }

    /**
     * Show info message
     */
    showInfo(message) {
        this.showNotification(message, 'info');
    }
    
    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.getElementById('adminNotifications') || document.body;
        container.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
}

// Initialize admin panel when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.amlAdminPanel = new AMLAdminPanel();
});