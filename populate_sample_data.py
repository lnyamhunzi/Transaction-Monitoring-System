import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import uuid
import random
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import Customer, Account, Transaction, Base
from config import settings
from main import get_password_hash

# Database setup
DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_sample_data(num_customers=100, num_transactions_per_customer=50):
    print("Generating sample data...")
    db = next(get_db())
    
    # Clear existing data (optional, for fresh start)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    customers = []
    accounts = []
    transactions = []

    for _ in range(num_customers):
        customer_id = str(uuid.uuid4())
        customer_email = f"user{random.randint(1000, 9999)}@example.com"
        customer_username = customer_email # Using email as username
        customer_password = "testpassword" # Fixed password for all generated customers
        hashed_customer_password = get_password_hash(customer_password)
        customer = Customer(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            full_name=f"Customer {random.randint(1000, 9999)}",
            date_of_birth=datetime(random.randint(1950, 2000), random.randint(1, 12), random.randint(1, 28)),
            nationality=random.choice(["USA", "GBR", "CAN", "AUS", "ZAF"]),
            id_number=f"ID{random.randint(100000, 999999)}",
            phone_number=f"+1-{random.randint(100, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            email=customer_email,
            address=f"{random.randint(1, 999)} Main St, City, Country",
            occupation=random.choice(["Engineer", "Doctor", "Teacher", "Artist", "Manager"]),
            employer=f"Company {random.randint(1, 10)}",
            account_opening_date=datetime.now() - timedelta(days=random.randint(365, 1000)),
            username=customer_username,
            hashed_password=hashed_customer_password
        )
        customers.append(customer)
        db.add(customer) # Add customer to session
        db.flush() # Flush to get customer_id into database before accounts

        account_number = f"ACC{random.randint(100000000, 999999999)}"
        account = Account(
            id=str(uuid.uuid4()),
            account_number=account_number,
            customer_id=customer_id, # This customer_id should now exist in DB
            account_type=random.choice(["SAVINGS", "CURRENT"]),
            currency="USD",
            balance=round(random.uniform(1000, 100000), 2),
            status="ACTIVE",
            opening_date=customer.account_opening_date
        )
        accounts.append(account)
        db.add(account) # Add account to session
        db.flush() # Flush to get account_number into database before transactions

        for _ in range(num_transactions_per_customer):
            transaction_date = datetime.now() - timedelta(days=random.randint(1, 90)) # Last 90 days
            amount = round(random.uniform(10, 5000), 2)
            transaction = Transaction(
                id=str(uuid.uuid4()),
                customer_id=customer_id,
                account_number=account_number, # This account_number should now exist in DB
                transaction_type=random.choice(["DEBIT", "CREDIT", "TRANSFER"]),
                amount=amount,
                base_amount=amount, # Assuming USD for simplicity
                currency="USD",
                channel=random.choice(["ONLINE", "ATM", "POS", "BRANCH"]),
                counterparty_account=f"CP{random.randint(100000000, 999999999)}",
                counterparty_name=f"CP Name {random.randint(100, 999)}",
                counterparty_bank=f"Bank {random.randint(1, 5)}",
                counterparty_country=random.choice(["USA", "GBR", "CAN"]),
                reference=f"REF{random.randint(10000, 99999)}",
                narrative=random.choice(["Payment", "Deposit", "Withdrawal", "Transfer"]), 
                processing_date=transaction_date,
                risk_score=round(random.uniform(0.1, 0.9), 2),
                is_suspicious=random.choice([True, False]),
                is_cross_border=random.choice([True, False]),
                is_high_value=(amount > 1000),
                ml_prediction=random.choice(["ANOMALY", "NORMAL"]) # Add ML prediction
            )
            transactions.append(transaction)
            db.add(transaction) # Add transaction to session
    
    db.commit() # Commit all changes at the end
    print(f"Generated {len(customers)} customers, {len(accounts)} accounts, and {len(transactions)} transactions.")
    print("===")
    print("Sample Customer Credentials:")
    print(f"Username: {customers[0].username}")
    print(f"Password: testpassword")
    print("===")
    db.close()

if __name__ == "__main__":
    generate_sample_data(num_customers=100, num_transactions_per_customer=50)