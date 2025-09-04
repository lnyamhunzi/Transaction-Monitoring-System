import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta
import os
import sys

# Add parent directory to path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import settings

def generate_transaction_data(days_back=90):
    """
    Generates transaction data from the database for the specified number of days back.
    """
    DATABASE_URL = settings.DATABASE_URL
    engine = create_engine(DATABASE_URL)

    query = f"""
    SELECT 
        t.id,
        t.customer_id,
        t.account_number,
        t.transaction_type,
        t.amount,
        t.base_amount,
        t.currency,
        t.channel,
        t.counterparty_account,
        t.counterparty_name,
        t.counterparty_bank,
        t.counterparty_country,
        t.reference,
        t.narrative,
        t.processing_date,
        t.processed_by,
        t.risk_score,
        t.is_suspicious,
        t.is_cross_border,
        t.is_high_value,
        t.created_at,
        c.risk_rating,
        c.is_pep,
        c.account_opening_date,
        CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as has_alert
    FROM transactions t
    LEFT JOIN customers c ON t.customer_id = c.customer_id
    LEFT JOIN alerts a ON t.id = a.transaction_id
    WHERE t.created_at >= NOW() - INTERVAL {days_back} DAY
    ORDER BY t.created_at DESC
    """
    
    print(f"Connecting to database and fetching data for the last {days_back} days...")
    df = pd.read_sql(query, engine)
    print(f"Successfully loaded {len(df)} transactions.")
    return df

if __name__ == "__main__":
    output_dir = "generated_data"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "transaction_data_90_days.csv")
    
    df_transactions = generate_transaction_data(days_back=90)
    
    if not df_transactions.empty:
        df_transactions.to_csv(output_file, index=False)
        print(f"Transaction data saved to {output_file}")
    else:
        print("No transaction data generated.")
