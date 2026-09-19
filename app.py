import os
import re
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
