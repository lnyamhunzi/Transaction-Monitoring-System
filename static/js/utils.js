function getAuthToken(key = 'admin_token') {
    return localStorage.getItem(key);
}

// Global utilities and base functionality
class AMLBase {
    static formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    }

    static formatDate(date) {
        return new Date(date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    static getRiskLevel(score) {
        if (score >= 0.9) return 'critical';
        if (score >= 0.7) return 'high';
        if (score >= 0.4) return 'medium';
        return 'low';
    }

    static showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        const container = document.getElementById('notifications');
        if (container) {
            container.appendChild(toast);
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
            toast.addEventListener('hidden.bs.toast', () => {
                container.removeChild(toast);
            });
        } else {
            console.warn('Notification container not found. Toast not displayed.');
        }
    }

    static updateLastUpdate() {
        const element = document.getElementById('lastUpdate');
        if (element) {
            element.textContent = new Date().toLocaleTimeString();
        }
    }
}

// Update last update time every minute
setInterval(() => {
    AMLBase.updateLastUpdate();
}, 60000);

// Initialize last update time
AMLBase.updateLastUpdate();

// Global error handler
window.addEventListener('error', (e) => {
    console.error('Global error:', e.error);
    AMLBase.showToast('An unexpected error occurred', 'danger');
});

// Make AMLBase globally available
window.AMLBase = AMLBase;