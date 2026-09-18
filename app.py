import os
import re
from flask import Flask, render_template, request, jsonify
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from database import get_db_connection, close_db_connection
from mysql.connector import Error as MySQLError

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_fallback_secret_key')

EMAIL_REGEX = re.compile(r'^[A-Za-z0-9_]+@[A-Za-z]+\.[A-Za-z]{2,}$')
PHONE_REGEX = re.compile(r'^[0-9]{10}$')

@app.route('/')
def home():
    """
    Home route. Simply renders index.html.
    """
    return render_template('index.html')

@app.route('/register', methods=['GET'])
def register_page():
    """
    Renders the User Registration HTML page.
    """
    return render_template('register.html')

@app.route('/api/register', methods=['POST'])
def api_register():
    """
    API endpoint to handle user registration with validation, password hashing, and parameterized SQL.
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

    # Field validations
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

        # Parameterized check for existing duplicate email or phone number
        check_query = "SELECT EMAIL, PHONE_NO FROM USERS WHERE EMAIL = %s OR PHONE_NO = %s"
        cursor.execute(check_query, (email, phone_no))
        existing_users = cursor.fetchall()

        for user in existing_users:
            if user['EMAIL'].lower() == email.lower():
                return jsonify({"success": False, "message": "Email address is already registered."}), 400
            if user['PHONE_NO'] == phone_no:
                return jsonify({"success": False, "message": "Phone number is already registered."}), 400

        # Password Hashing using Werkzeug
        password_hash = generate_password_hash(password)

        # Parameterized SQL Insertion into USERS table
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
        # Handle duplicate entry error code 1062 as fallback
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

@app.errorhandler(404)
def page_not_found(e):
    """
    Basic 404 Error Handler.
    """
    return jsonify({"error": "Resource not found", "status_code": 404}), 404

@app.errorhandler(500)
def internal_server_error(e):
    """
    Basic 500 Error Handler.
    """
    return jsonify({"error": "Internal server error", "status_code": 500}), 500

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() in ['true', '1', 't']
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
