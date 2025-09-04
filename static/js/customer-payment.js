document.addEventListener('DOMContentLoaded', () => {
    const paymentForm = document.getElementById('paymentForm');
    const sourceAccountSelect = document.getElementById('source_account_number');

    // Function to fetch and populate customer accounts
    async function loadCustomerAccounts() {
        try {
            const response = await fetch('/api/customer/me'); // Assuming this endpoint returns customer details including accounts
            if (!response.ok) {
                if (response.status === 401) {
                    window.location.href = '/portal/login'; // Redirect to login if not authenticated
                    return;
                }
                throw new Error('Failed to load customer data');
            }
            const customerData = await response.json();
            
            // Assuming customerData has an 'accounts' array
            if (customerData.accounts && customerData.accounts.length > 0) {
                sourceAccountSelect.innerHTML = ''; // Clear loading message
                customerData.accounts.forEach(account => {
                    const option = document.createElement('option');
                    option.value = account.account_number;
                    option.textContent = `${account.account_number} (${account.currency} ${account.balance.toFixed(2)})`;
                    sourceAccountSelect.appendChild(option);
                });
            } else {
                sourceAccountSelect.innerHTML = '<option value="">No accounts found</option>';
            }
        } catch (error) {
            console.error('Error loading customer accounts:', error);
            alert('Failed to load your accounts. Please try again later.');
            sourceAccountSelect.innerHTML = '<option value="">Error loading accounts</option>';
        }
    }

    // Load accounts when the page loads
    loadCustomerAccounts();

    if (paymentForm) {
        paymentForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(paymentForm);
            const data = Object.fromEntries(formData.entries());

            // Convert amount to float
            data.amount = parseFloat(data.amount);

            try {
                const response = await fetch('/api/customer/make_payment', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    alert('Payment successful!');
                    paymentForm.reset(); // Clear form
                    loadCustomerAccounts(); // Refresh account balances
                } else {
                    const errorData = await response.json();
                    alert(`Payment failed: ${errorData.detail || response.statusText}`);
                }
            } catch (error) {
                console.error('Error during payment:', error);
                alert('An error occurred during payment.');
            }
        });
    }
});
