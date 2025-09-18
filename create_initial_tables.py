from database import engine
from models import Base, User, Customer, Account, Transaction, Alert, Case, CaseActivity, SanctionsList, PEPList, ExchangeRate, SystemConfiguration, AuditLog, MLModel

def create_initial_tables():
    print("Creating initial database tables...")
    Base.metadata.create_all(engine)
    print("Initial database tables created successfully.")

if __name__ == "__main__":
    create_initial_tables()