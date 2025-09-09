import sqlalchemy
from sqlalchemy import create_engine, inspect
from config import settings

def run_migration():
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    
    # For transactions table
    trans_columns = [col['name'] for col in inspector.get_columns('transactions')]
    
    with engine.connect() as connection:
        if 'status' not in trans_columns:
            print("Adding 'status' column to 'transactions' table...")
            connection.execute(sqlalchemy.text("ALTER TABLE transactions ADD COLUMN status VARCHAR(255) NOT NULL DEFAULT 'PENDING'"))
            print("Column 'status' added.")
        else:
            print("Column 'status' already exists in 'transactions'.")
            
        if 'processing_status' not in trans_columns:
            print("Adding 'processing_status' column to 'transactions' table...")
            connection.execute(sqlalchemy.text("ALTER TABLE transactions ADD COLUMN processing_status VARCHAR(255)"))
            print("Column 'processing_status' added.")
        else:
            print("Column 'processing_status' already exists in 'transactions'.")

    # For customers table
    cust_columns = [col['name'] for col in inspector.get_columns('customers')]

    with engine.connect() as connection:
        if 'status' not in cust_columns:
            print("Adding 'status' column to 'customers' table...")
            connection.execute(sqlalchemy.text("ALTER TABLE customers ADD COLUMN status VARCHAR(255) DEFAULT 'active'"))
            print("Column 'status' added.")
        else:
            print("Column 'status' already exists in 'customers'.")

        if 'is_staff' not in cust_columns:
            print("Adding 'is_staff' column to 'customers' table...")
            connection.execute(sqlalchemy.text("ALTER TABLE customers ADD COLUMN is_staff BOOLEAN DEFAULT FALSE"))
            print("Column 'is_staff' added.")
        else:
            print("Column 'is_staff' already exists in 'customers'.")


if __name__ == "__main__":
    run_migration()
