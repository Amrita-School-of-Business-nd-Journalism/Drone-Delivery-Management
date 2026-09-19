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

@app.route('/customer/dashboard', methods=['GET'])
@role_required('CUSTOMER')
def customer_dashboard():
    """
    Protected Customer Dashboard route.
    """
    return render_template('customer_dashboard.html')

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
@app.route('/api/register', methods=['POST'])
def api_register():
    """
    API endpoint to handle user registration.
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

    if not first_name or not last_name or not email or not phone_no or not password or not role:
        return jsonify({"success": False, "message": "All fields are required."}), 400

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

        insert_query = """
            INSERT INTO USERS (FIRST_NAME, LAST_NAME, EMAIL, PHONE_NO, PASSWORD_HASH, CREATED_AT, ROLE)
            VALUES (%s, %s, %s, %s, %s, CURDATE(), %s)
        """
        cursor.execute(insert_query, (first_name, last_name, email, phone_no, password_hash, role))
        conn.commit()

        return jsonify({"success": True, "message": "User registered successfully!"}), 201

    except MySQLError as err:
        if conn:
            conn.rollback()
        if err.errno == 1062:
            return jsonify({"success": False, "message": "Duplicate email or phone number detected."}), 400
        print(f"MySQL Error during registration: {err}")
        return jsonify({"success": False, "message": "A database error occurred."}), 500

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

@app.route('/api/profile', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_profile():
    """
    API endpoint for viewing, updating, and deleting the logged-in user's profile.
    """
    user_id = session.get('user_id')
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

            # Format created_at date for JSON output
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

        if not first_name or not last_name or not phone_no:
            return jsonify({"success": False, "message": "First name, last name, and phone number are required."}), 400

        if len(first_name) > 25 or len(last_name) > 25:
            return jsonify({"success": False, "message": "First name and last name must not exceed 25 characters."}), 400

        if not PHONE_REGEX.match(phone_no):
            return jsonify({"success": False, "message": "Phone number must be exactly 10 digits."}), 400

        try:
            conn = get_db_connection(use_database=True)
            if not conn or not conn.is_connected():
                return jsonify({"success": False, "message": "Database connection failed."}), 500

            cursor = conn.cursor(dictionary=True)

            # Check if phone number is already taken by another user
            check_query = "SELECT USER_ID FROM USERS WHERE PHONE_NO = %s AND USER_ID != %s"
            cursor.execute(check_query, (phone_no, user_id))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Phone number is already in use by another account."}), 400

            # Parameterized update
            update_query = """
                UPDATE USERS 
                SET FIRST_NAME = %s, LAST_NAME = %s, PHONE_NO = %s 
                WHERE USER_ID = %s
            """
            cursor.execute(update_query, (first_name, last_name, phone_no, user_id))
            conn.commit()

            # Update session
            session['first_name'] = first_name

            return jsonify({"success": True, "message": "Profile updated successfully!"}), 200

        except MySQLError as err:
            if conn:
                conn.rollback()
            if err.errno == 1062:
                return jsonify({"success": False, "message": "Phone number is already registered."}), 400
            print(f"MySQL Error updating profile: {err}")
            return jsonify({"success": False, "message": "A database error occurred."}), 500

        finally:
            close_db_connection(conn, cursor)

    elif request.method == 'DELETE':
        try:
            conn = get_db_connection(use_database=True)
            if not conn or not conn.is_connected():
                return jsonify({"success": False, "message": "Database connection failed."}), 500

            cursor = conn.cursor()

            # Parameterized account deletion
            delete_query = "DELETE FROM USERS WHERE USER_ID = %s"
            cursor.execute(delete_query, (user_id,))
            conn.commit()

            # Clear session
            session.clear()

            return jsonify({"success": True, "message": "Account deleted successfully.", "redirect_url": url_for('home')}), 200

        except MySQLError as err:
            if conn:
                conn.rollback()
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
