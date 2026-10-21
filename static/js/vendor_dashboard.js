document.addEventListener('DOMContentLoaded', () => {
    // Top-level Dashboard Elements
    const businessNameElem = document.getElementById('vendor-business-name');
    const businessAddressElem = document.getElementById('vendor-business-address');
    const totalPackagesElem = document.getElementById('stat-total-packages');
    const availablePackagesElem = document.getElementById('stat-available-packages');
    const dispatchedPackagesElem = document.getElementById('stat-dispatched-packages');
    const packagesTableBody = document.getElementById('vendor-packages-body');
    const alertBox = document.getElementById('alert-message');

    // Drones Elements
    const dronesTableBody = document.getElementById('drones-table-body');
    const registerDroneForm = document.getElementById('register-drone-form');
    const btnRegisterDrone = document.getElementById('btn-register-drone');

    // Pilots Elements
    const pilotsTableBody = document.getElementById('pilots-table-body');
    const registerPilotForm = document.getElementById('register-pilot-form');
    const btnRegisterPilot = document.getElementById('btn-register-pilot');

    // Routes Elements
    const routesTableBody = document.getElementById('routes-table-body');
    const registerRouteForm = document.getElementById('register-route-form');
    const btnRegisterRoute = document.getElementById('btn-register-route');

    function showAlert(message, isSuccess = false) {
        if (!alertBox) return;
        alertBox.textContent = message;
        alertBox.className = `alert-box ${isSuccess ? 'alert-success' : 'alert-error'}`;
        alertBox.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function hideAlert() {
        if (!alertBox) return;
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    }

    // =========================================================================
    // 1. Vendor Overview & Package Inventory
    // =========================================================================
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

    // =========================================================================
    // 2. Drone Fleet Operations
    // =========================================================================
    async function loadDrones() {
        if (!dronesTableBody) return;
        try {
            const response = await fetch('/api/drones');
            const data = await response.json();

            if (response.ok && data.success) {
                renderDrones(data.drones || []);
            } else {
                dronesTableBody.innerHTML = `
                    <tr><td colspan="5" style="text-align: center; color: #dc2626; padding: 1rem;">
                        ${data.message || 'Failed to fetch drone fleet.'}
                    </td></tr>
                `;
            }
        } catch (err) {
            console.error('Error loading drones:', err);
            dronesTableBody.innerHTML = `
                <tr><td colspan="5" style="text-align: center; color: #dc2626; padding: 1rem;">
                    Network error fetching drone fleet.
                </td></tr>
            `;
        }
    }

    function renderDrones(drones) {
        if (!dronesTableBody) return;
        dronesTableBody.innerHTML = '';

        if (drones.length === 0) {
            dronesTableBody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align: center; color: #64748b; padding: 1.5rem;">
                        No drones registered in the database yet. Use the form above to add your first airframe.
                    </td>
                </tr>
            `;
            return;
        }

        drones.forEach(d => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>#${d.DRONE_ID}</strong></td>
                <td>${d.PAYLOAD_CAP} kg</td>
                <td>${d.CURR_LOCATION}</td>
                <td>${d.PURCHASE_DATE || '—'}</td>
                <td>${d.LAST_DELIVERY || 'Baseline'}</td>
            `;
            dronesTableBody.appendChild(tr);
        });
    }

    if (registerDroneForm) {
        registerDroneForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideAlert();

            const droneIdVal = document.getElementById('drone-id-input').value.trim();
            const payloadCapVal = document.getElementById('drone-payload-input').value.trim();
            const locationVal = document.getElementById('drone-location-input').value.trim();
            const purchaseDateVal = document.getElementById('drone-date-input').value.trim();

            if (!droneIdVal || !payloadCapVal || !locationVal) {
                showAlert('Drone ID, Payload Capacity, and Base Location are required.');
                return;
            }

            const payload = {
                drone_id: parseInt(droneIdVal, 10),
                payload_cap: parseInt(payloadCapVal, 10),
                curr_location: locationVal
            };

            if (purchaseDateVal) {
                payload.purchase_date = purchaseDateVal;
            }

            btnRegisterDrone.disabled = true;
            btnRegisterDrone.textContent = 'Registering...';

            try {
                const response = await fetch('/api/drones', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    showAlert(data.message || 'Drone registered successfully!', true);
                    registerDroneForm.reset();
                    loadDrones();
                } else {
                    showAlert(data.message || 'Failed to register drone.');
                }
            } catch (err) {
                console.error('Error registering drone:', err);
                showAlert('Network error occurred while registering drone.');
            } finally {
                btnRegisterDrone.disabled = false;
                btnRegisterDrone.textContent = 'Register Drone';
            }
        });
    }

    // =========================================================================
    // 3. Pilot Personnel & Duty Status Controls
    // =========================================================================
    async function loadPilots() {
        if (!pilotsTableBody) return;
        try {
            const response = await fetch('/api/pilots');
            const data = await response.json();

            if (response.ok && data.success) {
                renderPilots(data.pilots || []);
            } else {
                pilotsTableBody.innerHTML = `
                    <tr><td colspan="6" style="text-align: center; color: #dc2626; padding: 1rem;">
                        ${data.message || 'Failed to load pilot roster.'}
                    </td></tr>
                `;
            }
        } catch (err) {
            console.error('Error loading pilots:', err);
            pilotsTableBody.innerHTML = `
                <tr><td colspan="6" style="text-align: center; color: #dc2626; padding: 1rem;">
                    Network error loading pilot roster.
                </td></tr>
            `;
        }
    }

    function renderPilots(pilots) {
        if (!pilotsTableBody) return;
        pilotsTableBody.innerHTML = '';

        if (pilots.length === 0) {
            pilotsTableBody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; color: #64748b; padding: 1.5rem;">
                        No pilots registered in the database yet. Use the form above to onboard pilots.
                    </td>
                </tr>
            `;
            return;
        }

        pilots.forEach(p => {
            const tr = document.createElement('tr');

            let badgeClass = 'badge-pending';
            let actionHtml = '';

            if (p.STATUS === 'AVAILABLE') {
                badgeClass = 'badge-completed';
                actionHtml = `<button class="btn-sm btn-action btn-secondary-action btn-toggle-pilot" data-id="${p.PILOT_ID}" data-status="OFF_DUTY">Set Off-Duty</button>`;
            } else if (p.STATUS === 'OFF_DUTY') {
                badgeClass = 'badge-pending';
                actionHtml = `<button class="btn-sm btn-action btn-track btn-toggle-pilot" data-id="${p.PILOT_ID}" data-status="AVAILABLE">Set Available</button>`;
            } else if (p.STATUS === 'ON_MISSION') {
                badgeClass = 'badge-ongoing';
                actionHtml = `<span style="font-size: 0.85rem; color: #1e40af; font-weight: 600;">Locked in Flight</span>`;
            }

            tr.innerHTML = `
                <td><strong>#${p.PILOT_ID}</strong></td>
                <td>${p.PILOT_NAME}</td>
                <td><code>${p.LICENSE_NUMBER}</code></td>
                <td>${p.PHONE_NO}</td>
                <td><span class="${badgeClass}">${p.STATUS}</span></td>
                <td>${actionHtml}</td>
            `;
            pilotsTableBody.appendChild(tr);
        });

        // Attach event listeners to duty toggle buttons
        document.querySelectorAll('.btn-toggle-pilot').forEach(btn => {
            btn.addEventListener('click', () => {
                const pilotId = btn.getAttribute('data-id');
                const targetStatus = btn.getAttribute('data-status');
                handleTogglePilotStatus(pilotId, targetStatus);
            });
        });
    }

    async function handleTogglePilotStatus(pilotId, targetStatus) {
        hideAlert();
        try {
            const response = await fetch(`/api/pilots/${pilotId}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: targetStatus })
            });
            const data = await response.json();

            if (response.ok && data.success) {
                showAlert(data.message || 'Pilot duty status updated successfully!', true);
                loadPilots();
            } else {
                showAlert(data.message || 'Failed to update pilot duty status.');
            }
        } catch (err) {
            console.error('Error toggling pilot status:', err);
            showAlert('Network error while updating pilot status.');
        }
    }

    if (registerPilotForm) {
        registerPilotForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideAlert();

            const nameVal = document.getElementById('pilot-name-input').value.trim();
            const licenseVal = document.getElementById('pilot-license-input').value.trim();
            const phoneVal = document.getElementById('pilot-phone-input').value.trim();
            const statusVal = document.getElementById('pilot-status-select').value;

            if (!nameVal || !licenseVal || !phoneVal) {
                showAlert('Pilot name, license number, and 10-digit phone number are required.');
                return;
            }

            if (!/^[0-9]{10}$/.test(phoneVal)) {
                showAlert('Phone number must contain exactly 10 digits.');
                return;
            }

            btnRegisterPilot.disabled = true;
            btnRegisterPilot.textContent = 'Adding...';

            try {
                const response = await fetch('/api/pilots', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        pilot_name: nameVal,
                        license_number: licenseVal,
                        phone_no: phoneVal,
                        status: statusVal
                    })
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    showAlert(data.message || 'Pilot registered successfully!', true);
                    registerPilotForm.reset();
                    loadPilots();
                } else {
                    showAlert(data.message || 'Failed to add pilot.');
                }
            } catch (err) {
                console.error('Error adding pilot:', err);
                showAlert('Network error while registering pilot.');
            } finally {
                btnRegisterPilot.disabled = false;
                btnRegisterPilot.textContent = 'Add Pilot';
            }
        });
    }

    // =========================================================================
    // 4. Delivery Corridors & Routes
    // =========================================================================
    async function loadRoutes() {
        if (!routesTableBody) return;
        try {
            const response = await fetch('/api/routes');
            const data = await response.json();

            if (response.ok && data.success) {
                renderRoutes(data.routes || []);
            } else {
                routesTableBody.innerHTML = `
                    <tr><td colspan="4" style="text-align: center; color: #dc2626; padding: 1rem;">
                        ${data.message || 'Failed to load routes.'}
                    </td></tr>
                `;
            }
        } catch (err) {
            console.error('Error loading routes:', err);
            routesTableBody.innerHTML = `
                <tr><td colspan="4" style="text-align: center; color: #dc2626; padding: 1rem;">
                    Network error loading delivery routes.
                </td></tr>
            `;
        }
    }

    function renderRoutes(routes) {
        if (!routesTableBody) return;
        routesTableBody.innerHTML = '';

        if (routes.length === 0) {
            routesTableBody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; color: #64748b; padding: 1.5rem;">
                        No delivery routes registered yet. Use the form above to define your first route corridor.
                    </td>
                </tr>
            `;
            return;
        }

        routes.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>#${r.ROUTE_ID}</strong></td>
                <td><strong>${r.SOURCE}</strong> &rarr; <strong>${r.DESTINATION}</strong></td>
                <td>${r.DISTANCE} km</td>
                <td>${r.ESTIMATED_TIME} mins</td>
            `;
            routesTableBody.appendChild(tr);
        });
    }

    if (registerRouteForm) {
        registerRouteForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideAlert();

            const routeIdVal = document.getElementById('route-id-input').value.trim();
            const sourceVal = document.getElementById('route-source-input').value.trim();
            const destVal = document.getElementById('route-dest-input').value.trim();
            const distanceVal = document.getElementById('route-distance-input').value.trim();
            const timeVal = document.getElementById('route-time-input').value.trim();

            if (!sourceVal || !destVal || !distanceVal || !timeVal) {
                showAlert('Source, Destination, Distance, and Estimated Time are required.');
                return;
            }

            const payload = {
                source: sourceVal,
                destination: destVal,
                distance: parseFloat(distanceVal),
                estimated_time: parseInt(timeVal, 10)
            };

            if (routeIdVal) {
                payload.route_id = parseInt(routeIdVal, 10);
            }

            btnRegisterRoute.disabled = true;
            btnRegisterRoute.textContent = 'Adding...';

            try {
                const response = await fetch('/api/routes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    showAlert(data.message || 'Route registered successfully!', true);
                    registerRouteForm.reset();
                    loadRoutes();
                } else {
                    showAlert(data.message || 'Failed to add route.');
                }
            } catch (err) {
                console.error('Error adding route:', err);
                showAlert('Network error while registering route.');
            } finally {
                btnRegisterRoute.disabled = false;
                btnRegisterRoute.textContent = 'Add Route';
            }
        });
    }

    // Initialize all sections
    loadVendorDashboard();
    loadDrones();
    loadPilots();
    loadRoutes();
});
