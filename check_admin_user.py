import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from models import User, Base
from config import settings

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

def check_admin_user():
    db = next(get_db())
    try:
        admin_user = db.query(User).filter(User.username == "admin@mugonat.com").first()
        if admin_user:
            print("Admin user 'admin@mugonat.com' found in the database.")
            print(f"Full Name: {admin_user.full_name}")
            print(f"Role: {admin_user.role}")
            print(f"Hashed Password (first 10 chars): {admin_user.hashed_password[:10]}...")
        else:
            print("Admin user 'admin@mugonat.com' NOT found in the database.")
    except Exception as e:
        print(f"An error occurred while checking for admin user: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_admin_user()
