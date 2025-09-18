import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import get_db, engine
from models import Base, Transaction
from aml_processing import process_transaction_controls
from main import manager # Import the manager from main.py

async def reprocess_recent_transactions():
    print("Starting re-processing of transactions from the last 24 hours...")
    db: Session = next(get_db())
    
    try:
        # Calculate the time 24 hours ago
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        
        # Fetch transactions from the last 24 hours
        recent_transactions = db.query(Transaction).filter(
            Transaction.created_at >= twenty_four_hours_ago
        ).all()
        
        print(f"Found {len(recent_transactions)} transactions to re-process.")
        
        for transaction in recent_transactions:
            print(f"Re-processing transaction: {transaction.id}")
            # Prepare transaction_data in the format expected by process_transaction_controls
            transaction_data = {
                "id": str(transaction.id),
                "customer_id": transaction.customer_id,
                "account_number": transaction.account_number,
                "transaction_type": transaction.transaction_type,
                "amount": transaction.amount,
                "base_amount": transaction.base_amount,
                "currency": transaction.currency,
                "channel": transaction.channel,
                "counterparty_account": transaction.counterparty_account,
                "counterparty_name": transaction.counterparty_name,
                "counterparty_bank": transaction.counterparty_bank,
                "reference": transaction.reference,
                "narrative": transaction.narrative,
                "processed_by": transaction.processed_by,
                "status": transaction.status.value if hasattr(transaction.status, 'value') else str(transaction.status)
            }
            
            # Call process_transaction_controls
            # Note: process_transaction_controls expects a dict for transaction_data,
            # and the manager object.
            await process_transaction_controls(transaction.id, transaction_data, db, manager)
            print(f"Finished re-processing transaction: {transaction.id}")
            
        db.commit()
        print("Re-processing complete. All changes committed to the database.")
        
    except Exception as e:
        db.rollback()
        print(f"An error occurred during re-processing: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Ensure database tables are created before running
    Base.metadata.create_all(bind=engine)
    asyncio.run(reprocess_recent_transactions())