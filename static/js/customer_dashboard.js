document.addEventListener('DOMContentLoaded', () => {
    const customerNameElem = document.getElementById('customer-name');
    const totalPackagesElem = document.getElementById('stat-total-packages');
    const ongoingDeliveriesElem = document.getElementById('stat-ongoing-deliveries');
    const completedDeliveriesElem = document.getElementById('stat-completed-deliveries');
    const recentTableBody = document.getElementById('recent-deliveries-body');
    const alertBox = document.getElementById('alert-message');

    function showAlert(message, isSuccess = false) {
        if (!alertBox) return;
        alertBox.textContent = message;
        alertBox.className = `alert-box ${isSuccess ? 'alert-success' : 'alert-error'}`;
        alertBox.style.display = 'block';
    }

    async function loadCustomerDashboard() {
        try {
            const response = await fetch('/api/customer/dashboard-data');
            const data = await response.json();

            if (response.ok && data.success) {
                if (customerNameElem) customerNameElem.textContent = data.first_name || 'Customer';
                if (totalPackagesElem) totalPackagesElem.textContent = data.stats.total_packages;
                if (ongoingDeliveriesElem) ongoingDeliveriesElem.textContent = data.stats.ongoing_deliveries;
                if (completedDeliveriesElem) completedDeliveriesElem.textContent = data.stats.completed_deliveries;

                renderRecentDeliveries(data.recent_deliveries || []);
            } else {
                showAlert(data.message || 'Failed to load dashboard data.');
            }
        } catch (error) {
            console.error('Error fetching customer dashboard data:', error);
            showAlert('Network error loading dashboard data.');
        }
    }

    function renderRecentDeliveries(deliveries) {
        if (!recentTableBody) return;
        recentTableBody.innerHTML = '';

        if (deliveries.length === 0) {
            recentTableBody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; color: #64748b; padding: 1.5rem;">
                        No recent deliveries found.
                    </td>
                </tr>
            `;
            return;
        }

        deliveries.forEach(item => {
            const tr = document.createElement('tr');
            
            let statusBadgeClass = 'badge-pending';
            if (item.MISSION_STATUS === 'ONGOING') statusBadgeClass = 'badge-ongoing';
            if (item.MISSION_STATUS === 'OVER') statusBadgeClass = 'badge-completed';

            const routeText = (item.SOURCE !== 'N/A' && item.DESTINATION !== 'N/A') 
                ? `${item.SOURCE} &rarr; ${item.DESTINATION}` 
                : 'Pending Assignment';

            tr.innerHTML = `
                <td>#${item.PACKAGE_ID}</td>
                <td>${item.VENDOR_NAME || 'N/A'}</td>
                <td>${item.WEIGHT} kg</td>
                <td>${routeText}</td>
                <td><span class="status-badge ${statusBadgeClass}">${item.MISSION_STATUS}</span></td>
                <td><button class="btn-sm btn-track" onclick="trackDelivery(${item.PACKAGE_ID})">Track</button></td>
            `;
            recentTableBody.appendChild(tr);
        });
    }

    async function loadPaymentHistory() {
        const paymentsBody = document.getElementById('payments-history-body');
        if (!paymentsBody) return;

        try {
            const response = await fetch('/api/customer/payments');
            const data = await response.json();

            paymentsBody.innerHTML = '';

            if (response.ok && data.success && data.payments && data.payments.length > 0) {
                data.payments.forEach(pay => {
                    const tr = document.createElement('tr');
                    let statusBadgeClass = 'badge-pending';
                    if (pay.STATUS === 'COMPLETED') statusBadgeClass = 'badge-completed';
                    if (pay.STATUS === 'FAILED') statusBadgeClass = 'badge-error';

                    tr.innerHTML = `
                        <td>#${pay.PAYMENT_ID}</td>
                        <td>#${pay.PACKAGE_ID}</td>
                        <td>#${pay.MISSION_ID}</td>
                        <td>${pay.VENDOR_NAME || 'N/A'}</td>
                        <td>${pay.SOURCE} &rarr; ${pay.DESTINATION}</td>
                        <td>${pay.TIMESTAMP}</td>
                        <td><strong>₹${pay.AMOUNT}</strong></td>
                        <td><span style="font-weight: 600;">${pay.MODE}</span></td>
                        <td><span class="status-badge ${statusBadgeClass}">${pay.STATUS}</span></td>
                    `;
                    paymentsBody.appendChild(tr);
                });
            } else {
                paymentsBody.innerHTML = `
                    <tr>
                        <td colspan="9" style="text-align: center; color: #64748b; padding: 1.5rem;">
                            No payment history recorded yet.
                        </td>
                    </tr>
                `;
            }
        } catch (err) {
            console.error('Error loading payments:', err);
            paymentsBody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align: center; color: #ef4444; padding: 1rem;">
                        Failed to load payment history.
                    </td>
                </tr>
            `;
        }
    }

    // Quick action handlers
    const btnNewDelivery = document.getElementById('action-new-delivery');
    const btnTrackDelivery = document.getElementById('action-track-delivery');

    if (btnNewDelivery) {
        btnNewDelivery.addEventListener('click', () => {
            window.location.href = '/customer/new-delivery';
        });
    }

    if (btnTrackDelivery) {
        btnTrackDelivery.addEventListener('click', () => {
            window.location.href = '/customer/track';
        });
    }

    loadCustomerDashboard();
    loadPaymentHistory();
});

function trackDelivery(packageId) {
    window.location.href = `/customer/track?package_id=${packageId}`;
}
