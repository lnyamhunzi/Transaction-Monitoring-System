document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(loginForm);
            const data = Object.fromEntries(formData.entries());
            
            const response = await fetch('/api/customer/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams(data)
            });

            if (response.ok) {
                const token = await response.json();
                localStorage.setItem('customer_token', token.access_token);
                window.location.href = '/portal/dashboard';
            } else {
                alert('Login failed');
            }
        });
    }

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('customer_token');
            window.location.href = '/portal/login';
        });
    }

    if (window.location.pathname === '/portal/dashboard') {
        loadDashboardData();
    }

    const paymentForm = document.getElementById('payment-form');
    if (paymentForm) {
        paymentForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(paymentForm);
            const data = Object.fromEntries(formData.entries());
            data.transaction_type = 'PAYMENT';
            await makeTransaction(data);
        });
    }

    const transferForm = document.getElementById('transfer-form');
    if (transferForm) {
        transferForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(transferForm);
            const data = Object.fromEntries(formData.entries());
            data.transaction_type = 'TRANSFER';
            await makeTransaction(data);
        });
    }
});

async function loadDashboardData() {
    const token = localStorage.getItem('customer_token');
    if (!token) {
        window.location.href = '/portal/login';
        return;
    }

    const headers = {
        'Authorization': `Bearer ${token}`
    };

    const [profileRes, transactionsRes] = await Promise.all([
        fetch('/api/customer/me', { headers }),
        fetch('/api/customer/me/transactions', { headers })
    ]);

    if (profileRes.ok) {
        const profile = await profileRes.json();
        document.getElementById('customer-name').textContent = profile.full_name;
        document.getElementById('customer-email').textContent = profile.email;
    }

    if (transactionsRes.ok) {
        const transactions = await transactionsRes.json();
        const tableBody = document.getElementById('transactions-table-body');
        tableBody.innerHTML = '';
        transactions.forEach(tx => {
            const row = `<tr>
                <td>${new Date(tx.created_at).toLocaleDateString()}</td>
                <td>${tx.transaction_type}</td>
                <td>${tx.amount}</td>
                <td>${tx.currency}</td>
                <td>${tx.reference}</td>
            </tr>`;
            tableBody.innerHTML += row;
        });
    }
}

async function makeTransaction(data) {
    const token = localStorage.getItem('customer_token');
    if (!token) {
        window.location.href = '/portal/login';
        return;
    }

    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };

    const profileRes = await fetch('/api/customer/me', { headers: {'Authorization': `Bearer ${token}`} });
    if(profileRes.ok) {
        const profile = await profileRes.json();
        data.customer_id = profile.customer_id;
    } else {
        alert('Could not get customer profile');
        return;
    }

    const response = await fetch('/api/customer/me/transactions', {
        method: 'POST',
        headers,
        body: JSON.stringify(data)
    });

    if (response.ok) {
        alert('Transaction successful!');
        window.location.href = '/portal/dashboard';
    } else {
        alert('Transaction failed');
    }
}
