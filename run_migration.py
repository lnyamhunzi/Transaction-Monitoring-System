import sqlalchemy
from sqlalchemy import create_engine, inspect
from config import settings

def run_migration():
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    
    columns = [col['name'] for col in inspector.get_columns('transactions')]
    
    with engine.connect() as connection:
        if 'status' not in columns:
            print("Adding 'status' column to 'transactions' table...")
            connection.execute(sqlalchemy.text("ALTER TABLE transactions ADD COLUMN status VARCHAR(255) NOT NULL DEFAULT 'PENDING'"))
            print("Column 'status' added.")
        else:
            print("Column 'status' already exists.")
            
        if 'processing_status' not in columns:
            print("Adding 'processing_status' column to 'transactions' table...")
            connection.execute(sqlalchemy.text("ALTER TABLE transactions ADD COLUMN processing_status VARCHAR(255)"))
            print("Column 'processing_status' added.")
        else:
            print("Column 'processing_status' already exists.")

if __name__ == "__main__":
    run_migration()
