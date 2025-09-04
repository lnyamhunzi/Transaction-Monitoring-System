/**
 * Authentication module
 */

function getAuthToken() {
    return new Promise((resolve, reject) => {
        const token = localStorage.getItem('admin_token');
        if (token) {
            resolve(token);
        } else {
            // Poll for the token to be set
            const interval = setInterval(() => {
                const token = localStorage.getItem('admin_token');
                if (token) {
                    clearInterval(interval);
                    resolve(token);
                }
            }, 100);
        }
    });
}
