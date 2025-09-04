document.addEventListener('DOMContentLoaded', () => {
    const registrationForm = document.getElementById('registrationForm');
    if (registrationForm) {
        registrationForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(registrationForm);
            const data = Object.fromEntries(formData.entries());

            if (data.password !== data.confirm_password) {
                alert('Passwords do not match!');
                return;
            }
            delete data.confirm_password; // Don't send confirm_password to server

            try {
                const response = await fetch('/api/customer/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams(data).toString(),
                });

                if (response.ok) {
                    alert('Registration successful! Please log in.');
                    window.location.href = '/portal/login';
                } else {
                    const errorData = await response.json();
                    alert(`Registration failed: ${errorData.detail || response.statusText}`);
                }
            } catch (error) {
                console.error('Error during registration:', error);
                alert('An error occurred during registration.');
            }
        });
    }

    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(loginForm);
            const data = Object.fromEntries(formData.entries());

            try {
                const response = await fetch('/api/customer/token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams(data).toString(),
                });

                if (response.ok) {
                    // Token is set as a cookie by the backend, so just redirect
                    window.location.href = '/portal/dashboard';
                } else {
                    const errorData = await response.json();
                    alert(`Login failed: ${errorData.detail || response.statusText}`);
                }
            } catch (error) {
                console.error('Error during login:', error);
                alert('An error occurred during login.');
            }
        });
    }
});
