document.addEventListener('DOMContentLoaded', () => {
    const registerForm = document.getElementById('register-form');
    const alertBox = document.getElementById('alert-message');
    const submitBtn = document.getElementById('submit-btn');
    const roleSelect = document.getElementById('role');
    const vendorFields = document.getElementById('vendor-fields');

    function toggleVendorFields() {
        if (roleSelect.value === 'VENDOR') {
            vendorFields.style.display = 'block';
        } else {
            vendorFields.style.display = 'none';
        }
    }

    roleSelect.addEventListener('change', toggleVendorFields);
    toggleVendorFields();

    function showAlert(message, isSuccess = false) {
        alertBox.textContent = message;
        alertBox.className = `alert-box ${isSuccess ? 'alert-success' : 'alert-error'}`;
        alertBox.style.display = 'block';
    }

    function hideAlert() {
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    }

    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const role = roleSelect.value;
        const firstName = document.getElementById('first_name').value.trim();
        const lastName = document.getElementById('last_name').value.trim();
        const email = document.getElementById('email').value.trim();
        const phoneNo = document.getElementById('phone_no').value.trim();
        const password = document.getElementById('password').value;
        const vendorName = document.getElementById('vendor_name').value.trim();
        const vendorAddress = document.getElementById('vendor_address').value.trim();

        // Client-side validations
        if (!firstName || !lastName || !email || !phoneNo || !password || !role) {
            showAlert('Please fill in all required user fields.');
            return;
        }

        if (firstName.length > 25 || lastName.length > 25) {
            showAlert('First name and Last name must not exceed 25 characters.');
            return;
        }

        const emailRegex = /^[A-Za-z0-9_]+@[A-Za-z]+\.[A-Za-z]{2,}$/;
        if (!emailRegex.test(email) || email.length > 50) {
            showAlert('Please enter a valid email address (max 50 characters).');
            return;
        }

        const phoneRegex = /^[0-9]{10}$/;
        if (!phoneRegex.test(phoneNo)) {
            showAlert('Phone number must contain exactly 10 digits.');
            return;
        }

        if (password.length < 6) {
            showAlert('Password must be at least 6 characters long.');
            return;
        }

        if (role !== 'CUSTOMER' && role !== 'VENDOR') {
            showAlert('Invalid account role selected.');
            return;
        }

        // Vendor-specific validations
        if (role === 'VENDOR') {
            if (!vendorName) {
                showAlert('Vendor Business Name is required for vendor registration.');
                return;
            }
            if (vendorName.length > 50) {
                showAlert('Vendor Business Name must not exceed 50 characters.');
                return;
            }
            if (!vendorAddress) {
                showAlert('Vendor Address is required for vendor registration.');
                return;
            }
            if (vendorAddress.length > 100) {
                showAlert('Vendor Address must not exceed 100 characters.');
                return;
            }
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Registering...';

        const payload = {
            first_name: firstName,
            last_name: lastName,
            email: email,
            phone_no: phoneNo,
            password: password,
            role: role
        };

        if (role === 'VENDOR') {
            payload.vendor_name = vendorName;
            payload.vendor_address = vendorAddress;
        }

        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok && data.success) {
                showAlert(data.message || 'Registration successful!', true);
                registerForm.reset();
                toggleVendorFields();
            } else {
                showAlert(data.message || 'Registration failed. Please check your details.');
            }
        } catch (error) {
            console.error('Registration fetch error:', error);
            showAlert('Network error. Unable to process registration.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Register';
        }
    });
});
