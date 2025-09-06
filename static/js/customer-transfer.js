document.addEventListener('DOMContentLoaded', () => {
    const transferForm = document.getElementById('transferForm');
    const sourceAccountSelect = document.getElementById('source_account_number');
    const destinationAccountSelect = document.getElementById('destination_account_number');

    // Function to fetch and populate customer accounts
    async function loadCustomerAccounts() {
        try {
            const response = await fetch('/api/customer/me');
            if (!response.ok) {
                if (response.status === 401) {
                    window.location.href = '/portal/login';
                    return;
                }
                throw new Error('Failed to load customer data');
            }
            const customerData = await response.json();
            
            if (customerData.accounts && customerData.accounts.length > 0) {
                sourceAccountSelect.innerHTML = '';
                destinationAccountSelect.innerHTML = '';
                customerData.accounts.forEach(account => {
                    const option1 = document.createElement('option');
                    option1.value = account.account_number;
                    option1.textContent = `${account.account_number} (${account.currency} ${account.balance.toFixed(2)})`;
                    sourceAccountSelect.appendChild(option1);

                    const option2 = document.createElement('option');
                    option2.value = account.account_number;
                    option2.textContent = `${account.account_number} (${account.currency} ${account.balance.toFixed(2)})`;
                    destinationAccountSelect.appendChild(option2);
                });
            } else {
                sourceAccountSelect.innerHTML = '<option value="">No accounts found</option>';
                destinationAccountSelect.innerHTML = '<option value="">No accounts found</option>';
            }
        } catch (error) {
            console.error('Error loading customer accounts:', error);
            alert('Failed to load your accounts. Please try again later.');
            sourceAccountSelect.innerHTML = '<option value="">Error loading accounts</option>';
            destinationAccountSelect.innerHTML = '<option value="">Error loading accounts</option>';
        }
    }

    // Load accounts when the page loads
    loadCustomerAccounts();

    if (transferForm) {
        transferForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(transferForm);
            const data = Object.fromEntries(formData.entries());

            if (data.source_account_number === data.destination_account_number) {
                alert('Source and destination accounts cannot be the same.');
                return;
            }

            data.amount = parseFloat(data.amount);

            try {
                const response = await fetch('/api/customer/make_transfer', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data),
                });

                if (response.ok) {
                    alert('Transfer successful!');
                    transferForm.reset();
                    loadCustomerAccounts();
                } else {
                    const errorData = await response.json();
                    alert(`Transfer failed: ${errorData.detail || response.statusText}`);
                }
            } catch (error) {
                console.error('Error during transfer:', error);
                alert('An error occurred during transfer.');
            }
        });
    }
});
