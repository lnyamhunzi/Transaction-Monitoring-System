import mysql.connector
from config import settings

def apply_schema_changes():
    print("Applying schema changes to database...")
    try:
        conn = mysql.connector.connect(
            host=settings.DB_HOST,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            port=settings.DB_PORT
        )
        cursor = conn.cursor()

        # Add 'updated_at' to 'users' table if it doesn't exist
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
            print("Added 'updated_at' column to 'users' table.")
        except mysql.connector.Error as err:
            if "Duplicate column name" in str(err):
                print("'updated_at' column already exists in 'users' table. Skipping.")
            else:
                raise err

        # Add 'exchange_rate' to 'transactions' table if it doesn't exist
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN exchange_rate FLOAT DEFAULT 1.0")
            print("Added 'exchange_rate' column to 'transactions' table.")
        except mysql.connector.Error as err:
            if "Duplicate column name" in str(err):
                print("'exchange_rate' column already exists in 'transactions' table. Skipping.")
            else:
                raise err

        conn.commit()
        print("Schema changes applied successfully.")

    except mysql.connector.Error as err:
        print(f"Error applying schema changes: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    apply_schema_changes()