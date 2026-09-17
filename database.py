import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_db_connection():
    """
    Establishes and returns a connection to the MySQL/MariaDB database.
    """
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'drone_delivery_db')
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None

def test_db_connection():
    """
    Utility function to test database connectivity.
    """
    conn = get_db_connection()
    if conn and conn.is_connected():
        db_info = conn.get_server_info()
        conn.close()
        return True, f"Successfully connected to MySQL Server version {db_info}"
    return False, "Failed to connect to the database."
