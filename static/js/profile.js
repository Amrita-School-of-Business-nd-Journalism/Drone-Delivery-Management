document.addEventListener('DOMContentLoaded', () => {
    const profileForm = document.getElementById('profile-form');
    const alertBox = document.getElementById('alert-message');
    const saveBtn = document.getElementById('save-btn');
    const deleteBtn = document.getElementById('delete-account-btn');
    const backDashboardBtn = document.getElementById('back-dashboard-btn');

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
                document.getElementById('first_name').value = user.first_name || '';
                document.getElementById('last_name').value = user.last_name || '';
                document.getElementById('email').value = user.email || '';
                document.getElementById('phone_no').value = user.phone_no || '';
                document.getElementById('role').value = user.role || '';
                document.getElementById('created_at').value = user.created_at || '';

                if (user.role === 'CUSTOMER') {
                    backDashboardBtn.href = '/customer/dashboard';
                } else if (user.role === 'VENDOR') {
                    backDashboardBtn.href = '/vendor/dashboard';
                } else {
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

        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        try {
            const response = await fetch('/api/profile', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    phone_no: phoneNo
                })
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
