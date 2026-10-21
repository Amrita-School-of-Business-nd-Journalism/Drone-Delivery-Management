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
* The creation form dynamically populates with all registered drones, available pilots, pending packages, and valid routes.
* Initiate dispatch by clicking **Start Mission** (`IDLE` $\rightarrow$ `ONGOING`), which sets the pilot status to `ON_MISSION`.
* Finalize delivery by clicking **Complete Mission** (`ONGOING` $\rightarrow$ `OVER`), which releases the pilot back to `AVAILABLE`.

### E. Battery & Charging Supervision
* Navigate to **Batteries & Charging** (`/vendor/batteries`).
* Register new battery hardware linked to an existing drone.
* Manage charging sessions: click **Start Charging** to begin a charge; click **End Charging** to finalize the session and increment the battery's charge cycle counter.

---

## 8. Common Database Connection & Initialization Errors

| Error Symptom | Common Root Cause | Resolution |
| :--- | :--- | :--- |
| `mysql.connector.errors.ProgrammingError: 1049 (42000): Unknown database 'DRONEDELIVERY'` | Schema DDL was not executed prior to server launch. | Run `mysql -u root -p < database/DDL.sql` to initialize the database. |
| `mysql.connector.errors.InterfaceError: 2003: Can't connect to MySQL server on 'localhost'` | MySQL/MariaDB server daemon is stopped or listening on another port. | Start the service: `sudo systemctl start mariadb` or verify `DB_PORT` in `.env`. |
| `mysql.connector.errors.ProgrammingError: 1045 (28000): Access denied for user` | Incorrect `DB_USER` or `DB_PASSWORD` in `.env`. | Verify credentials using MySQL command line: `mysql -u <user> -p`. Update `.env` accordingly. |
| `Mission dropdowns are empty in the Vendor interface` | Database schema exists but master seed data was not imported. | Run `mysql -u root -p DRONEDELIVERY < database/seeds.sql` or use the Vendor Dashboard forms to register master data. |
| `Duplicate entry for key 'PHONE_NO'` or `'LICENSE_NUMBER'` | Violating unique constraints defined in `DDL.sql`. | Ensure each pilot and user has a unique phone number and license ID. |
