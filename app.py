import os
import re
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from database import get_db_connection, close_db_connection
from mysql.connector import Error as MySQLError

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_fallback_secret_key')

EMAIL_REGEX = re.compile(r'^[A-Za-z0-9_]+@[A-Za-z]+\.[A-Za-z]{2,}$')
PHONE_REGEX = re.compile(r'^[0-9]{10}$')
DATE_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# -----------------------------------------------------
# Authentication & Role Protection Decorators
# -----------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "Authentication required."}), 401
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({"success": False, "message": "Authentication required."}), 401
                return redirect(url_for('home'))
            
            user_role = session.get('role')
            if user_role != required_role:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({"success": False, "message": f"Access denied. Requires {required_role} role."}), 403
                if user_role == 'CUSTOMER':
                    return redirect(url_for('customer_dashboard'))
                elif user_role == 'VENDOR':
                    return redirect(url_for('vendor_dashboard'))
                return redirect(url_for('home'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

vendor_required = role_required('VENDOR')
customer_required = role_required('CUSTOMER')

# -----------------------------------------------------
# Page Routes
# -----------------------------------------------------
@app.route('/')
def home():
    """
    Home / Login page. If already authenticated, redirects to respective dashboard.
    """
    if 'user_id' in session:
        role = session.get('role')
        if role == 'CUSTOMER':
            return redirect(url_for('customer_dashboard'))
        elif role == 'VENDOR':
            return redirect(url_for('vendor_dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET'])
def register_page():
    """
    User Registration HTML page. If already authenticated, redirects to dashboard.
    """
    if 'user_id' in session:
        role = session.get('role')
        if role == 'CUSTOMER':
            return redirect(url_for('customer_dashboard'))
        elif role == 'VENDOR':
            return redirect(url_for('vendor_dashboard'))
    return render_template('register.html')

@app.route('/customer', methods=['GET'])
@app.route('/customer/dashboard', methods=['GET'])
@role_required('CUSTOMER')
def customer_dashboard():
    """
    Protected Customer Dashboard route.
    """
    return render_template('customer_dashboard.html')

@app.route('/customer/new-delivery', methods=['GET'])
@role_required('CUSTOMER')
def new_delivery_page():
    """
    Page for creating a new delivery request.
    """
    return render_template('new_delivery.html')

@app.route('/customer/track', methods=['GET'])
@role_required('CUSTOMER')
def track_delivery_page():
    """
    Page for customer package delivery tracking.
    """
    return render_template('track_delivery.html')

@app.route('/vendor', methods=['GET'])
@app.route('/vendor/dashboard', methods=['GET'])
@role_required('VENDOR')
def vendor_dashboard():
    """
    Protected Vendor Dashboard route.
    """
    return render_template('vendor_dashboard.html')

@app.route('/vendor/missions', methods=['GET'])
@role_required('VENDOR')
def vendor_missions_page():
    """
    Page for Vendor Mission Management.
    """
    return render_template('missions.html')

@app.route('/vendor/batteries', methods=['GET'])
@role_required('VENDOR')
def vendor_batteries_page():
    """
    Page for Vendor Battery & Charging Management.
    """
    return render_template('batteries.html')

@app.route('/profile', methods=['GET'])
@login_required
def profile_page():
    """
    User Profile HTML page. Accessible to both CUSTOMER and VENDOR.
    """
    return render_template('profile.html')

# -----------------------------------------------------
# API Endpoints
# -----------------------------------------------------
@app.route('/api/vendors', methods=['GET'])
@login_required
def api_get_vendors():
    """
    Retrieves existing vendors list from database.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        query = "SELECT VENDOR_ID, VENDOR_NAME, VENDOR_ADDRESS FROM VENDORS ORDER BY VENDOR_NAME"
        cursor.execute(query)
        vendors = cursor.fetchall()

        return jsonify({"success": True, "vendors": vendors}), 200

    except MySQLError as err:
        print(f"MySQL Error fetching vendors: {err}")
        return jsonify({"success": False, "message": "Database error fetching vendors."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/register', methods=['POST'])
def api_register():
    """
    API endpoint to handle user registration. Supports both CUSTOMER and VENDOR roles.
    For VENDOR, inserts into USERS and VENDORS in a single atomic transaction.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    email = (data.get('email') or '').strip()
    phone_no = (data.get('phone_no') or '').strip()
    password = data.get('password') or ''
    role = (data.get('role') or '').strip().upper()
    vendor_name = (data.get('vendor_name') or '').strip()
    vendor_address = (data.get('vendor_address') or '').strip()

    if not first_name or not last_name or not email or not phone_no or not password or not role:
        return jsonify({"success": False, "message": "All user fields are required."}), 400

    if len(first_name) > 25 or len(last_name) > 25:
        return jsonify({"success": False, "message": "First name and last name must not exceed 25 characters."}), 400

    if len(email) > 50 or not EMAIL_REGEX.match(email):
        return jsonify({"success": False, "message": "Invalid email address format."}), 400

    if not PHONE_REGEX.match(phone_no):
        return jsonify({"success": False, "message": "Phone number must be exactly 10 digits."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    if role not in ['CUSTOMER', 'VENDOR']:
        return jsonify({"success": False, "message": "Role must be CUSTOMER or VENDOR."}), 400

    if role == 'VENDOR':
        if not vendor_name:
            return jsonify({"success": False, "message": "Vendor Business Name is required for vendor registration."}), 400
        if len(vendor_name) > 50:
            return jsonify({"success": False, "message": "Vendor Business Name must not exceed 50 characters."}), 400
        if not vendor_address:
            return jsonify({"success": False, "message": "Vendor Address is required for vendor registration."}), 400
        if len(vendor_address) > 100:
            return jsonify({"success": False, "message": "Vendor Address must not exceed 100 characters."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        check_query = "SELECT EMAIL, PHONE_NO FROM USERS WHERE EMAIL = %s OR PHONE_NO = %s"
        cursor.execute(check_query, (email, phone_no))
        existing_users = cursor.fetchall()

        for user in existing_users:
            if user['EMAIL'].lower() == email.lower():
                return jsonify({"success": False, "message": "Email address is already registered."}), 400
            if user['PHONE_NO'] == phone_no:
                return jsonify({"success": False, "message": "Phone number is already registered."}), 400

        password_hash = generate_password_hash(password)

        insert_user_query = """
            INSERT INTO USERS (FIRST_NAME, LAST_NAME, EMAIL, PHONE_NO, PASSWORD_HASH, CREATED_AT, ROLE)
            VALUES (%s, %s, %s, %s, %s, CURDATE(), %s)
        """
        cursor.execute(insert_user_query, (first_name, last_name, email, phone_no, password_hash, role))
        
        if role == 'VENDOR':
            new_user_id = cursor.lastrowid
            insert_vendor_query = """
                INSERT INTO VENDORS (VENDOR_ID, VENDOR_NAME, VENDOR_ADDRESS)
                VALUES (%s, %s, %s)
            """
            cursor.execute(insert_vendor_query, (new_user_id, vendor_name, vendor_address))

        conn.commit()

        return jsonify({"success": True, "message": "User registered successfully!"}), 201

    except MySQLError as err:
        if conn:
            conn.rollback()
        if err.errno == 1062:
            return jsonify({"success": False, "message": "Duplicate email or phone number detected."}), 400
        print(f"MySQL Error during registration: {err}")
        return jsonify({"success": False, "message": "A database error occurred during registration."}), 500

    except Exception as ex:
        if conn:
            conn.rollback()
        print(f"Unexpected Exception during registration: {ex}")
        return jsonify({"success": False, "message": "An internal server error occurred."}), 500

    finally:
        close_db_connection(conn, cursor)

@app.route('/api/login', methods=['POST'])
def api_login():
    """
    API endpoint for User Login.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    requested_role = (data.get('role') or '').strip().upper()

    if not email or not password or not requested_role:
        return jsonify({"success": False, "message": "Email, password, and role selection are required."}), 400

    if requested_role not in ['CUSTOMER', 'VENDOR']:
        return jsonify({"success": False, "message": "Invalid role specified."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        query = "SELECT USER_ID, FIRST_NAME, LAST_NAME, EMAIL, PASSWORD_HASH, ROLE FROM USERS WHERE EMAIL = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()

        generic_error = {"success": False, "message": "Invalid email, password, or role selection."}

        if not user:
            return jsonify(generic_error), 401

        if not check_password_hash(user['PASSWORD_HASH'], password):
            return jsonify(generic_error), 401

        if user['ROLE'] != requested_role:
            return jsonify(generic_error), 401

        session.clear()
        session['user_id'] = user['USER_ID']
        session['email'] = user['EMAIL']
        session['first_name'] = user['FIRST_NAME']
        session['role'] = user['ROLE']

        redirect_url = url_for('customer_dashboard') if user['ROLE'] == 'CUSTOMER' else url_for('vendor_dashboard')

        return jsonify({
            "success": True,
            "message": "Login successful.",
            "redirect_url": redirect_url
        }), 200

    except MySQLError as err:
        print(f"MySQL Error during login: {err}")
        return jsonify({"success": False, "message": "A database error occurred."}), 500

    except Exception as ex:
        print(f"Unexpected Exception during login: {ex}")
        return jsonify({"success": False, "message": "An internal server error occurred."}), 500

    finally:
        close_db_connection(conn, cursor)

@app.route('/api/customer/dashboard-data', methods=['GET'])
@role_required('CUSTOMER')
def api_customer_dashboard_data():
    """
    Returns statistics and recent deliveries specifically for the logged-in customer.
    """
    user_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        query_total_pkgs = "SELECT COUNT(*) AS total FROM PACKAGES WHERE USER_ID = %s"
        cursor.execute(query_total_pkgs, (user_id,))
        total_packages = cursor.fetchone()['total']

        query_ongoing = """
            SELECT COUNT(*) AS total 
            FROM MISSIONS m 
            JOIN PACKAGES p ON m.PACKAGE_ID = p.PACKAGE_ID 
            WHERE p.USER_ID = %s AND m.MISSION_STATUS = 'ONGOING'
        """
        cursor.execute(query_ongoing, (user_id,))
        ongoing_deliveries = cursor.fetchone()['total']

        query_completed = """
            SELECT COUNT(*) AS total 
            FROM MISSIONS m 
            JOIN PACKAGES p ON m.PACKAGE_ID = p.PACKAGE_ID 
            WHERE p.USER_ID = %s AND m.MISSION_STATUS = 'OVER'
        """
        cursor.execute(query_completed, (user_id,))
        completed_deliveries = cursor.fetchone()['total']

        query_recent = """
            SELECT 
                p.PACKAGE_ID,
                p.PRODUCT_ID,
                COALESCE(v.VENDOR_NAME, 'N/A') AS VENDOR_NAME,
                p.WEIGHT,
                p.PRIORITY,
                p.STATUS AS PACKAGE_STATUS,
                m.MISSION_ID,
                COALESCE(m.MISSION_STATUS, 'PENDING') AS MISSION_STATUS,
                COALESCE(r.SOURCE, 'N/A') AS SOURCE,
                COALESCE(r.DESTINATION, 'N/A') AS DESTINATION
            FROM PACKAGES p
            LEFT JOIN VENDORS v ON p.VENDOR_ID = v.VENDOR_ID
            LEFT JOIN MISSIONS m ON p.PACKAGE_ID = m.PACKAGE_ID
            LEFT JOIN ROUTES r ON m.ROUTE_ID = r.ROUTE_ID
            WHERE p.USER_ID = %s
            ORDER BY p.PACKAGE_ID DESC
            LIMIT 5
        """
        cursor.execute(query_recent, (user_id,))
        recent_deliveries = cursor.fetchall()

        return jsonify({
            "success": True,
            "first_name": session.get('first_name', 'Customer'),
            "stats": {
                "total_packages": total_packages,
                "ongoing_deliveries": ongoing_deliveries,
                "completed_deliveries": completed_deliveries
            },
            "recent_deliveries": recent_deliveries
        }), 200

    except MySQLError as err:
        print(f"MySQL Error in customer dashboard API: {err}")
        return jsonify({"success": False, "message": "Database error retrieving dashboard data."}), 500

    finally:
        close_db_connection(conn, cursor)

@app.route('/api/customer/my-packages', methods=['GET'])
@role_required('CUSTOMER')
def api_customer_my_packages():
    """
    Returns list of package IDs and product IDs belonging exclusively to the logged-in customer.
    """
    user_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        query = "SELECT PACKAGE_ID, PRODUCT_ID FROM PACKAGES WHERE USER_ID = %s ORDER BY PACKAGE_ID DESC"
        cursor.execute(query, (user_id,))
        packages = cursor.fetchall()

        return jsonify({"success": True, "packages": packages}), 200

    except MySQLError as err:
        print(f"MySQL Error fetching customer packages: {err}")
        return jsonify({"success": False, "message": "Database error fetching package list."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/customer/track/<int:package_id>', methods=['GET'])
@role_required('CUSTOMER')
def api_track_package(package_id):
    """
    Returns detailed package, mission, drone, and route tracking details ONLY if the package belongs to the logged-in customer.
    """
    user_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                p.PACKAGE_ID,
                p.PRODUCT_ID,
                p.WEIGHT,
                p.PRIORITY,
                p.STATUS AS PACKAGE_STATUS,
                COALESCE(v.VENDOR_NAME, 'Not available') AS VENDOR_NAME,
                m.MISSION_ID,
                COALESCE(m.MISSION_STATUS, 'Not available') AS MISSION_STATUS,
                m.START_TIME,
                m.END_TIME,
                d.DRONE_ID,
                COALESCE(d.CURR_LOCATION, 'Not available') AS DRONE_LOCATION,
                d.PAYLOAD_CAP AS DRONE_PAYLOAD_CAP,
                r.ROUTE_ID,
                COALESCE(r.SOURCE, 'Not available') AS SOURCE,
                COALESCE(r.DESTINATION, 'Not available') AS DESTINATION,
                r.DISTANCE,
                r.ESTIMATED_TIME
            FROM PACKAGES p
            LEFT JOIN VENDORS v ON p.VENDOR_ID = v.VENDOR_ID
            LEFT JOIN MISSIONS m ON p.PACKAGE_ID = m.PACKAGE_ID
            LEFT JOIN DRONES d ON m.DRONE_ID = d.DRONE_ID
            LEFT JOIN ROUTES r ON m.ROUTE_ID = r.ROUTE_ID
            WHERE p.PACKAGE_ID = %s AND p.USER_ID = %s
        """
        cursor.execute(query, (package_id, user_id))
        row = cursor.fetchone()

        if not row:
            return jsonify({"success": False, "message": "Package not found or access denied."}), 404

        package_details = {
            "package_id": row['PACKAGE_ID'],
            "product_id": row['PRODUCT_ID'],
            "weight": row['WEIGHT'],
            "priority": row['PRIORITY'],
            "package_status": row['PACKAGE_STATUS'] or 'AVAILABLE',
            "vendor_name": row['VENDOR_NAME'],
            "mission_id": row['MISSION_ID'] if row['MISSION_ID'] else 'Not available',
            "mission_status": row['MISSION_STATUS'],
            "start_time": str(row['START_TIME']) if row['START_TIME'] else 'Not available',
            "end_time": str(row['END_TIME']) if row['END_TIME'] else 'Not available',
            "drone_id": row['DRONE_ID'] if row['DRONE_ID'] else 'Not available',
            "drone_location": row['DRONE_LOCATION'],
            "drone_payload_cap": row['DRONE_PAYLOAD_CAP'] if row['DRONE_PAYLOAD_CAP'] is not None else 'Not available',
            "route_id": row['ROUTE_ID'] if row['ROUTE_ID'] else 'Not available',
            "source": row['SOURCE'],
            "destination": row['DESTINATION'],
            "distance": str(row['DISTANCE']) if row['DISTANCE'] is not None else 'Not available',
            "estimated_time": row['ESTIMATED_TIME'] if row['ESTIMATED_TIME'] is not None else 'Not available'
        }

        return jsonify({"success": True, "package": package_details}), 200

    except MySQLError as err:
        print(f"MySQL Error tracking package: {err}")
        return jsonify({"success": False, "message": "Database error tracking package."}), 500

    finally:
        close_db_connection(conn, cursor)

@app.route('/api/customer/packages', methods=['POST'])
@role_required('CUSTOMER')
def api_create_package():
    """
    API Endpoint allowing the logged-in customer to create a package delivery request.
    """
    user_id = session.get('user_id')
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    try:
        vendor_id = int(data.get('vendor_id'))
        product_id = int(data.get('product_id'))
        weight = int(data.get('weight'))
        priority = int(data.get('priority'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Vendor ID, Product ID, Weight, and Priority must be valid integers."}), 400

    if vendor_id <= 0 or product_id <= 0 or weight <= 0 or priority <= 0:
        return jsonify({"success": False, "message": "Vendor ID, Product ID, Weight, and Priority must be positive values."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        vendor_query = "SELECT VENDOR_ID FROM VENDORS WHERE VENDOR_ID = %s"
        cursor.execute(vendor_query, (vendor_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "Selected vendor does not exist."}), 400

        id_query = "SELECT COALESCE(MAX(PACKAGE_ID), 0) + 1 AS next_id FROM PACKAGES"
        cursor.execute(id_query)
        next_package_id = cursor.fetchone()['next_id']

        insert_query = """
            INSERT INTO PACKAGES (PACKAGE_ID, USER_ID, VENDOR_ID, PRODUCT_ID, WEIGHT, PRIORITY, STATUS)
            VALUES (%s, %s, %s, %s, %s, %s, 'AVAILABLE')
        """
        cursor.execute(insert_query, (next_package_id, user_id, vendor_id, product_id, weight, priority))
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Package delivery request created successfully!",
            "package_id": next_package_id
        }), 201

    except MySQLError as err:
        if conn:
            conn.rollback()
        if err.errno == 1062:
            return jsonify({"success": False, "message": "Product ID is already registered for this Vendor."}), 400
        if err.errno == 1452:
            return jsonify({"success": False, "message": "Referenced Vendor or User does not exist."}), 400
        print(f"MySQL Error creating package: {err}")
        return jsonify({"success": False, "message": "Database error creating delivery request."}), 500

    finally:
        close_db_connection(conn, cursor)

@app.route('/api/vendor/dashboard-data', methods=['GET'])
@role_required('VENDOR')
def api_vendor_dashboard_data():
    """
    Returns profile information, package statistics, and package inventory exclusively for the logged-in vendor.
    """
    vendor_user_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        vendor_query = """
            SELECT 
                v.VENDOR_ID,
                v.VENDOR_NAME,
                v.VENDOR_ADDRESS,
                u.FIRST_NAME,
                u.LAST_NAME,
                u.EMAIL,
                u.PHONE_NO
            FROM USERS u
            LEFT JOIN VENDORS v ON u.USER_ID = v.VENDOR_ID
            WHERE u.USER_ID = %s AND u.ROLE = 'VENDOR'
        """
        cursor.execute(vendor_query, (vendor_user_id,))
        vendor_info = cursor.fetchone()

        if not vendor_info:
            return jsonify({"success": False, "message": "Vendor account record not found."}), 404

        vendor_data = {
            "vendor_id": vendor_info['VENDOR_ID'] or vendor_user_id,
            "vendor_name": vendor_info['VENDOR_NAME'] or f"{vendor_info['FIRST_NAME']} {vendor_info['LAST_NAME']} Store",
            "vendor_address": vendor_info['VENDOR_ADDRESS'] or "Not specified",
            "contact_name": f"{vendor_info['FIRST_NAME']} {vendor_info['LAST_NAME']}",
            "email": vendor_info['EMAIL'],
            "phone_no": vendor_info['PHONE_NO']
        }

        query_total = "SELECT COUNT(*) AS total FROM PACKAGES WHERE VENDOR_ID = %s"
        cursor.execute(query_total, (vendor_user_id,))
        total_packages = cursor.fetchone()['total']

        query_available = "SELECT COUNT(*) AS total FROM PACKAGES WHERE VENDOR_ID = %s AND STATUS = 'AVAILABLE'"
        cursor.execute(query_available, (vendor_user_id,))
        available_packages = cursor.fetchone()['total']

        query_dispatched = "SELECT COUNT(*) AS total FROM PACKAGES WHERE VENDOR_ID = %s AND STATUS != 'AVAILABLE'"
        cursor.execute(query_dispatched, (vendor_user_id,))
        dispatched_packages = cursor.fetchone()['total']

        packages_query = """
            SELECT 
                p.PACKAGE_ID,
                p.PRODUCT_ID,
                p.WEIGHT,
                p.PRIORITY,
                p.STATUS,
                CONCAT(u.FIRST_NAME, ' ', u.LAST_NAME) AS CUSTOMER_NAME,
                u.EMAIL AS CUSTOMER_EMAIL
            FROM PACKAGES p
            JOIN USERS u ON p.USER_ID = u.USER_ID
            WHERE p.VENDOR_ID = %s
            ORDER BY p.PACKAGE_ID DESC
            LIMIT 20
        """
        cursor.execute(packages_query, (vendor_user_id,))
        vendor_packages = cursor.fetchall()

        return jsonify({
            "success": True,
            "vendor": vendor_data,
            "stats": {
                "total_packages": total_packages,
                "available_packages": available_packages,
                "dispatched_packages": dispatched_packages
            },
            "packages": vendor_packages
        }), 200

    except MySQLError as err:
        print(f"MySQL Error in vendor dashboard API: {err}")
        return jsonify({"success": False, "message": "Database error retrieving vendor dashboard data."}), 500

    finally:
        close_db_connection(conn, cursor)

@app.route('/api/profile', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_profile():
    """
    API endpoint for viewing, updating, and deleting the logged-in user's profile.
    Supports vendor business info (VENDOR_NAME, VENDOR_ADDRESS) when role is VENDOR.
    """
    user_id = session.get('user_id')
    user_role = session.get('role')
    conn = None
    cursor = None

    if request.method == 'GET':
        try:
            conn = get_db_connection(use_database=True)
            if not conn or not conn.is_connected():
                return jsonify({"success": False, "message": "Database connection failed."}), 500

            cursor = conn.cursor(dictionary=True)
            query = "SELECT USER_ID, FIRST_NAME, LAST_NAME, EMAIL, PHONE_NO, ROLE, CREATED_AT FROM USERS WHERE USER_ID = %s"
            cursor.execute(query, (user_id,))
            user = cursor.fetchone()

            if not user:
                session.clear()
                return jsonify({"success": False, "message": "User record not found."}), 404

            if user.get('CREATED_AT'):
                user['created_at'] = str(user['CREATED_AT'])
            
            user_data = {
                "user_id": user['USER_ID'],
                "first_name": user['FIRST_NAME'],
                "last_name": user['LAST_NAME'],
                "email": user['EMAIL'],
                "phone_no": user['PHONE_NO'],
                "role": user['ROLE'],
                "created_at": user.get('created_at', '')
            }

            # Retrieve VENDOR profile fields if logged-in user is a VENDOR
            if user['ROLE'] == 'VENDOR':
                vendor_query = "SELECT VENDOR_NAME, VENDOR_ADDRESS FROM VENDORS WHERE VENDOR_ID = %s"
                cursor.execute(vendor_query, (user_id,))
                vendor = cursor.fetchone()
                if vendor:
                    user_data["vendor_name"] = vendor['VENDOR_NAME']
                    user_data["vendor_address"] = vendor['VENDOR_ADDRESS']
                else:
                    user_data["vendor_name"] = ""
                    user_data["vendor_address"] = ""

            return jsonify({"success": True, "user": user_data}), 200

        except MySQLError as err:
            print(f"MySQL Error fetching profile: {err}")
            return jsonify({"success": False, "message": "A database error occurred."}), 500
        finally:
            close_db_connection(conn, cursor)

    elif request.method == 'PUT':
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Invalid request payload."}), 400

        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        phone_no = (data.get('phone_no') or '').strip()
        vendor_name = (data.get('vendor_name') or '').strip()
        vendor_address = (data.get('vendor_address') or '').strip()

        if not first_name or not last_name or not phone_no:
            return jsonify({"success": False, "message": "First name, last name, and phone number are required."}), 400

        if len(first_name) > 25 or len(last_name) > 25:
            return jsonify({"success": False, "message": "First name and last name must not exceed 25 characters."}), 400

        if not PHONE_REGEX.match(phone_no):
            return jsonify({"success": False, "message": "Phone number must be exactly 10 digits."}), 400

        # Vendor specific validations
        if user_role == 'VENDOR':
            if not vendor_name:
                return jsonify({"success": False, "message": "Vendor Business Name is required."}), 400
            if len(vendor_name) > 50:
                return jsonify({"success": False, "message": "Vendor Business Name must not exceed 50 characters."}), 400
            if not vendor_address:
                return jsonify({"success": False, "message": "Vendor Business Address is required."}), 400
            if len(vendor_address) > 100:
                return jsonify({"success": False, "message": "Vendor Business Address must not exceed 100 characters."}), 400

        try:
            conn = get_db_connection(use_database=True)
            if not conn or not conn.is_connected():
                return jsonify({"success": False, "message": "Database connection failed."}), 500

            cursor = conn.cursor(dictionary=True)

            check_query = "SELECT USER_ID FROM USERS WHERE PHONE_NO = %s AND USER_ID != %s"
            cursor.execute(check_query, (phone_no, user_id))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Phone number is already in use by another account."}), 400

            # Step 1: Update USERS table
            update_user_query = """
                UPDATE USERS 
                SET FIRST_NAME = %s, LAST_NAME = %s, PHONE_NO = %s 
                WHERE USER_ID = %s
            """
            cursor.execute(update_user_query, (first_name, last_name, phone_no, user_id))

            # Step 2: Update VENDORS table if user is a VENDOR (Single Transaction)
            if user_role == 'VENDOR':
                update_vendor_query = """
                    UPDATE VENDORS
                    SET VENDOR_NAME = %s, VENDOR_ADDRESS = %s
                    WHERE VENDOR_ID = %s
                """
                cursor.execute(update_vendor_query, (vendor_name, vendor_address, user_id))

            # Commit atomic transaction
            conn.commit()

            session['first_name'] = first_name

            return jsonify({"success": True, "message": "Profile updated successfully!"}), 200

        except MySQLError as err:
            if conn:
                conn.rollback()
            if err.errno == 1062:
                return jsonify({"success": False, "message": "Phone number is already registered."}), 400
            print(f"MySQL Error updating profile: {err}")
            return jsonify({"success": False, "message": "A database error occurred during profile update."}), 500

        finally:
            close_db_connection(conn, cursor)

    elif request.method == 'DELETE':
        try:
            conn = get_db_connection(use_database=True)
            if not conn or not conn.is_connected():
                return jsonify({"success": False, "message": "Database connection failed."}), 500

            cursor = conn.cursor()

            # Transactional deletion for vendor and user
            if user_role == 'VENDOR':
                delete_vendor_query = "DELETE FROM VENDORS WHERE VENDOR_ID = %s"
                cursor.execute(delete_vendor_query, (user_id,))

            delete_user_query = "DELETE FROM USERS WHERE USER_ID = %s"
            cursor.execute(delete_user_query, (user_id,))
            
            conn.commit()
            session.clear()

            return jsonify({"success": True, "message": "Account deleted successfully.", "redirect_url": url_for('home')}), 200

        except MySQLError as err:
            if conn:
                conn.rollback()
            if err.errno == 1451:
                return jsonify({"success": False, "message": "Cannot delete vendor account while associated packages exist."}), 400
            print(f"MySQL Error deleting account: {err}")
            return jsonify({"success": False, "message": "A database error occurred while deleting account."}), 500

        finally:
            close_db_connection(conn, cursor)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Logs out the user by destroying the Flask session and redirecting to login.
    """
    session.clear()
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({"success": True, "message": "Logged out successfully.", "redirect_url": url_for('home')}), 200
    return redirect(url_for('home'))

# -----------------------------------------------------
# Operational Master Data APIs: Drones
# -----------------------------------------------------
@app.route('/api/drones', methods=['GET'])
@role_required('VENDOR')
def api_get_drones():
    """
    Retrieves all registered drones from the database.
    Restricted to VENDOR role.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DRONE_ID, PAYLOAD_CAP, CURR_LOCATION, PURCHASE_DATE, LAST_DELIVERY 
            FROM DRONES 
            ORDER BY DRONE_ID ASC
        """)
        drones = cursor.fetchall()
        for d in drones:
            d['PURCHASE_DATE'] = str(d['PURCHASE_DATE']) if d.get('PURCHASE_DATE') else None
            d['LAST_DELIVERY'] = str(d['LAST_DELIVERY']) if d.get('LAST_DELIVERY') else None

        return jsonify({"success": True, "drones": drones}), 200
    except MySQLError as err:
        print(f"MySQL Error fetching drones: {err}")
        return jsonify({"success": False, "message": "Database error fetching drones."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/drones', methods=['POST'])
@role_required('VENDOR')
def api_create_drone():
    """
    Registers a new drone airframe in the fleet.
    - DRONE_ID must be a unique positive integer.
    - PAYLOAD_CAP must be a positive integer (in kg).
    - CURR_LOCATION must be non-empty (max 100 characters).
    - PURCHASE_DATE must be a valid date YYYY-MM-DD (defaults to CURDATE()).
    - LAST_DELIVERY is initialized to NOW() (or purchase timestamp) to satisfy the schema's
      NOT NULL constraint on DRONES.LAST_DELIVERY without fabricating false delivery history.
      It represents the baseline commissioning timestamp until the first delivery is completed.
    Restricted to VENDOR role.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    raw_drone_id = data.get('drone_id')
    raw_payload_cap = data.get('payload_cap')
    curr_location = (data.get('curr_location') or '').strip()
    purchase_date_str = (data.get('purchase_date') or '').strip()

    try:
        drone_id = int(raw_drone_id)
        payload_cap = int(raw_payload_cap)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Drone ID and Payload Capacity must be valid integers."}), 400

    if drone_id <= 0:
        return jsonify({"success": False, "message": "Drone ID must be a positive integer."}), 400
    if payload_cap <= 0:
        return jsonify({"success": False, "message": "Payload Capacity must be a positive integer (kg)."}), 400
    if not curr_location:
        return jsonify({"success": False, "message": "Current Location is required."}), 400
    if len(curr_location) > 100:
        return jsonify({"success": False, "message": "Current Location must not exceed 100 characters."}), 400

    valid_purchase_date = None
    if purchase_date_str:
        if not DATE_REGEX.match(purchase_date_str):
            return jsonify({"success": False, "message": "Purchase Date must follow YYYY-MM-DD format."}), 400
        try:
            valid_purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"success": False, "message": "Invalid calendar date for Purchase Date."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        # Check for existing duplicate Drone ID
        cursor.execute("SELECT DRONE_ID FROM DRONES WHERE DRONE_ID = %s", (drone_id,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": f"Drone ID {drone_id} is already registered in the database."}), 400

        if valid_purchase_date:
            insert_query = """
                INSERT INTO DRONES (DRONE_ID, PAYLOAD_CAP, CURR_LOCATION, PURCHASE_DATE, LAST_DELIVERY)
                VALUES (%s, %s, %s, %s, NOW())
            """
            cursor.execute(insert_query, (drone_id, payload_cap, curr_location, valid_purchase_date))
        else:
            insert_query = """
                INSERT INTO DRONES (DRONE_ID, PAYLOAD_CAP, CURR_LOCATION, PURCHASE_DATE, LAST_DELIVERY)
                VALUES (%s, %s, %s, CURDATE(), NOW())
            """
            cursor.execute(insert_query, (drone_id, payload_cap, curr_location))

        # Auto-provision an operational commissioning battery so the drone is flight-ready
        cursor.execute("SELECT COALESCE(MAX(BATTERY_ID), 0) + 1 AS next_bat_id FROM BATTERIES")
        next_bat_id = cursor.fetchone()['next_bat_id']
        cursor.execute("""
            INSERT INTO BATTERIES (BATTERY_ID, DRONE_ID, CAPACITY, CYCLES, STATUS)
            VALUES (%s, %s, 5000, 0, 'GOOD')
        """, (next_bat_id, drone_id))

        # Auto-log baseline commissioning maintenance check
        cursor.execute("""
            INSERT INTO MAINTENACE (DRONE_ID, STATUS, REPAIR_DATE, COST, REASON)
            VALUES (%s, 'GOOD', CURDATE(), 100, 'Commissioning inspection passed')
        """, (drone_id,))

        conn.commit()

        return jsonify({
            "success": True, 
            "message": f"Drone #{drone_id} registered successfully!",
            "drone": {
                "drone_id": drone_id,
                "payload_cap": payload_cap,
                "curr_location": curr_location,
                "purchase_date": str(valid_purchase_date) if valid_purchase_date else str(date.today())
            }
        }), 201

    except MySQLError as err:
        if conn:
            conn.rollback()
        if err.errno == 1062:
            return jsonify({"success": False, "message": f"Drone ID {drone_id} already exists."}), 400
        print(f"MySQL Error creating drone: {err}")
        return jsonify({"success": False, "message": "Database error creating drone."}), 500
    finally:
        close_db_connection(conn, cursor)

# -----------------------------------------------------
# Operational Master Data APIs: Pilots
# -----------------------------------------------------
@app.route('/api/pilots', methods=['GET'])
@role_required('VENDOR')
def api_get_pilots():
    """
    Retrieves all pilot records from the database.
    Restricted to VENDOR role.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT PILOT_ID, PILOT_NAME, LICENSE_NUMBER, PHONE_NO, STATUS 
            FROM PILOTS 
            ORDER BY PILOT_ID ASC
        """)
        pilots = cursor.fetchall()
        return jsonify({"success": True, "pilots": pilots}), 200
    except MySQLError as err:
        print(f"MySQL Error fetching pilots: {err}")
        return jsonify({"success": False, "message": "Database error fetching pilots."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/pilots', methods=['POST'])
@role_required('VENDOR')
def api_create_pilot():
    """
    Registers a new certified pilot using auto-increment PILOT_ID.
    - PILOT_NAME max 50 chars.
    - LICENSE_NUMBER unique, max 50 chars.
    - PHONE_NO exactly 10 digits (matching DDL CHECK regex ^[0-9]{10}$).
    - STATUS must be 'AVAILABLE' or 'OFF_DUTY' (defaults to 'AVAILABLE').
    Restricted to VENDOR role.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    pilot_name = (data.get('pilot_name') or '').strip()
    license_number = (data.get('license_number') or '').strip().upper()
    phone_no = (data.get('phone_no') or '').strip()
    status = (data.get('status') or 'AVAILABLE').strip().upper()

    if not pilot_name or not license_number or not phone_no:
        return jsonify({"success": False, "message": "Pilot name, license number, and phone number are required."}), 400

    if len(pilot_name) > 50:
        return jsonify({"success": False, "message": "Pilot name must not exceed 50 characters."}), 400
    if len(license_number) > 50:
        return jsonify({"success": False, "message": "License number must not exceed 50 characters."}), 400
    if not PHONE_REGEX.match(phone_no):
        return jsonify({"success": False, "message": "Phone number must be exactly 10 digits."}), 400

    if status not in ['AVAILABLE', 'OFF_DUTY']:
        return jsonify({"success": False, "message": "Initial pilot status must be 'AVAILABLE' or 'OFF_DUTY'."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        # Check unique license number and phone number
        cursor.execute("SELECT PILOT_ID, LICENSE_NUMBER, PHONE_NO FROM PILOTS WHERE LICENSE_NUMBER = %s OR PHONE_NO = %s", (license_number, phone_no))
        existing = cursor.fetchall()
        for p in existing:
            if p['LICENSE_NUMBER'] == license_number:
                return jsonify({"success": False, "message": f"License number '{license_number}' is already registered."}), 400
            if p['PHONE_NO'] == phone_no:
                return jsonify({"success": False, "message": f"Phone number '{phone_no}' is already registered to another pilot."}), 400

        insert_query = """
            INSERT INTO PILOTS (PILOT_NAME, LICENSE_NUMBER, PHONE_NO, STATUS)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(insert_query, (pilot_name, license_number, phone_no, status))
        conn.commit()
        new_pilot_id = cursor.lastrowid

        return jsonify({
            "success": True, 
            "message": f"Pilot '{pilot_name}' registered successfully!",
            "pilot_id": new_pilot_id,
            "pilot": {
                "pilot_id": new_pilot_id,
                "pilot_name": pilot_name,
                "license_number": license_number,
                "phone_no": phone_no,
                "status": status
            }
        }), 201

    except MySQLError as err:
        if conn:
            conn.rollback()
        if err.errno == 1062:
            return jsonify({"success": False, "message": "License number or phone number already exists."}), 400
        print(f"MySQL Error creating pilot: {err}")
        return jsonify({"success": False, "message": "Database error creating pilot."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/pilots/<int:pilot_id>/status', methods=['PUT'])
@role_required('VENDOR')
def api_update_pilot_status(pilot_id):
    """
    Updates a pilot's duty status between 'AVAILABLE' and 'OFF_DUTY'.
    - Manual transition to 'ON_MISSION' is forbidden.
    - Pilots currently on mission or assigned to active/pending missions cannot be set to 'OFF_DUTY'.
    Restricted to VENDOR role.
    """
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({"success": False, "message": "Status field is required."}), 400

    new_status = str(data.get('status')).strip().upper()
    if new_status not in ['AVAILABLE', 'OFF_DUTY']:
        return jsonify({
            "success": False, 
            "message": "Status can only be toggled between 'AVAILABLE' and 'OFF_DUTY'. 'ON_MISSION' is managed exclusively by mission dispatch."
        }), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT PILOT_ID, PILOT_NAME, STATUS FROM PILOTS WHERE PILOT_ID = %s", (pilot_id,))
        pilot = cursor.fetchone()
        if not pilot:
            conn.rollback()
            return jsonify({"success": False, "message": f"Pilot #{pilot_id} not found."}), 404

        current_status = pilot['STATUS']
        if current_status == 'ON_MISSION':
            conn.rollback()
            return jsonify({
                "success": False, 
                "message": f"Cannot alter duty status of Pilot #{pilot_id} while currently flying an active mission (ON_MISSION)."
            }), 400

        # If switching to OFF_DUTY, verify pilot is not assigned to any active (IDLE or ONGOING) mission
        if new_status == 'OFF_DUTY':
            cursor.execute("""
                SELECT MISSION_ID, MISSION_STATUS 
                FROM MISSIONS 
                WHERE PILOT_ID = %s AND MISSION_STATUS IN ('IDLE', 'ONGOING')
            """, (pilot_id,))
            active_mission = cursor.fetchone()
            if active_mission:
                conn.rollback()
                return jsonify({
                    "success": False, 
                    "message": f"Cannot set Pilot #{pilot_id} to OFF_DUTY while assigned to active Mission #{active_mission['MISSION_ID']} ({active_mission['MISSION_STATUS']})."
                }), 400

        cursor.execute("UPDATE PILOTS SET STATUS = %s WHERE PILOT_ID = %s", (new_status, pilot_id))
        conn.commit()

        return jsonify({
            "success": True, 
            "message": f"Pilot #{pilot_id} ({pilot['PILOT_NAME']}) status updated from {current_status} to {new_status}."
        }), 200

    except MySQLError as err:
        if conn:
            conn.rollback()
        print(f"MySQL Error updating pilot status: {err}")
        return jsonify({"success": False, "message": "Database error updating pilot status."}), 500
    finally:
        close_db_connection(conn, cursor)

# -----------------------------------------------------
# Operational Master Data APIs: Routes
# -----------------------------------------------------
@app.route('/api/routes', methods=['GET'])
@role_required('VENDOR')
def api_get_routes():
    """
    Retrieves all delivery route corridors from the database.
    Restricted to VENDOR role.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT ROUTE_ID, SOURCE, DESTINATION, DISTANCE, ESTIMATED_TIME 
            FROM ROUTES 
            ORDER BY ROUTE_ID ASC
        """)
        routes = cursor.fetchall()
        for r in routes:
            r['DISTANCE'] = float(r['DISTANCE']) if r.get('DISTANCE') is not None else None

        return jsonify({"success": True, "routes": routes}), 200
    except MySQLError as err:
        print(f"MySQL Error fetching routes: {err}")
        return jsonify({"success": False, "message": "Database error fetching routes."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/routes', methods=['POST'])
@role_required('VENDOR')
def api_create_route():
    """
    Registers a new delivery corridor in the database.
    - ROUTE_ID must be a positive integer (auto-computed if omitted).
    - SOURCE and DESTINATION must be non-empty (max 25 characters).
    - DISTANCE must be a positive decimal/float (in km).
    - ESTIMATED_TIME must be a positive integer (in minutes).
    Restricted to VENDOR role.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    raw_route_id = data.get('route_id')
    source = (data.get('source') or '').strip()
    destination = (data.get('destination') or '').strip()
    raw_distance = data.get('distance')
    raw_time = data.get('estimated_time')

    if not source or not destination:
        return jsonify({"success": False, "message": "Source and Destination waypoints are required."}), 400

    if len(source) > 25:
        return jsonify({"success": False, "message": "Source waypoint must not exceed 25 characters."}), 400
    if len(destination) > 25:
        return jsonify({"success": False, "message": "Destination waypoint must not exceed 25 characters."}), 400

    try:
        distance = float(raw_distance)
        estimated_time = int(raw_time)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Distance must be a valid number and Estimated Time must be a valid integer."}), 400

    if distance <= 0:
        return jsonify({"success": False, "message": "Distance must be greater than zero."}), 400
    if estimated_time <= 0:
        return jsonify({"success": False, "message": "Estimated Time must be greater than zero."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        if raw_route_id is not None and str(raw_route_id).strip() != "":
            try:
                target_route_id = int(raw_route_id)
                if target_route_id <= 0:
                    return jsonify({"success": False, "message": "Route ID must be a positive integer."}), 400
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": "Route ID must be a valid integer."}), 400

            cursor.execute("SELECT ROUTE_ID FROM ROUTES WHERE ROUTE_ID = %s", (target_route_id,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": f"Route ID {target_route_id} already exists."}), 400
        else:
            cursor.execute("SELECT COALESCE(MAX(ROUTE_ID), 0) + 1 AS next_id FROM ROUTES")
            target_route_id = cursor.fetchone()['next_id']

        insert_query = """
            INSERT INTO ROUTES (ROUTE_ID, SOURCE, DESTINATION, DISTANCE, ESTIMATED_TIME)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (target_route_id, source, destination, distance, estimated_time))
        conn.commit()

        return jsonify({
            "success": True, 
            "message": f"Route #{target_route_id} ({source} -> {destination}) registered successfully!",
            "route_id": target_route_id,
            "route": {
                "route_id": target_route_id,
                "source": source,
                "destination": destination,
                "distance": distance,
                "estimated_time": estimated_time
            }
        }), 201

    except MySQLError as err:
        if conn:
            conn.rollback()
        if err.errno == 1062:
            return jsonify({"success": False, "message": f"Route ID {target_route_id} already exists."}), 400
        print(f"MySQL Error creating route: {err}")
        return jsonify({"success": False, "message": "Database error creating route."}), 500
    finally:
        close_db_connection(conn, cursor)


# -----------------------------------------------------
# Mission Management API Endpoints
# -----------------------------------------------------
@app.route('/api/missions/options', methods=['GET'])
@role_required('VENDOR')
def api_get_mission_options():
    """
    Returns available drones, pilots, packages, and routes for creating/updating missions.
    Strictly isolated: only returns packages belonging to the logged-in vendor,
    and returns flight-ready drones (not actively charging, not grounded in maintenance, healthy battery).
    """
    vendor_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        # 1. Eligible Drones: has GOOD battery, not charging, not in BAD maintenance, not in active mission
        drone_query = """
            SELECT d.DRONE_ID, d.PAYLOAD_CAP, d.CURR_LOCATION 
            FROM DRONES d
            WHERE d.DRONE_ID NOT IN (
                SELECT DRONE_ID FROM MISSIONS WHERE MISSION_STATUS IN ('IDLE', 'ONGOING')
            )
            AND EXISTS (
                SELECT 1 FROM BATTERIES b WHERE b.DRONE_ID = d.DRONE_ID AND b.STATUS = 'GOOD'
            )
            AND NOT EXISTS (
                SELECT 1 FROM CHARGING_SESSIONS cs
                JOIN BATTERIES b ON cs.BATTERY_ID = b.BATTERY_ID
                WHERE b.DRONE_ID = d.DRONE_ID AND cs.END_TIME IS NULL
            )
            AND NOT EXISTS (
                SELECT 1 FROM MAINTENACE m 
                WHERE m.DRONE_ID = d.DRONE_ID 
                  AND m.MAINTENANCE_ID = (
                      SELECT m2.MAINTENANCE_ID FROM MAINTENACE m2 
                      WHERE m2.DRONE_ID = d.DRONE_ID 
                      ORDER BY m2.REPAIR_DATE DESC, m2.MAINTENANCE_ID DESC 
                      LIMIT 1
                  )
                  AND m.STATUS = 'BAD'
            )
            ORDER BY d.DRONE_ID ASC
        """
        cursor.execute(drone_query)
        drones = cursor.fetchall()

        # 2. Available Pilots: AVAILABLE status, not in active mission
        pilot_query = """
            SELECT PILOT_ID, PILOT_NAME, LICENSE_NUMBER, PHONE_NO, STATUS 
            FROM PILOTS 
            WHERE STATUS = 'AVAILABLE'
              AND PILOT_ID NOT IN (
                  SELECT PILOT_ID FROM MISSIONS WHERE MISSION_STATUS IN ('IDLE', 'ONGOING')
              )
            ORDER BY PILOT_NAME ASC
        """
        cursor.execute(pilot_query)
        pilots = cursor.fetchall()

        # 3. Available Packages: Belonging strictly to the logged-in vendor, not in active mission
        package_query = """
            SELECT PACKAGE_ID, PRODUCT_ID, USER_ID, WEIGHT, PRIORITY, STATUS 
            FROM PACKAGES 
            WHERE VENDOR_ID = %s 
              AND STATUS IN ('AVAILABLE', 'REQUESTED', 'READY')
              AND PACKAGE_ID NOT IN (
                  SELECT PACKAGE_ID FROM MISSIONS WHERE MISSION_STATUS IN ('IDLE', 'ONGOING')
              )
            ORDER BY PACKAGE_ID DESC
        """
        cursor.execute(package_query, (vendor_id,))
        packages = cursor.fetchall()

        # 4. Active Routes
        cursor.execute("SELECT ROUTE_ID, SOURCE, DESTINATION, DISTANCE, ESTIMATED_TIME FROM ROUTES ORDER BY ROUTE_ID ASC")
        routes = cursor.fetchall()

        return jsonify({
            "success": True,
            "drones": drones,
            "pilots": pilots,
            "packages": packages,
            "routes": routes
        }), 200

    except MySQLError as err:
        print(f"MySQL Error fetching mission options: {err}")
        return jsonify({"success": False, "message": "Database error fetching mission options."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/missions', methods=['GET'])
@role_required('VENDOR')
def api_get_missions():
    """
    Returns list of all missions belonging to the logged-in vendor.
    """
    vendor_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                m.MISSION_ID,
                m.DRONE_ID,
                m.PILOT_ID,
                p_pilot.PILOT_NAME,
                p_pilot.STATUS AS PILOT_STATUS,
                m.PACKAGE_ID,
                m.ROUTE_ID,
                r.SOURCE,
                r.DESTINATION,
                m.MISSION_STATUS,
                m.START_TIME,
                m.END_TIME
            FROM MISSIONS m
            LEFT JOIN PILOTS p_pilot ON m.PILOT_ID = p_pilot.PILOT_ID
            LEFT JOIN DRONES d ON m.DRONE_ID = d.DRONE_ID
            LEFT JOIN PACKAGES p ON m.PACKAGE_ID = p.PACKAGE_ID
            LEFT JOIN ROUTES r ON m.ROUTE_ID = r.ROUTE_ID
            WHERE p.VENDOR_ID = %s
            ORDER BY m.MISSION_ID DESC
        """
        cursor.execute(query, (vendor_id,))
        missions = cursor.fetchall()

        for m in missions:
            m['START_TIME'] = str(m['START_TIME']) if m.get('START_TIME') else None
            m['END_TIME'] = str(m['END_TIME']) if m.get('END_TIME') else None

        return jsonify({"success": True, "missions": missions}), 200

    except MySQLError as err:
        print(f"MySQL Error fetching missions: {err}")
        return jsonify({"success": False, "message": "Database error fetching missions."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/missions/<int:mission_id>', methods=['GET'])
@role_required('VENDOR')
def api_get_mission(mission_id):
    """
    Returns detailed mission object for a specific mission_id, enforcing vendor ownership.
    """
    vendor_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                m.MISSION_ID,
                m.DRONE_ID,
                m.PILOT_ID,
                p_pilot.PILOT_NAME,
                p_pilot.STATUS AS PILOT_STATUS,
                m.PACKAGE_ID,
                m.ROUTE_ID,
                r.SOURCE,
                r.DESTINATION,
                m.MISSION_STATUS,
                m.START_TIME,
                m.END_TIME,
                p.VENDOR_ID
            FROM MISSIONS m
            LEFT JOIN PILOTS p_pilot ON m.PILOT_ID = p_pilot.PILOT_ID
            LEFT JOIN DRONES d ON m.DRONE_ID = d.DRONE_ID
            LEFT JOIN PACKAGES p ON m.PACKAGE_ID = p.PACKAGE_ID
            LEFT JOIN ROUTES r ON m.ROUTE_ID = r.ROUTE_ID
            WHERE m.MISSION_ID = %s
        """
        cursor.execute(query, (mission_id,))
        mission = cursor.fetchone()

        if not mission:
            return jsonify({"success": False, "message": "Mission not found."}), 404

        if mission.get('VENDOR_ID') and mission['VENDOR_ID'] != vendor_id:
            return jsonify({"success": False, "message": "Access Denied: Mission belongs to another vendor."}), 403

        mission['START_TIME'] = str(mission['START_TIME']) if mission.get('START_TIME') else None
        mission['END_TIME'] = str(mission['END_TIME']) if mission.get('END_TIME') else None

        return jsonify({"success": True, "mission": mission}), 200

    except MySQLError as err:
        print(f"MySQL Error fetching mission detail: {err}")
        return jsonify({"success": False, "message": "Database error fetching mission."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/missions', methods=['POST'])
@role_required('VENDOR')
def api_create_mission():
    """
    Creates a new mission in 'IDLE' state using stored procedure sp_create_mission.
    Enforces payload capacity, vendor ownership, healthy batteries, no active charging,
    no maintenance grounding, and double-booking prevention atomically.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    vendor_id = session.get('user_id')
    raw_mission_id = data.get('mission_id')
    try:
        drone_id = int(data.get('drone_id'))
        pilot_id = int(data.get('pilot_id'))
        package_id = int(data.get('package_id'))
        route_id = int(data.get('route_id'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Drone ID, Pilot ID, Package ID, and Route ID must be valid integers."}), 400

    custom_mission_id = None
    if raw_mission_id is not None and str(raw_mission_id).strip() != "":
        try:
            custom_mission_id = int(raw_mission_id)
            if custom_mission_id <= 0:
                return jsonify({"success": False, "message": "Mission ID must be a positive integer."}), 400
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Mission ID must be a valid integer."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor()
        args = (drone_id, pilot_id, package_id, route_id, vendor_id, custom_mission_id, 0, 0, ' ' * 255)
        result = cursor.callproc('sp_create_mission', args)
        target_mission_id = result[6]
        status_code = result[7]
        status_message = result[8].strip()

        if status_code in [200, 201]:
            return jsonify({
                "success": True,
                "message": status_message,
                "mission_id": target_mission_id
            }), 201
        else:
            return jsonify({
                "success": False,
                "message": status_message
            }), status_code

    except MySQLError as err:
        error_msg = err.msg if hasattr(err, 'msg') else str(err)
        return jsonify({"success": False, "message": error_msg}), 400
    except Exception as ex:
        print(f"Unexpected Exception creating mission: {ex}")
        return jsonify({"success": False, "message": "An internal server error occurred."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/missions/<int:mission_id>', methods=['PUT'])
@role_required('VENDOR')
def api_update_mission(mission_id):
    """
    Updates assignments (drone, pilot, package, route) for an existing IDLE mission.
    Enforces payload capacity, vendor ownership, pilot availability, and battery/maintenance invariants.
    Completed (OVER) and CANCELLED missions cannot be modified.
    """
    vendor_id = session.get('user_id')
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    try:
        drone_id = int(data.get('drone_id'))
        pilot_id = int(data.get('pilot_id'))
        package_id = int(data.get('package_id'))
        route_id = int(data.get('route_id'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Drone ID, Pilot ID, Package ID, and Route ID must be valid integers."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT MISSION_ID, DRONE_ID, PILOT_ID, PACKAGE_ID, MISSION_STATUS FROM MISSIONS WHERE MISSION_ID = %s", (mission_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.rollback()
            return jsonify({"success": False, "message": "Mission not found."}), 404

        if existing['MISSION_STATUS'] in ('OVER', 'CANCELLED'):
            conn.rollback()
            return jsonify({"success": False, "message": f"Finished ({existing['MISSION_STATUS']}) missions cannot be modified."}), 400

        # Validate Drone exists & fetch capacity
        cursor.execute("SELECT DRONE_ID, PAYLOAD_CAP FROM DRONES WHERE DRONE_ID = %s", (drone_id,))
        drone_rec = cursor.fetchone()
        if not drone_rec:
            conn.rollback()
            return jsonify({"success": False, "message": f"Referenced Drone ID {drone_id} does not exist."}), 400

        # Validate Pilot exists & status
        cursor.execute("SELECT PILOT_ID, STATUS FROM PILOTS WHERE PILOT_ID = %s", (pilot_id,))
        pilot = cursor.fetchone()
        if not pilot:
            conn.rollback()
            return jsonify({"success": False, "message": f"Referenced Pilot ID {pilot_id} does not exist."}), 400

        if pilot_id != existing['PILOT_ID']:
            if pilot['STATUS'] == 'OFF_DUTY':
                conn.rollback()
                return jsonify({"success": False, "message": "Cannot assign an OFF_DUTY pilot."}), 400
            if pilot['STATUS'] != 'AVAILABLE':
                conn.rollback()
                return jsonify({"success": False, "message": f"Pilot is currently in '{pilot['STATUS']}' status and not AVAILABLE."}), 400

        # Validate Package exists, ownership, & weight
        cursor.execute("SELECT PACKAGE_ID, VENDOR_ID, WEIGHT FROM PACKAGES WHERE PACKAGE_ID = %s", (package_id,))
        pkg = cursor.fetchone()
        if not pkg:
            conn.rollback()
            return jsonify({"success": False, "message": f"Referenced Package ID {package_id} does not exist."}), 400

        if pkg['VENDOR_ID'] != vendor_id:
            conn.rollback()
            return jsonify({"success": False, "message": "Access Denied: You cannot assign packages belonging to another vendor."}), 403

        # Payload capacity check
        if pkg['WEIGHT'] > drone_rec['PAYLOAD_CAP']:
            conn.rollback()
            return jsonify({"success": False, "message": f"Package weight ({pkg['WEIGHT']} kg) exceeds drone payload capacity ({drone_rec['PAYLOAD_CAP']} kg)."}), 400

        # Drone Battery Health & Charging checks
        cursor.execute("SELECT COUNT(*) AS good_count FROM BATTERIES WHERE DRONE_ID = %s AND STATUS = 'GOOD'", (drone_id,))
        if cursor.fetchone()['good_count'] == 0:
            conn.rollback()
            return jsonify({"success": False, "message": f"Drone #{drone_id} has no healthy battery available (STATUS='GOOD')."}), 400

        cursor.execute("""
            SELECT COUNT(*) AS charging_count 
            FROM CHARGING_SESSIONS cs
            JOIN BATTERIES b ON cs.BATTERY_ID = b.BATTERY_ID
            WHERE b.DRONE_ID = %s AND cs.END_TIME IS NULL
        """, (drone_id,))
        if cursor.fetchone()['charging_count'] > 0:
            conn.rollback()
            return jsonify({"success": False, "message": f"Drone #{drone_id} has a battery in an active charging session."}), 400

        # Drone Maintenance check (checks latest maintenance condition)
        cursor.execute("""
            SELECT STATUS FROM MAINTENACE 
            WHERE DRONE_ID = %s 
            ORDER BY REPAIR_DATE DESC, MAINTENANCE_ID DESC 
            LIMIT 1
        """, (drone_id,))
        latest_maint = cursor.fetchone()
        if latest_maint and latest_maint['STATUS'] == 'BAD':
            conn.rollback()
            return jsonify({"success": False, "message": f"Drone #{drone_id} is grounded under active maintenance."}), 400

        # Validate Route exists
        cursor.execute("SELECT ROUTE_ID FROM ROUTES WHERE ROUTE_ID = %s", (route_id,))
        if not cursor.fetchone():
            conn.rollback()
            return jsonify({"success": False, "message": f"Referenced Route ID {route_id} does not exist."}), 400

        # Conflict checks
        cursor.execute("SELECT MISSION_ID FROM MISSIONS WHERE DRONE_ID = %s AND MISSION_STATUS IN ('IDLE', 'ONGOING') AND MISSION_ID != %s", (drone_id, mission_id))
        if cursor.fetchone():
            conn.rollback()
            return jsonify({"success": False, "message": f"Drone ID {drone_id} is already assigned to another active mission."}), 400

        cursor.execute("SELECT MISSION_ID FROM MISSIONS WHERE PILOT_ID = %s AND MISSION_STATUS IN ('IDLE', 'ONGOING') AND MISSION_ID != %s", (pilot_id, mission_id))
        if cursor.fetchone():
            conn.rollback()
            return jsonify({"success": False, "message": f"Pilot ID {pilot_id} is already assigned to another active mission."}), 400

        cursor.execute("SELECT MISSION_ID FROM MISSIONS WHERE PACKAGE_ID = %s AND MISSION_STATUS IN ('IDLE', 'ONGOING') AND MISSION_ID != %s", (package_id, mission_id))
        if cursor.fetchone():
            conn.rollback()
            return jsonify({"success": False, "message": f"Package ID {package_id} is already assigned to another active mission."}), 400

        # If package changed, release old package and reserve new package
        if package_id != existing['PACKAGE_ID']:
            cursor.execute("UPDATE PACKAGES SET STATUS = 'AVAILABLE' WHERE PACKAGE_ID = %s", (existing['PACKAGE_ID'],))
            cursor.execute("UPDATE PACKAGES SET STATUS = 'NOT AVAILABLE' WHERE PACKAGE_ID = %s", (package_id,))

        update_query = """
            UPDATE MISSIONS 
            SET DRONE_ID = %s, PILOT_ID = %s, PACKAGE_ID = %s, ROUTE_ID = %s
            WHERE MISSION_ID = %s
        """
        cursor.execute(update_query, (drone_id, pilot_id, package_id, route_id, mission_id))

        conn.commit()
        return jsonify({"success": True, "message": "Mission updated successfully!"}), 200

    except MySQLError as err:
        if conn:
            conn.rollback()
        error_msg = err.msg if hasattr(err, 'msg') else str(err)
        return jsonify({"success": False, "message": error_msg}), 400
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/missions/<int:mission_id>/start', methods=['POST'])
@role_required('VENDOR')
def api_start_mission(mission_id):
    """
    Starts an IDLE mission using stored procedure sp_start_mission.
    Revalidates pre-flight safety (pilot status, healthy battery, no active charging session,
    maintenance state, vendor authorization) and transitions mission to ONGOING atomically.
    """
    vendor_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor()
        args = (mission_id, vendor_id, 0, ' ' * 255)
        result = cursor.callproc('sp_start_mission', args)
        status_code = result[2]
        status_message = result[3].strip()

        if status_code == 200:
            return jsonify({"success": True, "message": status_message}), 200
        else:
            return jsonify({"success": False, "message": status_message}), status_code

    except MySQLError as err:
        error_msg = err.msg if hasattr(err, 'msg') else str(err)
        return jsonify({"success": False, "message": error_msg}), 400
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/missions/<int:mission_id>/complete', methods=['POST'])
@role_required('VENDOR')
def api_complete_mission(mission_id):
    """
    Completes an ONGOING mission using stored procedure sp_complete_mission.
    Atomically:
    - Sets MISSIONS.MISSION_STATUS = 'OVER', END_TIME = NOW()
    - Releases PILOTS.STATUS = 'AVAILABLE'
    - Updates DRONES.LAST_DELIVERY = NOW() and DRONES.CURR_LOCATION = route.DESTINATION
    - Sets PACKAGES.STATUS = 'NOT AVAILABLE' (delivered)
    """
    vendor_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor()
        args = (mission_id, vendor_id, 0, ' ' * 255)
        result = cursor.callproc('sp_complete_mission', args)
        status_code = result[2]
        status_message = result[3].strip()

        if status_code == 200:
            return jsonify({"success": True, "message": status_message}), 200
        else:
            return jsonify({"success": False, "message": status_message}), status_code

    except MySQLError as err:
        error_msg = err.msg if hasattr(err, 'msg') else str(err)
        return jsonify({"success": False, "message": error_msg}), 400
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/missions/<int:mission_id>/cancel', methods=['POST'])
@role_required('VENDOR')
def api_cancel_mission(mission_id):
    """
    Cancels an IDLE mission using stored procedure sp_cancel_mission.
    Safely transitions MISSION_STATUS to 'CANCELLED' and restores package status to 'AVAILABLE'.
    """
    vendor_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor()
        args = (mission_id, vendor_id, 0, ' ' * 255)
        result = cursor.callproc('sp_cancel_mission', args)
        status_code = result[2]
        status_message = result[3].strip()

        if status_code == 200:
            return jsonify({"success": True, "message": status_message}), 200
        else:
            return jsonify({"success": False, "message": status_message}), status_code

    except MySQLError as err:
        error_msg = err.msg if hasattr(err, 'msg') else str(err)
        return jsonify({"success": False, "message": error_msg}), 400
    finally:
        close_db_connection(conn, cursor)

# -----------------------------------------------------
# Battery & Charging Management API Endpoints
# -----------------------------------------------------
@app.route('/api/batteries', methods=['GET'])
@role_required('VENDOR')
def api_get_batteries():
    """
    Returns list of batteries with status, capacity, cycles, assigned drone info, and active charging status.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                b.BATTERY_ID,
                b.DRONE_ID,
                b.CAPACITY,
                b.CYCLES,
                b.STATUS,
                d.CURR_LOCATION AS DRONE_LOCATION,
                (SELECT cs.START_TIME 
                 FROM CHARGING_SESSIONS cs 
                 WHERE cs.BATTERY_ID = b.BATTERY_ID AND cs.END_TIME IS NULL 
                 LIMIT 1) AS CURRENT_CHARGING_START
            FROM BATTERIES b
            LEFT JOIN DRONES d ON b.DRONE_ID = d.DRONE_ID
            ORDER BY b.BATTERY_ID ASC
        """
        cursor.execute(query)
        batteries = cursor.fetchall()

        for bat in batteries:
            bat['is_charging'] = bat['CURRENT_CHARGING_START'] is not None
            bat['CURRENT_CHARGING_START'] = str(bat['CURRENT_CHARGING_START']) if bat['CURRENT_CHARGING_START'] else None

        return jsonify({"success": True, "batteries": batteries}), 200

    except MySQLError as err:
        print(f"MySQL Error fetching batteries: {err}")
        return jsonify({"success": False, "message": "Database error fetching batteries."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/batteries', methods=['POST'])
@role_required('VENDOR')
def api_create_battery():
    """
    Registers a new battery assigned to an existing drone.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    try:
        battery_id = int(data.get('battery_id'))
        drone_id = int(data.get('drone_id'))
        capacity = int(data.get('capacity'))
        cycles = int(data.get('cycles', 0))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Battery ID, Drone ID, Capacity, and Cycles must be valid integers."}), 400

    status = (data.get('status') or 'GOOD').strip().upper()

    if battery_id <= 0 or drone_id <= 0 or capacity <= 0 or cycles < 0:
        return jsonify({"success": False, "message": "Battery ID, Drone ID, and Capacity must be positive. Cycles cannot be negative."}), 400

    if status not in ['GOOD', 'BAD']:
        return jsonify({"success": False, "message": "Battery status must be 'GOOD' or 'BAD'."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT DRONE_ID FROM DRONES WHERE DRONE_ID = %s", (drone_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": f"Referenced Drone ID {drone_id} does not exist."}), 400

        cursor.execute("SELECT BATTERY_ID FROM BATTERIES WHERE BATTERY_ID = %s", (battery_id,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": f"Battery ID {battery_id} already exists."}), 400

        insert_query = """
            INSERT INTO BATTERIES (BATTERY_ID, DRONE_ID, CAPACITY, CYCLES, STATUS)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (battery_id, drone_id, capacity, cycles, status))
        conn.commit()

        return jsonify({"success": True, "message": "Battery registered successfully!", "battery_id": battery_id}), 201

    except MySQLError as err:
        if conn:
            conn.rollback()
        if err.errno == 1062:
            return jsonify({"success": False, "message": "Battery ID already exists."}), 400
        if err.errno == 1452:
            return jsonify({"success": False, "message": "Referenced Drone ID does not exist."}), 400
        print(f"MySQL Error registering battery: {err}")
        return jsonify({"success": False, "message": "Database error registering battery."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/charging-sessions', methods=['GET'])
@role_required('VENDOR')
def api_get_charging_sessions():
    """
    Returns full charging session history across all batteries or for a specific battery_id query param.
    """
    battery_id_param = request.args.get('battery_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)

        if battery_id_param:
            query = """
                SELECT cs.BATTERY_ID, cs.START_TIME, cs.END_TIME, b.DRONE_ID
                FROM CHARGING_SESSIONS cs
                JOIN BATTERIES b ON cs.BATTERY_ID = b.BATTERY_ID
                WHERE cs.BATTERY_ID = %s
                ORDER BY cs.START_TIME DESC
            """
            cursor.execute(query, (battery_id_param,))
        else:
            query = """
                SELECT cs.BATTERY_ID, cs.START_TIME, cs.END_TIME, b.DRONE_ID
                FROM CHARGING_SESSIONS cs
                JOIN BATTERIES b ON cs.BATTERY_ID = b.BATTERY_ID
                ORDER BY cs.START_TIME DESC
            """
            cursor.execute(query)

        sessions = cursor.fetchall()

        for s in sessions:
            s['START_TIME'] = str(s['START_TIME']) if s.get('START_TIME') else None
            s['END_TIME'] = str(s['END_TIME']) if s.get('END_TIME') else None
            s['is_ongoing'] = s['END_TIME'] is None

        return jsonify({"success": True, "charging_sessions": sessions}), 200

    except MySQLError as err:
        print(f"MySQL Error fetching charging sessions: {err}")
        return jsonify({"success": False, "message": "Database error fetching charging history."}), 500
    finally:
        close_db_connection(conn, cursor)

@app.route('/api/charging-sessions/start', methods=['POST'])
@role_required('VENDOR')
def api_start_charging_session():
    """
    Starts a charging session for a battery:
    - Validates battery exists in BATTERIES table.
    - Ensures no active/overlapping charging session exists for the battery.
    - Uses database transaction with rollback.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    try:
        battery_id = int(data.get('battery_id'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Battery ID must be a valid integer."}), 400

    custom_start_time = data.get('start_time')

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT BATTERY_ID, STATUS FROM BATTERIES WHERE BATTERY_ID = %s", (battery_id,))
        battery = cursor.fetchone()
        if not battery:
            conn.rollback()
            return jsonify({"success": False, "message": f"Referenced Battery ID {battery_id} does not exist."}), 400

        cursor.execute("""
            SELECT m.MISSION_ID 
            FROM MISSIONS m
            JOIN BATTERIES b ON m.DRONE_ID = b.DRONE_ID
            WHERE b.BATTERY_ID = %s AND m.MISSION_STATUS = 'ONGOING'
        """, (battery_id,))
        flying_mission = cursor.fetchone()
        if flying_mission:
            conn.rollback()
            return jsonify({
                "success": False,
                "message": f"Safety Violation: Cannot initiate battery charging while assigned drone is actively flying an ONGOING mission (Mission #{flying_mission['MISSION_ID']})."
            }), 400

        cursor.execute("""
            SELECT BATTERY_ID, START_TIME 
            FROM CHARGING_SESSIONS 
            WHERE BATTERY_ID = %s AND END_TIME IS NULL
        """, (battery_id,))
        active_session = cursor.fetchone()

        if active_session:
            conn.rollback()
            return jsonify({
                "success": False, 
                "message": f"Battery ID {battery_id} is already in an active charging session (Started at {active_session['START_TIME']}). Overlapping charging sessions are not allowed."
            }), 400

        if custom_start_time:
            insert_query = """
                INSERT INTO CHARGING_SESSIONS (BATTERY_ID, START_TIME, END_TIME)
                VALUES (%s, %s, NULL)
            """
            cursor.execute(insert_query, (battery_id, custom_start_time))
        else:
            insert_query = """
                INSERT INTO CHARGING_SESSIONS (BATTERY_ID, START_TIME, END_TIME)
                VALUES (%s, NOW(), NULL)
            """
            cursor.execute(insert_query, (battery_id,))

        conn.commit()

        return jsonify({
            "success": True,
            "message": f"Charging session started successfully for Battery #{battery_id}!"
        }), 201

    except MySQLError as err:
        if conn:
            conn.rollback()
        if err.errno == 1062:
            return jsonify({"success": False, "message": "A charging session with this exact start timestamp already exists for this battery."}), 400
        if err.errno == 1452:
            return jsonify({"success": False, "message": "Referenced Battery ID does not exist."}), 400
        if err.errno == 1644:
            return jsonify({"success": False, "message": err.msg}), 400
        print(f"MySQL Error starting charging session: {err}")
        return jsonify({"success": False, "message": "Database error starting charging session."}), 500

    except Exception as ex:
        if conn:
            conn.rollback()
        print(f"Unexpected Exception starting charging session: {ex}")
        return jsonify({"success": False, "message": "An internal server error occurred."}), 500

    finally:
        close_db_connection(conn, cursor)

@app.route('/api/charging-sessions/end', methods=['POST'])
@role_required('VENDOR')
def api_end_charging_session():
    """
    Ends an active charging session for a battery:
    - Finds active session (END_TIME IS NULL).
    - Validates end_time >= START_TIME.
    - Sets END_TIME = NOW() (or specified end_time).
    - Increments battery CYCLES by 1.
    - Uses database transaction with rollback.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    try:
        battery_id = int(data.get('battery_id'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Battery ID must be a valid integer."}), 400

    custom_end_time = data.get('end_time')

    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT BATTERY_ID, START_TIME 
            FROM CHARGING_SESSIONS 
            WHERE BATTERY_ID = %s AND END_TIME IS NULL
            ORDER BY START_TIME DESC LIMIT 1
        """, (battery_id,))
        session_rec = cursor.fetchone()

        if not session_rec:
            conn.rollback()
            return jsonify({
                "success": False, 
                "message": f"No active charging session found for Battery ID {battery_id}."
            }), 400

        start_time = session_rec['START_TIME']

        if custom_end_time:
            cursor.execute("SELECT %s < %s AS is_earlier", (custom_end_time, start_time))
            chk = cursor.fetchone()
            if chk and chk['is_earlier']:
                conn.rollback()
                return jsonify({
                    "success": False,
                    "message": "End time cannot be earlier than start time."
                }), 400

            update_session_query = """
                UPDATE CHARGING_SESSIONS 
                SET END_TIME = %s 
                WHERE BATTERY_ID = %s AND START_TIME = %s
            """
            cursor.execute(update_session_query, (custom_end_time, battery_id, start_time))
        else:
            update_session_query = """
                UPDATE CHARGING_SESSIONS 
                SET END_TIME = NOW() 
                WHERE BATTERY_ID = %s AND START_TIME = %s
            """
            cursor.execute(update_session_query, (battery_id, start_time))

        update_battery_query = """
            UPDATE BATTERIES 
            SET CYCLES = CYCLES + 1 
            WHERE BATTERY_ID = %s
        """
        cursor.execute(update_battery_query, (battery_id,))

        conn.commit()

        return jsonify({
            "success": True,
            "message": f"Charging session ended for Battery #{battery_id}. Battery cycles incremented."
        }), 200

    except MySQLError as err:
        if conn:
            conn.rollback()
        print(f"MySQL Error ending charging session: {err}")
        return jsonify({"success": False, "message": "Database error ending charging session."}), 500

    finally:
        close_db_connection(conn, cursor)

# -----------------------------------------------------
# Checkpoint 3: Billing & Payments APIs
# -----------------------------------------------------

def calculate_mission_billing(distance: float, weight: float) -> int:
    """
    Centrally defined deterministic billing formula (Academic model):
    - Base Fee: ₹50 flat
    - Distance Rate: ₹10 / km (derived from ROUTES.DISTANCE)
    - Weight Rate: ₹15 / kg (derived from PACKAGES.WEIGHT)
    - Total = round(50 + (10 * distance) + (15 * weight))
    - Min: ₹50, Currency: INR
    """
    base_fee = 50
    dist_rate = 10.0
    weight_rate = 15.0
    total = base_fee + (float(distance) * dist_rate) + (float(weight) * weight_rate)
    return max(50, int(round(total)))


@app.route('/api/customer/billing/<int:mission_id>', methods=['GET'])
@login_required
@customer_required
def api_get_customer_billing(mission_id):
    """
    Returns deterministic billing calculation and payment status for a customer mission.
    Enforces customer ownership of the underlying package.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT m.MISSION_ID, m.MISSION_STATUS, m.START_TIME, m.END_TIME,
                   p.PACKAGE_ID, p.PRODUCT_ID, p.USER_ID, p.WEIGHT,
                   r.ROUTE_ID, r.SOURCE, r.DESTINATION, r.DISTANCE,
                   v.VENDOR_NAME
            FROM MISSIONS m
            JOIN PACKAGES p ON m.PACKAGE_ID = p.PACKAGE_ID
            JOIN ROUTES r ON m.ROUTE_ID = r.ROUTE_ID
            JOIN VENDORS v ON p.VENDOR_ID = v.VENDOR_ID
            WHERE m.MISSION_ID = %s
        """
        cursor.execute(query, (mission_id,))
        mission = cursor.fetchone()

        if not mission:
            return jsonify({"success": False, "message": f"Mission #{mission_id} not found."}), 404

        # Enforce customer package ownership
        if mission['USER_ID'] != session['user_id']:
            return jsonify({"success": False, "message": "Access denied: Package belongs to another customer."}), 403

        distance = float(mission['DISTANCE'])
        weight = float(mission['WEIGHT'])
        base_fee = 50
        dist_fee = round(distance * 10.0, 2)
        weight_fee = round(weight * 15.0, 2)
        total_amount = calculate_mission_billing(distance, weight)

        # Check existing payment history for this mission
        pay_query = """
            SELECT PAYMENT_ID, USER_ID, MISSION_ID, TIMESTAMP, MODE, AMOUNT, STATUS
            FROM PAYMENTS
            WHERE MISSION_ID = %s
            ORDER BY PAYMENT_ID DESC
        """
        cursor.execute(pay_query, (mission_id,))
        payments = cursor.fetchall()
        for p in payments:
            if isinstance(p.get('TIMESTAMP'), (datetime, date)):
                p['TIMESTAMP'] = p['TIMESTAMP'].strftime("%Y-%m-%d %H:%M:%S")

        existing_payment = payments[0] if payments else None
        is_paid = any(p['STATUS'] == 'COMPLETED' for p in payments)

        return jsonify({
            "success": True,
            "billing": {
                "mission_id": mission_id,
                "mission_status": mission['MISSION_STATUS'],
                "package_id": mission['PACKAGE_ID'],
                "vendor_name": mission['VENDOR_NAME'],
                "source": mission['SOURCE'],
                "destination": mission['DESTINATION'],
                "distance_km": distance,
                "weight_kg": weight,
                "base_fee": base_fee,
                "distance_fee": dist_fee,
                "weight_fee": weight_fee,
                "total_amount": total_amount,
                "currency": "INR",
                "is_paid": is_paid,
                "eligible_for_payment": mission['MISSION_STATUS'] == 'OVER' and not is_paid,
                "existing_payment": existing_payment,
                "all_payments": payments
            }
        }), 200

    except MySQLError as err:
        print(f"MySQL Error fetching billing: {err}")
        return jsonify({"success": False, "message": "Database error loading billing details."}), 500
    finally:
        close_db_connection(conn, cursor)


@app.route('/api/customer/payments', methods=['POST'])
@login_required
@customer_required
def api_process_payment():
    """
    Submits a payment for a completed delivery mission via sp_process_payment.
    Enforces customer ownership, completed mission state, and duplicate prevention.
    """
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Missing request payload."}), 400

        mission_id = data.get('mission_id')
        mode = data.get('mode', 'ONLINE').strip().upper()

        if not mission_id:
            return jsonify({"success": False, "message": "Mission ID is required."}), 400

        try:
            mission_id = int(mission_id)
        except ValueError:
            return jsonify({"success": False, "message": "Invalid Mission ID format."}), 400

        if mode not in ['ONLINE', 'COD']:
            return jsonify({"success": False, "message": "Unsupported payment mode. Must be ONLINE or COD."}), 400

        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor()

        # Call sp_process_payment
        args = (session['user_id'], mission_id, mode, 0, 0, 0, ' ' * 255)
        result_args = cursor.callproc('sp_process_payment', args)

        payment_id = result_args[3]
        final_amount = result_args[4]
        status_code = result_args[5]
        status_msg = result_args[6].strip() if result_args[6] else ''

        if status_code in [200, 201]:
            conn.commit()
            target_status = 'COMPLETED' if mode == 'ONLINE' else 'PROCESSING'
            return jsonify({
                "success": True,
                "message": status_msg,
                "payment_id": payment_id,
                "amount": final_amount,
                "mode": mode,
                "status": target_status
            }), status_code
        else:
            conn.rollback()
            return jsonify({"success": False, "message": status_msg}), status_code

    except MySQLError as err:
        if conn:
            conn.rollback()
        err_msg = str(err)
        print(f"MySQL Error processing payment: {err_msg}")
        if "Payment Integrity Error" in err_msg:
            return jsonify({"success": False, "message": err_msg.split(':')[-1].strip()}), 400
        return jsonify({"success": False, "message": "Database error processing payment."}), 500
    finally:
        close_db_connection(conn, cursor)


@app.route('/api/customer/payments', methods=['GET'])
@login_required
@customer_required
def api_get_customer_payments():
    """
    Returns full payment history for packages belonging to the authenticated customer.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT p.PAYMENT_ID, p.MISSION_ID, pkg.PACKAGE_ID, pkg.PRODUCT_ID,
                   p.TIMESTAMP, p.MODE, p.AMOUNT, p.STATUS,
                   r.SOURCE, r.DESTINATION, r.DISTANCE, pkg.WEIGHT,
                   v.VENDOR_NAME
            FROM PAYMENTS p
            JOIN MISSIONS m ON p.MISSION_ID = m.MISSION_ID
            JOIN PACKAGES pkg ON m.PACKAGE_ID = pkg.PACKAGE_ID
            JOIN ROUTES r ON m.ROUTE_ID = r.ROUTE_ID
            JOIN VENDORS v ON pkg.VENDOR_ID = v.VENDOR_ID
            WHERE pkg.USER_ID = %s
            ORDER BY p.TIMESTAMP DESC, p.PAYMENT_ID DESC
        """
        cursor.execute(query, (session['user_id'],))
        payments = cursor.fetchall()

        for p in payments:
            if isinstance(p.get('TIMESTAMP'), (datetime, date)):
                p['TIMESTAMP'] = p['TIMESTAMP'].strftime("%Y-%m-%d %H:%M:%S")

        return jsonify({"success": True, "payments": payments}), 200

    except MySQLError as err:
        print(f"MySQL Error fetching customer payments: {err}")
        return jsonify({"success": False, "message": "Database error loading payment records."}), 500
    finally:
        close_db_connection(conn, cursor)


# -----------------------------------------------------
# Checkpoint 3: Maintenance APIs
# -----------------------------------------------------

@app.route('/api/maintenance', methods=['GET'])
@login_required
@vendor_required
def api_get_maintenance_records():
    """
    Returns all maintenance records with drone location and capacity details.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT m.MAINTENANCE_ID, m.DRONE_ID, m.STATUS, m.REPAIR_DATE, m.COST, m.REASON,
                   d.CURR_LOCATION, d.PAYLOAD_CAP
            FROM MAINTENACE m
            JOIN DRONES d ON m.DRONE_ID = d.DRONE_ID
            ORDER BY m.REPAIR_DATE DESC, m.MAINTENANCE_ID DESC
        """
        cursor.execute(query)
        records = cursor.fetchall()

        for r in records:
            if isinstance(r.get('REPAIR_DATE'), (datetime, date)):
                r['REPAIR_DATE'] = r['REPAIR_DATE'].strftime("%Y-%m-%d")

        return jsonify({"success": True, "maintenance_records": records}), 200

    except MySQLError as err:
        print(f"MySQL Error fetching maintenance: {err}")
        return jsonify({"success": False, "message": "Database error loading maintenance records."}), 500
    finally:
        close_db_connection(conn, cursor)


@app.route('/api/maintenance', methods=['POST'])
@login_required
@vendor_required
def api_create_maintenance_record():
    """
    Records a maintenance or inspection event for a drone via sp_record_maintenance.
    """
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Missing request payload."}), 400

        drone_id = data.get('drone_id')
        status = data.get('status', 'GOOD').strip().upper()
        cost = data.get('cost')
        reason = data.get('reason', '').strip()
        repair_date = data.get('repair_date')

        if not drone_id or cost is None:
            return jsonify({"success": False, "message": "Drone ID and Cost are required."}), 400

        try:
            drone_id = int(drone_id)
            cost = int(cost)
        except ValueError:
            return jsonify({"success": False, "message": "Drone ID and Cost must be valid integers."}), 400

        if cost <= 0:
            return jsonify({"success": False, "message": "Maintenance cost must be strictly positive."}), 400

        if status not in ['GOOD', 'BAD']:
            return jsonify({"success": False, "message": "Maintenance status must be GOOD or BAD."}), 400

        if not reason:
            reason = "Routine Inspection" if status == 'GOOD' else "Issue Detected"

        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor()

        args = (drone_id, status, cost, reason, repair_date, 0, 0, ' ' * 255)
        result_args = cursor.callproc('sp_record_maintenance', args)

        maint_id = result_args[5]
        status_code = result_args[6]
        status_msg = result_args[7].strip() if result_args[7] else ''

        if status_code in [200, 201]:
            conn.commit()
            return jsonify({
                "success": True,
                "message": status_msg,
                "maintenance_id": maint_id
            }), status_code
        else:
            conn.rollback()
            return jsonify({"success": False, "message": status_msg}), status_code

    except MySQLError as err:
        if conn:
            conn.rollback()
        err_msg = str(err)
        print(f"MySQL Error creating maintenance: {err_msg}")
        if "Maintenance Error" in err_msg:
            return jsonify({"success": False, "message": err_msg.split(':')[-1].strip()}), 400
        return jsonify({"success": False, "message": "Database error saving maintenance record."}), 500
    finally:
        close_db_connection(conn, cursor)


@app.route('/api/maintenance/drones-summary', methods=['GET'])
@login_required
@vendor_required
def api_get_drones_maintenance_summary():
    """
    Returns each drone with its latest maintenance diagnostics and flight condition.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        if not conn or not conn.is_connected():
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT d.DRONE_ID, d.PAYLOAD_CAP, d.CURR_LOCATION,
                   COALESCE(latest_m.STATUS, 'GOOD') AS CURRENT_CONDITION,
                   latest_m.REPAIR_DATE AS LAST_REPAIR_DATE,
                   latest_m.REASON AS LAST_REASON,
                   latest_m.COST AS LAST_COST,
                   CASE 
                       WHEN EXISTS (SELECT 1 FROM MISSIONS WHERE DRONE_ID = d.DRONE_ID AND MISSION_STATUS = 'ONGOING') THEN 'IN_FLIGHT'
                       WHEN EXISTS (SELECT 1 FROM CHARGING_SESSIONS cs JOIN BATTERIES b ON cs.BATTERY_ID = b.BATTERY_ID WHERE b.DRONE_ID = d.DRONE_ID AND cs.END_TIME IS NULL) THEN 'CHARGING'
                       WHEN COALESCE(latest_m.STATUS, 'GOOD') = 'BAD' THEN 'GROUNDED'
                       ELSE 'READY'
                   END AS OPERATIONAL_STATUS
            FROM DRONES d
            LEFT JOIN (
                SELECT m1.*
                FROM MAINTENACE m1
                JOIN (
                    SELECT DRONE_ID, MAX(MAINTENANCE_ID) AS MAX_ID
                    FROM MAINTENACE
                    GROUP BY DRONE_ID
                ) m2 ON m1.MAINTENANCE_ID = m2.MAX_ID
            ) latest_m ON d.DRONE_ID = latest_m.DRONE_ID
            ORDER BY d.DRONE_ID ASC
        """
        cursor.execute(query)
        summary = cursor.fetchall()

        for s in summary:
            if isinstance(s.get('LAST_REPAIR_DATE'), (datetime, date)):
                s['LAST_REPAIR_DATE'] = s['LAST_REPAIR_DATE'].strftime("%Y-%m-%d")

        return jsonify({"success": True, "drones_summary": summary}), 200

    except MySQLError as err:
        print(f"MySQL Error fetching drone maintenance summary: {err}")
        return jsonify({"success": False, "message": "Database error loading drone diagnostics."}), 500
    finally:
        close_db_connection(conn, cursor)


# -----------------------------------------------------
# Error Handlers
# -----------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Resource not found", "status_code": 404}), 404

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({"error": "Internal server error", "status_code": 500}), 500

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() in ['true', '1', 't']
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
