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

### Step 4: Apply Payments Billing & Maintenance Diagnostics Objects
Deploy the billing procedures, payment integrity guards, and maintenance stored procedures for Checkpoint 3:
```bash
mysql -u root -p DRONEDELIVERY < database/checkpoint3_maintenance_payments.sql
```
> **Note:** `database/checkpoint3_maintenance_payments.sql` configures auto-increment for `PAYMENTS` and `MAINTENACE`, installs `sp_process_payment` and `sp_record_maintenance`, installs triggers `trg_check_payment_mission_status` and `trg_check_maintenance_validity`, and updates mission dispatch procedures to evaluate latest maintenance conditions. It is idempotent and safe to run on existing databases.

#### Database Installation Summary:
- **Fresh Database Setup:** Execute Step 1 (`DDL.sql`) $\rightarrow$ Step 2 (`seeds.sql`) $\rightarrow$ Step 3 (`checkpoint2_integrity.sql`) $\rightarrow$ Step 4 (`checkpoint3_maintenance_payments.sql`).
- **Existing Populated Database:** Steps 3 and 4 can be safely executed or rerun at any time without dropping tables or losing live users, packages, or flight history.

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

## 9. Payments, Billing & Academic Pricing Model

### A. Academic Pricing Formula
To calculate delivery charges without external billing services, the system introduces a deterministic, server-validated academic pricing formula:

$$\text{AMOUNT} = \max\left(50, \operatorname{round}\left(50 + (10 \times \text{DISTANCE}) + (15 \times \text{WEIGHT})\right)\right)$$

* **Base Handling Fee:** ₹50.00 flat fee for every delivery.
* **Distance Rate:** ₹10.00 per kilometer (derived from `ROUTES.DISTANCE`).
* **Weight Rate:** ₹15.00 per kilogram (derived from `PACKAGES.WEIGHT`).
* **Currency:** Indian Rupee (INR / ₹).
* **Rounding & Storage:** Rounded to the nearest integer to match the schema type `PAYMENTS.AMOUNT INT(11)`.
* **Example Calculation:**
  * For Route 1 (8.5 km) carrying a 4 kg package:
  * $\text{Total} = 50 + (10 \times 8.5) + (15 \times 4) = 50 + 85 + 60 = 195 \text{ INR}$.

### B. Payment Workflow & Invariants
* **Eligibility:** Payment can **only** be submitted for completed missions (`MISSION_STATUS = 'OVER'`). Attempting to pay for `IDLE` or `ONGOING` missions is blocked at both API and trigger levels.
* **Customer Ownership:** Enforced via SQL queries matching `PACKAGES.USER_ID = session['user_id']`. Non-owners and vendors are blocked with `403 Forbidden`.
* **Duplicate Prevention:** Once a payment is recorded with `STATUS = 'COMPLETED'`, further payment requests for that mission return `409 Conflict`.
* **Supported Modes:**
  * `ONLINE`: In this academic demo system (without an external banking gateway), this records the payment as `COMPLETED` immediately.
  * `COD` (Cash on Delivery): Records the payment as `PROCESSING`, awaiting cash handover upon physical receipt.
* **Audit Trail:** Payments are stored permanently in `PAYMENTS`; records are never deleted to reverse a transaction.

---

## 10. Drone Maintenance & Grounding Diagnostics

### A. Operational Workflow
* Accessible from the **Vendor Dashboard** under the **Drone Maintenance** section (`#maintenance-section`).
* Vendors can log diagnostic inspection events:
  * **Condition Status:** `GOOD` (Clearance / Routine inspection passed) or `BAD` (Issue detected / Grounded).
  * **Repair Cost:** Must be a positive integer ($\text{COST} > 0$).
  * **Repair Date:** Defaults to current date (future dates beyond 1 day rejected).
  * **Reason / Notes:** Diagnostic description (e.g., "Rotor frame fracture", "Routine inspection").

### B. Flight-Readiness Integration
* A drone whose **latest** maintenance record has `STATUS = 'BAD'` is strictly grounded.
* Grounded drones cannot be selected or dispatched in `sp_create_mission` or launched in `sp_start_mission`.
* Recording a subsequent `STATUS = 'GOOD'` inspection record clears the issue and restores flight eligibility.
* An older `GOOD` record does not override a subsequent `BAD` record, maintaining flight safety invariants.

---

## 11. Stored Procedures, Triggers & Transactions Summary

### Stored Procedures (6 Total)
1. **`sp_create_mission`**: Atomic validation (ownership, payload weight, battery health, charging locks, latest maintenance status) and insertion in `IDLE` state.
2. **`sp_start_mission`**: Row-locked (`FOR UPDATE`) re-verification and transition to `ONGOING`, setting pilot to `ON_MISSION`.
3. **`sp_complete_mission`**: Atomic 4-table update: mission marked `OVER`, pilot released to `AVAILABLE`, package set to `NOT AVAILABLE`, drone location synced to destination with updated `LAST_DELIVERY`.
4. **`sp_cancel_mission`**: Aborts `IDLE` mission and restores package/pilot availability.
5. **`sp_process_payment`**: Validates customer ownership, enforces completed mission state, applies deterministic billing formula, checks for duplicate completion, and inserts into `PAYMENTS`.
6. **`sp_record_maintenance`**: Validates cost and status, logs maintenance event, and updates drone diagnostic history.

### Database Triggers (6 Total)
1. **`trg_check_mission_payload_assignment`**: Blocks insertion/update if package weight exceeds drone capacity or if drone/pilot/package is already on an active mission.
2. **`trg_check_mission_transition`**: Enforces legal state machine transitions (`IDLE` $\rightarrow$ `ONGOING`/`CANCELLED`, `ONGOING` $\rightarrow$ `OVER`).
3. **`trg_check_charging_drone_not_flying`**: Blocks charging session insertion for drones actively flying.
4. **`trg_check_mission_start_drone_not_charging`**: Blocks mission launch if drone is actively charging.
5. **`trg_check_payment_mission_status`**: Blocks payment logging if mission is not `OVER` or if duplicate completed payment exists.
6. **`trg_check_maintenance_validity`**: Enforces `COST > 0` and rejects invalid future repair dates.

---

## 12. Automated Testing & Verification

The test suite contains 24 automated unit and integration tests covering static checks, authorization, flight integrity, charging restrictions, payment workflows, maintenance diagnostics, and transactional rollbacks.

### Run All Test Suites:
```bash
# Ensure virtual environment is activated:
python -m unittest discover -s tests -p "test_*.py" -v
```

### Run Checkpoint-Specific Suites:
```bash
# Checkpoint 2 (Lifecycle Integrity & Triggers - 12 tests):
python -m unittest tests/test_checkpoint2.py -v

# Checkpoint 3 (Payments & Maintenance Diagnostics - 12 tests):
python -m unittest tests/test_checkpoint3.py -v
```

---

## 13. End-to-End Demo Walkthrough

1. **Customer Package Booking:**
   * Login as customer (`rahul.verma@example.com` / `password123`).
   * Book a delivery request (Warehouse A to Zone A, Weight: 4 kg).
2. **Vendor Mission Dispatch:**
   * Login as vendor (`vikram.malhotra@apexlogistics.com` / `password123`).
   * On **Missions** page, select the package, an available drone, an available pilot, and Route 1.
   * Click **Create Mission** (`IDLE`).
   * Click **Start Mission** (`ONGOING` &mdash; pilot status becomes `ON_MISSION`).
   * Click **Complete Mission** (`OVER` &mdash; pilot freed, drone moved to Zone A).
3. **Customer Billing & Payment:**
   * Return to customer account and open **Track Delivery**.
   * View the calculated bill breakdown: Base (₹50) + Distance (8.5 km @ ₹10 = ₹85) + Weight (4 kg @ ₹15 = ₹60) = ₹195.
   * Select `ONLINE` payment and submit. The status transitions to `COMPLETED`.
   * Open the **Dashboard** to see the payment transaction logged in **Billing & Payment History**.
4. **Maintenance Diagnostics & Grounding Demo:**
   * Return to vendor dashboard and navigate to **Fleet Maintenance**.
   * Ground Drone 101: Select Drone 101, Status `BAD`, Cost `300`, Reason `Motor bearing wear`.
   * Try to create a mission with Drone 101: The system rejects creation ("Drone is grounded under active maintenance").
   * Clear Drone 101: Select Drone 101, Status `GOOD`, Cost `150`, Reason `Bearings replaced and tested`.
   * Drone 101 is now flight-ready again.

---

## 14. DBMS Architecture & Viva Review Summary

* **Relational Schema:** 11 normalized tables (`USERS`, `VENDORS`, `DRONES`, `PILOTS`, `BATTERIES`, `MAINTENACE`, `CHARGING_SESSIONS`, `PACKAGES`, `ROUTES`, `MISSIONS`, `PAYMENTS`).
* **Integrity Constraints:** Primary keys, foreign key cascading controls, unique constraints on user emails, phone numbers, pilot licenses, vendor product IDs, and CHECK constraints (`AMOUNT > 0`, `COST > 0`, phone regexp).
* **Concurrency & ACID Transactions:** Stored procedures utilize `START TRANSACTION`, `COMMIT`, `ROLLBACK`, and `SELECT ... FOR UPDATE` row locks to prevent race conditions during dispatch and billing.
* **Triggers vs Application Logic:** Critical safety invariants (payload capacity, state machine transitions, charging while flying, payment on incomplete delivery) are enforced directly within MariaDB triggers to ensure data integrity cannot be bypassed by raw SQL or external clients.

---

## 15. Common Database Connection & Initialization Errors

| Error Symptom | Common Root Cause | Resolution |
| :--- | :--- | :--- |
| `mysql.connector.errors.ProgrammingError: 1049 (42000): Unknown database 'DRONEDELIVERY'` | Schema DDL was not executed prior to server launch. | Run `mysql -u root -p < database/DDL.sql` to initialize the database. |
| `mysql.connector.errors.InterfaceError: 2003: Can't connect to MySQL server on 'localhost'` | MySQL/MariaDB server daemon is stopped or listening on another port. | Start the service: `sudo systemctl start mariadb` or verify `DB_PORT` in `.env`. |
| `mysql.connector.errors.ProgrammingError: 1045 (28000): Access denied for user` | Incorrect `DB_USER` or `DB_PASSWORD` in `.env`. | Verify credentials using MySQL command line: `mysql -u <user> -p`. Update `.env` accordingly. |
| `Mission dropdowns are empty in the Vendor interface` | Database schema exists but master seed data was not imported. | Run `mysql -u root -p DRONEDELIVERY < database/seeds.sql` or use the Vendor Dashboard forms to register master data. |
| `Duplicate entry for key 'PHONE_NO'` or `'LICENSE_NUMBER'` | Violating unique constraints defined in `DDL.sql`. | Ensure each pilot and user has a unique phone number and license ID. |
