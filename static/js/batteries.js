document.addEventListener('DOMContentLoaded', () => {
    const alertBox = document.getElementById('alert-message');
    const droneSelect = document.getElementById('battery-drone-select');
    const createForm = document.getElementById('create-battery-form');
    const batteriesBody = document.getElementById('batteries-table-body');
    const historyBody = document.getElementById('charging-history-body');
    const btnRegister = document.getElementById('btn-register-battery');

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

    async function loadDrones() {
        try {
            const res = await fetch('/api/missions/options');
            const data = await res.json();
            if (data.success && data.drones) {
                droneSelect.innerHTML = '<option value="">-- Select Drone --</option>';
                data.drones.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.DRONE_ID;
                    opt.textContent = `Drone #${d.DRONE_ID} (${d.CURR_LOCATION})`;
                    droneSelect.appendChild(opt);
                });
            } else {
                droneSelect.innerHTML = '<option value="">No Drones available in DB</option>';
            }
        } catch (err) {
            console.error('Error loading drones:', err);
        }
    }

    async function loadBatteries() {
        try {
            const res = await fetch('/api/batteries');
            const data = await res.json();

            if (!data.success) {
                showAlert(data.message || 'Failed to load batteries.');
                return;
            }

            const batteries = data.batteries || [];
            if (batteries.length === 0) {
                batteriesBody.innerHTML = `
                    <tr>
                        <td colspan="7" style="text-align: center; color: #64748b; padding: 1.5rem;">
                            No batteries registered yet.
                        </td>
                    </tr>
                `;
                return;
            }

            batteriesBody.innerHTML = '';
            batteries.forEach(b => {
                const tr = document.createElement('tr');

                let statusBadgeClass = b.STATUS === 'GOOD' ? 'badge-completed' : 'alert-error';
                let chargingBadgeClass = b.is_charging ? 'badge-ongoing' : 'badge-pending';
                let chargingText = b.is_charging ? 'Charging...' : 'Idle';

                let actionBtn = '';
                if (b.is_charging) {
                    actionBtn = `<button class="btn-sm btn-action btn-secondary-action btn-end-charge" data-id="${b.BATTERY_ID}">End Charging</button>`;
                } else {
                    actionBtn = `<button class="btn-sm btn-action btn-start-charge" data-id="${b.BATTERY_ID}">Start Charging</button>`;
                }

                tr.innerHTML = `
                    <td><strong>Battery #${b.BATTERY_ID}</strong></td>
                    <td>Drone #${b.DRONE_ID} (${b.DRONE_LOCATION || 'N/A'})</td>
                    <td>${b.CAPACITY} mAh</td>
                    <td>${b.CYCLES} cycles</td>
                    <td><span class="${statusBadgeClass}">${b.STATUS}</span></td>
                    <td><span class="${chargingBadgeClass}">${chargingText}</span></td>
                    <td>${actionBtn}</td>
                `;
                batteriesBody.appendChild(tr);
            });

            document.querySelectorAll('.btn-start-charge').forEach(btn => {
                btn.addEventListener('click', () => handleStartCharging(btn.getAttribute('data-id')));
            });

            document.querySelectorAll('.btn-end-charge').forEach(btn => {
                btn.addEventListener('click', () => handleEndCharging(btn.getAttribute('data-id')));
            });

        } catch (err) {
            console.error('Error loading batteries:', err);
            showAlert('Failed to connect to server while loading batteries.');
        }
    }

    async function loadChargingHistory() {
        try {
            const res = await fetch('/api/charging-sessions');
            const data = await res.json();

            if (!data.success) {
                return;
            }

            const sessions = data.charging_sessions || [];
            if (sessions.length === 0) {
                historyBody.innerHTML = `
                    <tr>
                        <td colspan="5" style="text-align: center; color: #64748b; padding: 1.5rem;">
                            No charging sessions recorded.
                        </td>
                    </tr>
                `;
                return;
            }

            historyBody.innerHTML = '';
            sessions.forEach(s => {
                const tr = document.createElement('tr');

                let statusBadge = s.is_ongoing 
                    ? '<span class="badge-ongoing">In Progress</span>' 
                    : '<span class="badge-completed">Completed</span>';

                tr.innerHTML = `
                    <td><strong>Battery #${s.BATTERY_ID}</strong></td>
                    <td>Drone #${s.DRONE_ID}</td>
                    <td>${s.START_TIME || '—'}</td>
                    <td>${s.END_TIME || '—'}</td>
                    <td>${statusBadge}</td>
                `;
                historyBody.appendChild(tr);
            });
        } catch (err) {
            console.error('Error loading charging history:', err);
        }
    }

    createForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const batteryId = document.getElementById('battery-id-input').value.trim();
        const droneId = droneSelect.value;
        const capacity = document.getElementById('capacity-input').value.trim();
        const cycles = document.getElementById('cycles-input').value.trim();
        const status = document.getElementById('status-select').value;

        if (!batteryId || !droneId || !capacity) {
            showAlert('Battery ID, Drone, and Capacity are required.');
            return;
        }

        btnRegister.disabled = true;
        btnRegister.textContent = 'Registering...';

        try {
            const payload = {
                battery_id: parseInt(batteryId),
                drone_id: parseInt(droneId),
                capacity: parseInt(capacity),
                cycles: parseInt(cycles || 0),
                status: status
            };

            const res = await fetch('/api/batteries', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();

            if (data.success) {
                showAlert(data.message, 'success');
                createForm.reset();
                document.getElementById('cycles-input').value = '0';
                loadBatteries();
            } else {
                showAlert(data.message || 'Failed to register battery.');
            }
        } catch (err) {
            console.error('Error registering battery:', err);
            showAlert('Network or server error while registering battery.');
        } finally {
            btnRegister.disabled = false;
            btnRegister.textContent = 'Register Battery';
        }
    });

    async function handleStartCharging(batteryId) {
        hideAlert();
        try {
            const res = await fetch('/api/charging-sessions/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ battery_id: parseInt(batteryId) })
            });

            const data = await res.json();

            if (data.success) {
                showAlert(data.message, 'success');
                loadBatteries();
                loadChargingHistory();
            } else {
                showAlert(data.message || 'Failed to start charging session.');
            }
        } catch (err) {
            console.error('Error starting charging session:', err);
            showAlert('Network or server error while starting charging session.');
        }
    }

    async function handleEndCharging(batteryId) {
        hideAlert();
        try {
            const res = await fetch('/api/charging-sessions/end', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ battery_id: parseInt(batteryId) })
            });

            const data = await res.json();

            if (data.success) {
                showAlert(data.message, 'success');
                loadBatteries();
                loadChargingHistory();
            } else {
                showAlert(data.message || 'Failed to end charging session.');
            }
        } catch (err) {
            console.error('Error ending charging session:', err);
            showAlert('Network or server error while ending charging session.');
        }
    }

    loadDrones();
    loadBatteries();
    loadChargingHistory();
});
