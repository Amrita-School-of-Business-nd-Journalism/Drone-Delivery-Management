import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_db_connection(use_database=True):
    """
    1. Opens a database connection to MySQL/MariaDB server using environment variables.
    Handles connection errors gracefully.
    """
    try:
        config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', '')
        }
        if use_database:
            config['database'] = os.getenv('DB_NAME', 'DRONEDELIVERY')
            
        connection = mysql.connector.connect(**config)
        return connection
    except Error as e:
        print(f"Database Connection Error: {e}")
        return None

def close_db_connection(connection=None, cursor=None):
    """
    2. Safely closes the database cursor and connection.
    """
    try:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
    except Error as e:
        print(f"Error while closing database resources: {e}")

def test_db_connection():
    """
    3. Error handling & connection verification helper.
    """
    connection = None
    try:
        connection = get_db_connection(use_database=True)
        if connection and connection.is_connected():
            server_info = connection.get_server_info()
            return True, f"Successfully connected to MySQL server (v{server_info})"
        return False, "Could not establish database connection."
    except Error as e:
        return False, f"Database error encountered: {str(e)}"
    finally:
        close_db_connection(connection)
