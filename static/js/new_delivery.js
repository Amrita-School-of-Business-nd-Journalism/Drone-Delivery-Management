document.addEventListener('DOMContentLoaded', () => {
    const vendorSelect = document.getElementById('vendor_id');
    const form = document.getElementById('new-delivery-form');
    const alertBox = document.getElementById('alert-message');
    const submitBtn = document.getElementById('submit-package-btn');

    function showAlert(message, isSuccess = false) {
        alertBox.textContent = message;
        alertBox.className = `alert-box ${isSuccess ? 'alert-success' : 'alert-error'}`;
        alertBox.style.display = 'block';
    }

    function hideAlert() {
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    }

    // Load Vendors dropdown
    async function loadVendors() {
        try {
            const response = await fetch('/api/vendors');
            const data = await response.json();

            vendorSelect.innerHTML = '';

            if (response.ok && data.success && data.vendors && data.vendors.length > 0) {
                const defaultOption = document.createElement('option');
                defaultOption.value = '';
                defaultOption.textContent = '-- Select a Vendor --';
                vendorSelect.appendChild(defaultOption);

                data.vendors.forEach(vendor => {
                    const option = document.createElement('option');
                    option.value = vendor.VENDOR_ID;
                    option.textContent = `${vendor.VENDOR_NAME} (ID: ${vendor.VENDOR_ID})`;
                    vendorSelect.appendChild(option);
                });
            } else {
                const noVendorOption = document.createElement('option');
                noVendorOption.value = '';
                noVendorOption.textContent = 'No vendors available in database.';
                vendorSelect.appendChild(noVendorOption);
                showAlert('No registered vendors found. A vendor must exist in database to create a package.');
            }
        } catch (error) {
            console.error('Error fetching vendors:', error);
            showAlert('Network error loading vendor list.');
        }
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const vendorIdVal = vendorSelect.value;
        const productIdVal = document.getElementById('product_id').value;
        const weightVal = document.getElementById('weight').value;
        const priorityVal = document.getElementById('priority').value;

        if (!vendorIdVal || !productIdVal || !weightVal || !priorityVal) {
            showAlert('Please complete all required form fields.');
            return;
        }

        const vendorId = parseInt(vendorIdVal, 10);
        const productId = parseInt(productIdVal, 10);
        const weight = parseInt(weightVal, 10);
        const priority = parseInt(priorityVal, 10);

        if (isNaN(vendorId) || vendorId <= 0) {
            showAlert('Please select a valid vendor.');
            return;
        }

        if (isNaN(productId) || productId <= 0) {
            showAlert('Product ID must be a positive integer.');
            return;
        }

        if (isNaN(weight) || weight <= 0) {
            showAlert('Weight must be a positive integer in kg.');
            return;
        }

        if (isNaN(priority) || priority < 1 || priority > 5) {
            showAlert('Priority must be between 1 and 5.');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating Request...';

        try {
            const response = await fetch('/api/customer/packages', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    vendor_id: vendorId,
                    product_id: productId,
                    weight: weight,
                    priority: priority
                })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                showAlert(`Package Delivery Request #${data.package_id} created successfully!`, true);
                form.reset();
            } else {
                showAlert(data.message || 'Failed to create delivery request.');
            }
        } catch (error) {
            console.error('Error creating package:', error);
            showAlert('Network error trying to create delivery request.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Delivery Request';
        }
    });

    loadVendors();
});
