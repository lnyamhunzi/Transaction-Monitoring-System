import mysql.connector
from config import settings

def create_database_if_not_exists():
    print(f"Attempting to connect to MySQL server at {settings.DB_HOST}:{settings.DB_PORT}...")
    try:
        # Connect to MySQL server without specifying a database
        conn = mysql.connector.connect(
            host=settings.DB_HOST,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            port=settings.DB_PORT
        )
        cursor = conn.cursor()

        db_name = settings.DB_NAME
        print(f"Creating database '{db_name}' if it does not exist...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"Database '{db_name}' ensured to exist.")

        conn.commit()

    except mysql.connector.Error as err:
        print(f"Error creating database: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    create_database_if_not_exists()
