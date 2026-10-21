# Drone Delivery Management System (`Drone_Dev`)

A role-governed web application designed to manage autonomous commercial drone delivery operations, pairing verified flight personnel, drone airframes, charging cycles, and dispatch corridors with customer delivery booking and live telemetry tracking.

---

## 1. System Requirements & Prerequisites

* **Operating System:** Linux / macOS / Windows (WSL recommended for Windows)
* **Python Runtime:** Python 3.10 or higher
* **Database Server:** MariaDB 10.5+ or MySQL 8.0+
* **Dependencies:**
  * `Flask==3.0.3` (Web application framework)
  * `mysql-connector-python==9.0.0` (Database driver)
  * `python-dotenv==1.0.1` (Environment configuration loader)
  * `Werkzeug==3.0.3` (WSGI utilities and password hashing)

---

## 2. Installation & Environment Setup

### Step 1: Clone the Repository
```bash
git clone <repository_url>
cd Drone_Dev
```

### Step 2: Create and Activate Virtual Environment
```bash
# Create virtual environment
python3 -m venv .venv

# Activate on Linux / macOS:
source .venv/bin/activate

# Or activate on Windows (PowerShell):
# .venv\Scripts\Activate.ps1
```

### Step 3: Install Required Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Database Initialization & Seeding

### Step 1: Initialize Database Schema (DDL)
Ensure your MySQL/MariaDB service is running:
```bash
# On systemd Linux systems:
sudo systemctl status mariadb # or mysql
```

Execute the database DDL script to create the `DRONEDELIVERY` database and all 11 required tables:
```bash
mysql -u root -p < database/DDL.sql
```
*(Enter your MySQL root password when prompted)*

### Step 2: Import Reproducible Master Seed Data
Load the baseline master data for Drones, Certified Pilots, and Flight Corridors:
```bash
mysql -u root -p DRONEDELIVERY < database/seeds.sql
```
> **Note:** `database/seeds.sql` is fully idempotent using `ON DUPLICATE KEY UPDATE`. It can safely be executed repeatedly without causing duplicate key collisions or database corruption.

### Step 3: Apply Delivery Lifecycle Integrity Objects (Stored Procedures & Triggers)
Deploy the business logic constraints, stored procedures, and triggers for Checkpoint 2:
```bash
mysql -u root -p DRONEDELIVERY < database/checkpoint2_integrity.sql
```
> **Note:** `database/checkpoint2_integrity.sql` aligns status ENUMs, installs 4 stored procedures (`sp_create_mission`, `sp_start_mission`, `sp_complete_mission`, `sp_cancel_mission`), and installs 4 database triggers enforcing payload limits, flight state transitions, and charging locks. It is idempotent.

---

## 4. Environment Configuration

Copy `.env.example` to create your local `.env` configuration:
```bash
cp .env.example .env
```

Edit `.env` to match your local database credentials:
```ini
# Flask Configuration
FLASK_APP=app.py
FLASK_DEBUG=True
SECRET_KEY=change_this_to_a_secure_random_key

# MySQL/MariaDB Database Configuration
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
DB_NAME=DRONEDELIVERY
```

---

## 5. Starting the Application

Launch the Flask development server:
```bash
python app.py
```
Or alternatively via Flask CLI:
```bash
flask run --host=0.0.0.0 --port=5000
```
Open your browser and navigate to: `http://localhost:5000`

---

## 6. User Roles & First Account Setup

The application features two distinct role models enforced by server-side decorators:

1. **`VENDOR` Role (Fleet Operator & Dispatcher):**
   * Manages drone fleet registration, pilot rosters, and delivery corridors.
   * Manages battery hardware and charging sessions.
   * Assembles, starts, and completes drone flight missions.
2. **`CUSTOMER` Role (Parcel Consumer):**
   * Submits package dispatch requisitions to registered vendors.
   * Tracks assigned drone, pilot, waypoints, and flight mission status in real time.

### Registering Your First Account:
1. Navigate to `/register` (`http://localhost:5000/register`).
2. Select **Vendor** from the "Account Role" dropdown.
3. Enter your contact details and business information:
   * First Name & Last Name (Max 25 characters)
   * Valid Email Address
   * 10-Digit Phone Number (e.g. `9876543210`)
   * Password ($\ge$ 6 characters)
   * Vendor Business Name & Physical Address
4. Submit the form and log in via `/` (`http://localhost:5000/`).

---

## 7. Master Data & Operations User Guide

Once logged in as a **Vendor**, the application provides the following controls:

### A. Drone Fleet Management
* Accessible directly from the **Vendor Dashboard** under the **Fleet Management** section.
* Register new airframes by specifying:
  * **Drone ID:** Unique positive integer (e.g., `106`).
  * **Payload Capacity:** Maximum cargo weight in kilograms.
  * **Base Location:** Current hangar / station name (e.g., `Warehouse A`).
  * **Purchase Date:** Date acquired (defaults to today if left blank).
* *Note on `LAST_DELIVERY`:* The underlying schema requires `LAST_DELIVERY DATETIME NOT NULL`. When a new drone is registered, it is initialized to the registration timestamp as a baseline until its first actual delivery is completed.

### B. Pilot Personnel & Duty Roster
* Accessible from the **Vendor Dashboard** under the **Pilot Personnel** section.
* Onboard certified pilots with full name, unique license number, and 10-digit phone number.
* **Duty Status Controls:**
  * Toggle between `AVAILABLE` and `OFF_DUTY`.
  * Status changes to `OFF_DUTY` are safely rejected if the pilot is assigned to an active mission.
  * The `ON_MISSION` status is strictly managed by mission dispatch and cannot be forced manually.

### C. Delivery Routes & Corridors
* Accessible from the **Vendor Dashboard** under the **Flight Network** section.
* Define new corridors by specifying:
  * **Source Waypoint:** Origin dispatch hub (e.g., `Warehouse A`).
  * **Destination Waypoint:** Delivery zone (e.g., `Zone D`).
  * **Distance:** Flight distance in kilometers.
  * **Estimated Time:** Flight duration in minutes.

### D. Mission Dispatch & Management
* Navigate to **Missions** via the top navigation bar (`/vendor/missions`).
* The creation form dynamically populates only with valid options:
  * Only packages belonging to the authenticated vendor that are available/ready for dispatch.
  * Only flight-ready drones (not currently charging, no active grounding maintenance, and possessing a healthy non-discharged battery).
  * Only available pilots (excluding pilots `OFF_DUTY` or assigned to active missions).
* Initiate dispatch by clicking **Start Mission** (`IDLE` $\rightarrow$ `ONGOING`), which sets the pilot status to `ON_MISSION`.
* Finalize delivery by clicking **Complete Mission** (`ONGOING` $\rightarrow$ `OVER`), which atomically releases the pilot back to `AVAILABLE`, marks the package as `NOT AVAILABLE` / delivered, and updates the drone's current location to the route destination with updated `LAST_DELIVERY` timestamp.
* Alternatively, abort an idle mission by clicking **Cancel Mission** (`IDLE` $\rightarrow$ `CANCELLED`), which releases package, pilot, and drone back to the available pool.

### E. Battery & Charging Supervision
* Navigate to **Batteries & Charging** (`/vendor/batteries`).
* Register new battery hardware linked to an existing drone.
* Manage charging sessions: click **Start Charging** to begin a charge; click **End Charging** to finalize the session and increment the battery's charge cycle counter.
* Drones currently engaged in active flight missions (`ONGOING`) are locked at both the application and database trigger level from beginning charging sessions.

---

## 8. Delivery Lifecycle Integrity, Stored Procedures & Triggers

To guarantee ACID consistency and business invariant enforcement at the database layer, Checkpoint 2 introduces dedicated stored procedures and triggers defined in `database/checkpoint2_integrity.sql`.

### Stored Procedures

1. **`sp_create_mission(p_vendor_id, p_drone_id, p_pilot_id, p_package_id, p_route_id, OUT p_mission_id, OUT p_status_code, OUT p_status_msg)`**
   * Verifies vendor ownership of the package.
   * Checks package status (`AVAILABLE` or `READY`), pilot status (`AVAILABLE`), and ensures none are tied to active (`IDLE` or `ONGOING`) missions.
   * Verifies drone payload capacity (`WEIGHT <= PAYLOAD_CAP`).
   * Validates drone flight eligibility (no active charging, no open maintenance, healthy battery).
   * Inserts the mission record in `IDLE` state atomically.
2. **`sp_start_mission(p_mission_id, p_vendor_id, OUT p_status_code, OUT p_status_msg)`**
   * Locks the mission record with `FOR UPDATE`.
   * Confirms mission is in `IDLE` state and owned by the vendor.
   * Re-evaluates live readiness of drone, pilot, and package.
   * Atomically transitions mission status to `ONGOING`, sets `START_TIME = NOW()`, and sets pilot status to `ON_MISSION`.
3. **`sp_complete_mission(p_mission_id, p_vendor_id, OUT p_status_code, OUT p_status_msg)`**
   * Locks the mission record with `FOR UPDATE`.
   * Confirms mission is currently in `ONGOING` state.
   * Sets `MISSION_STATUS = 'OVER'`, `END_TIME = NOW()`.
   * Sets assigned pilot status back to `AVAILABLE`.
   * Updates `DRONES.LAST_DELIVERY = NOW()` and moves `DRONES.CURR_LOCATION` to `ROUTES.DEST_LOCATION`.
   * Marks package status as `NOT AVAILABLE` (delivered).
4. **`sp_cancel_mission(p_mission_id, p_vendor_id, OUT p_status_code, OUT p_status_msg)`**
   * Locks the mission record with `FOR UPDATE`.
   * Confirms mission is currently `IDLE`.
   * Transitions `MISSION_STATUS = 'CANCELLED'`.
   * Releases package and pilot reservations, ensuring pilot remains `AVAILABLE`.

### Database Triggers

1. **`trg_check_mission_payload_assignment` (BEFORE INSERT / UPDATE on `MISSIONS`):**
   * Enforces cargo weight cannot exceed drone payload capacity (`SIGNAL SQLSTATE '45000'`).
   * Rejects duplicate assignment of package, drone, or pilot if already reserved by another active mission (`IDLE` or `ONGOING`).
2. **`trg_check_mission_transition` (BEFORE UPDATE on `MISSIONS`):**
   * Restricts lifecycle state changes strictly to valid transitions:
     * `IDLE` $\rightarrow$ `ONGOING` or `CANCELLED`
     * `ONGOING` $\rightarrow$ `OVER`
   * Prohibits tampering with historical/terminal missions (`OVER` or `CANCELLED`).
3. **`trg_check_charging_drone_not_flying` (BEFORE INSERT on `CHARGING_SESSIONS`):**
   * Prevents initiating a charging session on a drone that is actively flying an `ONGOING` mission.
4. **`trg_check_mission_start_drone_not_charging` (BEFORE UPDATE on `MISSIONS`):**
   * Prevents transitioning a mission to `ONGOING` if the drone has an active charging session (`END_TIME IS NULL`).

### Atomic Transaction Workflows

1. **Mission Creation Workflow (`POST /api/missions`):**
   * Executed within a MariaDB transaction block inside `sp_create_mission`.
   * Atomically evaluates eligibility across 5 tables (`PACKAGES`, `PILOTS`, `DRONES`, `BATTERIES`, `MAINTENACE`) and inserts the `MISSIONS` record.
2. **Mission Start Dispatch Workflow (`POST /api/missions/<id>/start`):**
   * Row-level locking (`SELECT ... FOR UPDATE`) prevents concurrent double-dispatch races.
   * Synchronously transitions `MISSIONS` to `ONGOING` and `PILOTS` to `ON_MISSION`.
3. **Mission Finalization Workflow (`POST /api/missions/<id>/complete`):**
   * Atomically mutates 4 tables (`MISSIONS`, `PILOTS`, `DRONES`, `PACKAGES`) in one isolated transaction commit: mission marked `OVER`, pilot freed, drone relocated and stamped, package completed.

---

## 9. Automated Testing & Verification

The test suite validates both positive operational lifecycles and negative edge-case rejections, including database trigger locks and transaction rollbacks.

### Run Automated Tests:
```bash
# Ensure virtual environment is activated and database is running:
python -m unittest tests/test_checkpoint2.py -v
```

### Test Coverage Summary:
* `test_01_complete_mission_lifecycle_positive`: Full end-to-end lifecycle (`IDLE` $\rightarrow$ `ONGOING` $\rightarrow$ `OVER`, drone location sync, last delivery timestamp update, pilot release).
* `test_02_mission_cancellation_flow`: Cancellation from `IDLE` state releases assets.
* `test_03_reject_overweight_package`: Rejects creation when package weight exceeds drone payload capacity.
* `test_04_reject_cross_vendor_package_dispatch`: Prevents Vendor A from dispatching Vendor B's package (403 Forbidden).
* `test_05_reject_drone_currently_charging`: Prevents mission start when drone is charging.
* `test_06_reject_charging_when_drone_flying`: Trigger rejects charging session insertion while drone is flying.
* `test_07_trigger_rejects_illegal_state_transition`: Trigger blocks illegal transitions (e.g. `IDLE` directly to `OVER`).
* `test_08_customer_cannot_dispatch_missions`: Role guard blocks non-vendors with 403 Forbidden.
* `test_09_package_tracking_reflects_lifecycle`: Live package tracking reflects status changes accurately.
* `test_10_transaction_rollback_on_failure`: Database rollback test verifying no partial state commits occur on failure.
* `test_11_reject_double_booking_active_assets`: Trigger blocks concurrent double-booking of package/pilot/drone.
* `test_12_pilot_duty_toggle_guard`: Pilot cannot be switched to `OFF_DUTY` while assigned to an active mission.

---

## 10. Common Database Connection & Initialization Errors

| Error Symptom | Common Root Cause | Resolution |
| :--- | :--- | :--- |
| `mysql.connector.errors.ProgrammingError: 1049 (42000): Unknown database 'DRONEDELIVERY'` | Schema DDL was not executed prior to server launch. | Run `mysql -u root -p < database/DDL.sql` to initialize the database. |
| `mysql.connector.errors.InterfaceError: 2003: Can't connect to MySQL server on 'localhost'` | MySQL/MariaDB server daemon is stopped or listening on another port. | Start the service: `sudo systemctl start mariadb` or verify `DB_PORT` in `.env`. |
| `mysql.connector.errors.ProgrammingError: 1045 (28000): Access denied for user` | Incorrect `DB_USER` or `DB_PASSWORD` in `.env`. | Verify credentials using MySQL command line: `mysql -u <user> -p`. Update `.env` accordingly. |
| `Mission dropdowns are empty in the Vendor interface` | Database schema exists but master seed data was not imported. | Run `mysql -u root -p DRONEDELIVERY < database/seeds.sql` or use the Vendor Dashboard forms to register master data. |
| `Duplicate entry for key 'PHONE_NO'` or `'LICENSE_NUMBER'` | Violating unique constraints defined in `DDL.sql`. | Ensure each pilot and user has a unique phone number and license ID. |
