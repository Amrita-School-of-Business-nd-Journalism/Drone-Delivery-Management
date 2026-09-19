document.addEventListener('DOMContentLoaded', () => {
    const profileForm = document.getElementById('profile-form');
    const alertBox = document.getElementById('alert-message');
    const saveBtn = document.getElementById('save-btn');
    const deleteBtn = document.getElementById('delete-account-btn');
    const backDashboardBtn = document.getElementById('back-dashboard-btn');
    const vendorProfileFields = document.getElementById('vendor-profile-fields');
    let currentUserRole = '';

    function showAlert(message, isSuccess = false) {
        alertBox.textContent = message;
        alertBox.className = `alert-box ${isSuccess ? 'alert-success' : 'alert-error'}`;
        alertBox.style.display = 'block';
    }

    function hideAlert() {
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    }

    // Load User Profile
    async function loadProfile() {
        try {
            const response = await fetch('/api/profile');
            const data = await response.json();

            if (response.ok && data.success) {
                const user = data.user;
                currentUserRole = user.role;

                document.getElementById('first_name').value = user.first_name || '';
                document.getElementById('last_name').value = user.last_name || '';
                document.getElementById('email').value = user.email || '';
                document.getElementById('phone_no').value = user.phone_no || '';
                document.getElementById('role').value = user.role || '';
                document.getElementById('created_at').value = user.created_at || '';

                if (user.role === 'VENDOR') {
                    vendorProfileFields.style.display = 'block';
                    document.getElementById('vendor_name').value = user.vendor_name || '';
                    document.getElementById('vendor_address').value = user.vendor_address || '';
                    backDashboardBtn.href = '/vendor/dashboard';
                } else if (user.role === 'CUSTOMER') {
                    vendorProfileFields.style.display = 'none';
                    backDashboardBtn.href = '/customer/dashboard';
                } else {
                    vendorProfileFields.style.display = 'none';
                    backDashboardBtn.href = '/';
                }
            } else {
                showAlert(data.message || 'Failed to load profile.');
            }
        } catch (error) {
            console.error('Error fetching profile:', error);
            showAlert('Network error loading profile details.');
        }
    }

    // Handle Profile Update
    profileForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const firstName = document.getElementById('first_name').value.trim();
        const lastName = document.getElementById('last_name').value.trim();
        const phoneNo = document.getElementById('phone_no').value.trim();
        const vendorName = document.getElementById('vendor_name').value.trim();
        const vendorAddress = document.getElementById('vendor_address').value.trim();

        if (!firstName || !lastName || !phoneNo) {
            showAlert('First name, last name, and phone number are required.');
            return;
        }

        if (firstName.length > 25 || lastName.length > 25) {
            showAlert('First name and last name must not exceed 25 characters.');
            return;
        }

        const phoneRegex = /^[0-9]{10}$/;
        if (!phoneRegex.test(phoneNo)) {
            showAlert('Phone number must be exactly 10 digits.');
            return;
        }

        const payload = {
            first_name: firstName,
            last_name: lastName,
            phone_no: phoneNo
        };

        if (currentUserRole === 'VENDOR') {
            if (!vendorName) {
                showAlert('Vendor Business Name is required for vendor profile.');
                return;
            }
            if (vendorName.length > 50) {
                showAlert('Vendor Business Name must not exceed 50 characters.');
                return;
            }
            if (!vendorAddress) {
                showAlert('Vendor Address is required for vendor profile.');
                return;
            }
            if (vendorAddress.length > 100) {
                showAlert('Vendor Address must not exceed 100 characters.');
                return;
            }
            payload.vendor_name = vendorName;
            payload.vendor_address = vendorAddress;
        }

        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        try {
            const response = await fetch('/api/profile', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok && data.success) {
                showAlert(data.message || 'Profile updated successfully!', true);
            } else {
                showAlert(data.message || 'Failed to update profile.');
            }
        } catch (error) {
            console.error('Update profile error:', error);
            showAlert('Network error updating profile.');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Changes';
        }
    });

    // Handle Account Deletion
    deleteBtn.addEventListener('click', async () => {
        const confirmed = confirm('Are you sure you want to permanently delete your account? This action CANNOT be undone.');
        if (!confirmed) return;

        deleteBtn.disabled = true;
        deleteBtn.textContent = 'Deleting...';

        try {
            const response = await fetch('/api/profile', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (response.ok && data.success) {
                alert(data.message || 'Account deleted successfully.');
                window.location.href = data.redirect_url || '/';
            } else {
                showAlert(data.message || 'Failed to delete account.');
                deleteBtn.disabled = false;
                deleteBtn.textContent = 'Delete Account';
            }
        } catch (error) {
            console.error('Delete account error:', error);
            showAlert('Network error trying to delete account.');
            deleteBtn.disabled = false;
            deleteBtn.textContent = 'Delete Account';
        }
    });

    loadProfile();
});
