document.addEventListener('DOMContentLoaded', () => {
    const alertBox = document.getElementById('alert-message');
    const droneSelect = document.getElementById('drone-select');
    const pilotSelect = document.getElementById('pilot-select');
    const packageSelect = document.getElementById('package-select');
    const routeSelect = document.getElementById('route-select');
    const createForm = document.getElementById('create-mission-form');
    const missionsBody = document.getElementById('missions-table-body');
    const btnSubmit = document.getElementById('btn-submit-mission');

    function showAlert(message, type = 'error') {
        alertBox.className = `alert-box alert-${type}`;
        alertBox.textContent = message;
        alertBox.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function hideAlert() {
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    }

    async function loadOptions() {
        try {
            const res = await fetch('/api/missions/options');
            const data = await res.json();

            if (!data.success) {
                showAlert(data.message || 'Failed to load options.');
                return;
            }

            // Populate Drones
            droneSelect.innerHTML = '<option value="">-- Select Drone --</option>';
            if (data.drones && data.drones.length > 0) {
                data.drones.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.DRONE_ID;
                    opt.textContent = `Drone #${d.DRONE_ID} (Cap: ${d.PAYLOAD_CAP}kg, Loc: ${d.CURR_LOCATION})`;
                    droneSelect.appendChild(opt);
                });
            } else {
                droneSelect.innerHTML = '<option value="">No Drones available in DB</option>';
            }

            // Populate Pilots
            pilotSelect.innerHTML = '<option value="">-- Select Pilot --</option>';
            if (data.pilots && data.pilots.length > 0) {
                data.pilots.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.PILOT_ID;
                    opt.textContent = `Pilot #${p.PILOT_ID}: ${p.PILOT_NAME} [${p.STATUS}]`;
                    if (p.STATUS !== 'AVAILABLE') {
                        opt.disabled = true;
                    }
                    pilotSelect.appendChild(opt);
                });
            } else {
                pilotSelect.innerHTML = '<option value="">No Pilots available in DB</option>';
            }

            // Populate Packages
            packageSelect.innerHTML = '<option value="">-- Select Package --</option>';
            if (data.packages && data.packages.length > 0) {
                data.packages.forEach(pkg => {
                    const opt = document.createElement('option');
                    opt.value = pkg.PACKAGE_ID;
                    opt.textContent = `Package #${pkg.PACKAGE_ID} (Product: ${pkg.PRODUCT_ID}, Weight: ${pkg.WEIGHT}kg)`;
                    packageSelect.appendChild(opt);
                });
            } else {
                packageSelect.innerHTML = '<option value="">No Packages available in DB</option>';
            }

            // Populate Routes
            routeSelect.innerHTML = '<option value="">-- Select Route --</option>';
            if (data.routes && data.routes.length > 0) {
                data.routes.forEach(r => {
                    const opt = document.createElement('option');
                    opt.value = r.ROUTE_ID;
                    opt.textContent = `Route #${r.ROUTE_ID}: ${r.SOURCE} -> ${r.DESTINATION} (${r.DISTANCE} km)`;
                    routeSelect.appendChild(opt);
                });
            } else {
                routeSelect.innerHTML = '<option value="">No Routes available in DB</option>';
            }

        } catch (err) {
            console.error('Error loading mission options:', err);
            showAlert('Failed to connect to server while loading dropdown options.');
        }
    }

    async function loadMissions() {
        try {
            const res = await fetch('/api/missions');
            const data = await res.json();

            if (!data.success) {
                showAlert(data.message || 'Failed to load missions.');
                return;
            }

            const missions = data.missions || [];
            if (missions.length === 0) {
                missionsBody.innerHTML = `
                    <tr>
                        <td colspan="9" style="text-align: center; color: #64748b; padding: 1.5rem;">
                            No missions created yet.
                        </td>
                    </tr>
                `;
                return;
            }

            missionsBody.innerHTML = '';
            missions.forEach(m => {
                const tr = document.createElement('tr');

                let statusBadgeClass = 'badge-pending';
                if (m.MISSION_STATUS === 'ONGOING') statusBadgeClass = 'badge-ongoing';
                else if (m.MISSION_STATUS === 'OVER') statusBadgeClass = 'badge-completed';
                else if (m.MISSION_STATUS === 'CANCELLED') statusBadgeClass = 'alert-error';

                let actionBtn = '';
                if (m.MISSION_STATUS === 'IDLE') {
                    actionBtn = `
                        <button class="btn-sm btn-action btn-start-mission" data-id="${m.MISSION_ID}">Start</button>
                        <button class="btn-sm btn-action btn-secondary-action btn-cancel-mission" data-id="${m.MISSION_ID}" style="margin-left: 0.35rem;">Cancel</button>
                    `;
                } else if (m.MISSION_STATUS === 'ONGOING') {
                    actionBtn = `<button class="btn-sm btn-action btn-secondary-action btn-complete-mission" data-id="${m.MISSION_ID}">Complete</button>`;
                } else if (m.MISSION_STATUS === 'CANCELLED') {
                    actionBtn = `<span style="color: #991b1b; font-size: 0.85rem; font-weight: 600;">Cancelled</span>`;
                } else {
                    actionBtn = `<span style="color: #065f46; font-size: 0.85rem; font-weight: 600;">Completed</span>`;
                }

                const pilotDisplay = m.PILOT_NAME ? `${m.PILOT_NAME} (#${m.PILOT_ID})` : `#${m.PILOT_ID}`;
                const routeDisplay = (m.SOURCE && m.DESTINATION) ? `${m.SOURCE} → ${m.DESTINATION}` : `Route #${m.ROUTE_ID}`;
                const startTimeDisplay = m.START_TIME || '—';
                const endTimeDisplay = m.END_TIME || '—';

                tr.innerHTML = `
                    <td><strong>#${m.MISSION_ID}</strong></td>
                    <td>Drone #${m.DRONE_ID}</td>
                    <td>${pilotDisplay}</td>
                    <td>Package #${m.PACKAGE_ID}</td>
                    <td>${routeDisplay}</td>
                    <td><span class="${statusBadgeClass}">${m.MISSION_STATUS}</span></td>
                    <td>${startTimeDisplay}</td>
                    <td>${endTimeDisplay}</td>
                    <td>${actionBtn}</td>
                `;
                missionsBody.appendChild(tr);
            });

            // Attach event listeners to action buttons
            document.querySelectorAll('.btn-start-mission').forEach(btn => {
                btn.addEventListener('click', () => handleStartMission(btn.getAttribute('data-id')));
            });

            document.querySelectorAll('.btn-complete-mission').forEach(btn => {
                btn.addEventListener('click', () => handleCompleteMission(btn.getAttribute('data-id')));
            });

            document.querySelectorAll('.btn-cancel-mission').forEach(btn => {
                btn.addEventListener('click', () => handleCancelMission(btn.getAttribute('data-id')));
            });

        } catch (err) {
            console.error('Error loading missions:', err);
            showAlert('Failed to connect to server while loading mission records.');
        }
    }

    createForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const missionIdVal = document.getElementById('mission-id-input').value.trim();
        const droneId = droneSelect.value;
        const pilotId = pilotSelect.value;
        const packageId = packageSelect.value;
        const routeId = routeSelect.value;

        if (!droneId || !pilotId || !packageId || !routeId) {
            showAlert('Please select valid Drone, Pilot, Package, and Route.');
            return;
        }

        btnSubmit.disabled = true;
        btnSubmit.textContent = 'Creating...';

        try {
            const payload = {
                drone_id: parseInt(droneId),
                pilot_id: parseInt(pilotId),
                package_id: parseInt(packageId),
                route_id: parseInt(routeId)
            };

            if (missionIdVal !== '') {
                payload.mission_id = parseInt(missionIdVal);
            }

            const res = await fetch('/api/missions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();

            if (data.success) {
                showAlert(data.message, 'success');
                document.getElementById('mission-id-input').value = '';
                loadOptions();
                loadMissions();
            } else {
                showAlert(data.message || 'Failed to create mission.');
            }
        } catch (err) {
            console.error('Error creating mission:', err);
            showAlert('Network or server error while creating mission.');
        } finally {
            btnSubmit.disabled = false;
            btnSubmit.textContent = 'Create Mission';
        }
    });

    async function handleStartMission(missionId) {
        hideAlert();
        try {
            const res = await fetch(`/api/missions/${missionId}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();

            if (data.success) {
                showAlert(data.message, 'success');
                loadOptions();
                loadMissions();
            } else {
                showAlert(data.message || 'Failed to start mission.');
            }
        } catch (err) {
            console.error('Error starting mission:', err);
            showAlert('Network or server error while starting mission.');
        }
    }

    async function handleCompleteMission(missionId) {
        hideAlert();
        try {
            const res = await fetch(`/api/missions/${missionId}/complete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();

            if (data.success) {
                showAlert(data.message, 'success');
                loadOptions();
                loadMissions();
            } else {
                showAlert(data.message || 'Failed to complete mission.');
            }
        } catch (err) {
            console.error('Error completing mission:', err);
            showAlert('Network or server error while completing mission.');
        }
    }

    async function handleCancelMission(missionId) {
        hideAlert();
        if (!confirm(`Are you sure you want to cancel Mission #${missionId}? The package and pilot will be released.`)) {
            return;
        }

        try {
            const res = await fetch(`/api/missions/${missionId}/cancel`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();

            if (data.success) {
                showAlert(data.message, 'success');
                loadOptions();
                loadMissions();
            } else {
                showAlert(data.message || 'Failed to cancel mission.');
            }
        } catch (err) {
            console.error('Error cancelling mission:', err);
            showAlert('Network or server error while cancelling mission.');
        }
    }

    loadOptions();
    loadMissions();
});
