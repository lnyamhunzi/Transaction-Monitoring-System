function getAuthToken(key = 'admin_token') {
    return localStorage.getItem(key);
}

// Centralized utility functions for AML application
const AMLBase = {
    getRiskLevel: function(score) {
        if (score >= 0.9) return 'critical';
        if (score >= 0.7) return 'high';
        if (score >= 0.4) return 'medium';
        return 'low';
    },
    formatCurrency: function(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    },
    showToast: function(message, type = 'info') {
        // This is a placeholder. In a real app, you'd use a toast library (e.g., Bootstrap Toast)
        console.log(`TOAST (${type.toUpperCase()}): ${message}`);
        const notificationContainer = document.getElementById('adminNotifications') || document.getElementById('notifications');
        if (notificationContainer) {
            const toast = document.createElement('div');
            toast.className = `alert alert-${type} alert-dismissible fade show`;
            toast.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;
            notificationContainer.appendChild(toast);
            setTimeout(() => toast.remove(), 5000);
        } else {
            alert(message); // Fallback if no container
        }
    }
};

// Make AMLBase globally accessible if needed, or export it
window.AMLBase = AMLBase;
