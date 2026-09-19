document.addEventListener('DOMContentLoaded', () => {
    const packageSelect = document.getElementById('package-select');
    const packageInput = document.getElementById('package-id-input');
    const trackForm = document.getElementById('track-form');
    const alertBox = document.getElementById('alert-message');
    const trackingResults = document.getElementById('tracking-results');
    const trackSubmitBtn = document.getElementById('track-submit-btn');

    function showAlert(message, isSuccess = false) {
        alertBox.textContent = message;
        alertBox.className = `alert-box ${isSuccess ? 'alert-success' : 'alert-error'}`;
        alertBox.style.display = 'block';
    }

    function hideAlert() {
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    }

    // Load customer's packages into dropdown
    async function loadMyPackages() {
        try {
            const response = await fetch('/api/customer/my-packages');
            const data = await response.json();

            packageSelect.innerHTML = '';

            if (response.ok && data.success && data.packages && data.packages.length > 0) {
                const defaultOpt = document.createElement('option');
                defaultOpt.value = '';
                defaultOpt.textContent = '-- Select a Package --';
                packageSelect.appendChild(defaultOpt);

                data.packages.forEach(pkg => {
                    const opt = document.createElement('option');
                    opt.value = pkg.PACKAGE_ID;
                    opt.textContent = `Package #${pkg.PACKAGE_ID} (Product: ${pkg.PRODUCT_ID})`;
                    packageSelect.appendChild(opt);
                });
            } else {
                const noOpt = document.createElement('option');
                noOpt.value = '';
                noOpt.textContent = 'No packages found for your account.';
                packageSelect.appendChild(noOpt);
            }

            // Check if package_id query param exists in URL
            const urlParams = new URLSearchParams(window.location.search);
            const queryPackageId = urlParams.get('package_id');
            if (queryPackageId) {
                packageInput.value = queryPackageId;
                packageSelect.value = queryPackageId;
                fetchTrackingData(queryPackageId);
            }

        } catch (error) {
            console.error('Error loading my packages:', error);
        }
    }

    packageSelect.addEventListener('change', () => {
        if (packageSelect.value) {
            packageInput.value = packageSelect.value;
        }
    });

    packageInput.addEventListener('input', () => {
        if (packageInput.value) {
            packageSelect.value = packageInput.value;
        }
    });

    trackForm.addEventListener('submit', (e) => {
        e.preventDefault();
        hideAlert();

        const packageId = packageInput.value || packageSelect.value;
        if (!packageId || parseInt(packageId, 10) <= 0) {
            showAlert('Please select or enter a valid Package ID.');
            return;
        }

        fetchTrackingData(packageId);
    });

    async function fetchTrackingData(packageId) {
        hideAlert();
        trackingResults.style.display = 'none';
        trackSubmitBtn.disabled = true;
        trackSubmitBtn.textContent = 'Tracking...';

        try {
            const response = await fetch(`/api/customer/track/${packageId}`);
            const data = await response.json();

            if (response.ok && data.success && data.package) {
                renderTrackingResults(data.package);
                trackingResults.style.display = 'block';
            } else {
                showAlert(data.message || 'Package not found or access denied.');
            }
        } catch (error) {
            console.error('Tracking fetch error:', error);
            showAlert('Network error trying to fetch tracking details.');
        } finally {
            trackSubmitBtn.disabled = false;
            trackSubmitBtn.textContent = 'Track Package';
        }
    }

    function renderTrackingResults(pkg) {
        document.getElementById('res-package-id').textContent = pkg.package_id;
        document.getElementById('res-product-id').textContent = pkg.product_id;
        document.getElementById('res-weight').textContent = `${pkg.weight} kg`;
        document.getElementById('res-priority').textContent = pkg.priority;
        document.getElementById('res-vendor').textContent = pkg.vendor_name || 'Not available';

        const pkgStatusElem = document.getElementById('res-package-status');
        pkgStatusElem.textContent = pkg.package_status || 'AVAILABLE';

        const missionStatusElem = document.getElementById('res-mission-status');
        missionStatusElem.textContent = pkg.mission_status || 'Not available';
        
        let missionBadgeClass = 'badge-pending';
        if (pkg.mission_status === 'ONGOING') missionBadgeClass = 'badge-ongoing';
        if (pkg.mission_status === 'OVER') missionBadgeClass = 'badge-completed';
        missionStatusElem.className = `status-badge ${missionBadgeClass}`;

        document.getElementById('res-mission-id').textContent = pkg.mission_id ? `#${pkg.mission_id}` : 'Not available';
        document.getElementById('res-start-time').textContent = pkg.start_time || 'Not available';
        document.getElementById('res-end-time').textContent = pkg.end_time || 'Not available';

        document.getElementById('res-drone-id').textContent = pkg.drone_id ? `#${pkg.drone_id}` : 'Not available';
        document.getElementById('res-drone-location').textContent = pkg.drone_location || 'Not available';
        document.getElementById('res-drone-capacity').textContent = pkg.drone_payload_cap ? `${pkg.drone_payload_cap} kg` : 'Not available';

        document.getElementById('res-route-id').textContent = pkg.route_id ? `#${pkg.route_id}` : 'Not available';
        document.getElementById('res-route-source').textContent = pkg.source || 'Not available';
        document.getElementById('res-route-dest').textContent = pkg.destination || 'Not available';
        document.getElementById('res-route-distance').textContent = pkg.distance ? `${pkg.distance} km` : 'Not available';
        document.getElementById('res-route-time').textContent = pkg.estimated_time ? `${pkg.estimated_time} mins` : 'Not available';
    }

    loadMyPackages();
});
