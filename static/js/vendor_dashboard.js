document.addEventListener('DOMContentLoaded', () => {
    const businessNameElem = document.getElementById('vendor-business-name');
    const businessAddressElem = document.getElementById('vendor-business-address');
    const totalPackagesElem = document.getElementById('stat-total-packages');
    const availablePackagesElem = document.getElementById('stat-available-packages');
    const dispatchedPackagesElem = document.getElementById('stat-dispatched-packages');
    const packagesTableBody = document.getElementById('vendor-packages-body');
    const alertBox = document.getElementById('alert-message');

    function showAlert(message, isSuccess = false) {
        if (!alertBox) return;
        alertBox.textContent = message;
        alertBox.className = `alert-box ${isSuccess ? 'alert-success' : 'alert-error'}`;
        alertBox.style.display = 'block';
    }

    async function loadVendorDashboard() {
        try {
            const response = await fetch('/api/vendor/dashboard-data');
            const data = await response.json();

            if (response.ok && data.success) {
                if (businessNameElem) businessNameElem.textContent = data.vendor.vendor_name || 'Vendor Dashboard';
                if (businessAddressElem) businessAddressElem.textContent = data.vendor.vendor_address || 'Not specified';
                
                if (totalPackagesElem) totalPackagesElem.textContent = data.stats.total_packages;
                if (availablePackagesElem) availablePackagesElem.textContent = data.stats.available_packages;
                if (dispatchedPackagesElem) dispatchedPackagesElem.textContent = data.stats.dispatched_packages;

                renderVendorPackages(data.packages || []);
            } else {
                showAlert(data.message || 'Failed to load vendor dashboard data.');
            }
        } catch (error) {
            console.error('Error fetching vendor dashboard data:', error);
            showAlert('Network error loading vendor dashboard.');
        }
    }

    function renderVendorPackages(packages) {
        if (!packagesTableBody) return;
        packagesTableBody.innerHTML = '';

        if (packages.length === 0) {
            packagesTableBody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; color: #64748b; padding: 1.5rem;">
                        No packages associated with your vendor account.
                    </td>
                </tr>
            `;
            return;
        }

        packages.forEach(pkg => {
            const tr = document.createElement('tr');

            let statusBadgeClass = 'badge-completed';
            if (pkg.STATUS === 'AVAILABLE') statusBadgeClass = 'badge-ongoing';
            if (pkg.STATUS === 'NOT AVAILABLE') statusBadgeClass = 'badge-pending';

            tr.innerHTML = `
                <td>#${pkg.PACKAGE_ID}</td>
                <td>${pkg.PRODUCT_ID}</td>
                <td>${pkg.CUSTOMER_NAME || 'N/A'}</td>
                <td>${pkg.CUSTOMER_EMAIL || 'N/A'}</td>
                <td>${pkg.WEIGHT} kg</td>
                <td>${pkg.PRIORITY}</td>
                <td><span class="status-badge ${statusBadgeClass}">${pkg.STATUS}</span></td>
            `;
            packagesTableBody.appendChild(tr);
        });
    }

    loadVendorDashboard();
});
