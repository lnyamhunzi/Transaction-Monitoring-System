from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect, Request, Response, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func, case, asc
import uvicorn
from passlib.context import CryptContext
from jose import JWTError, jwt
import uuid
import random

from database import get_db, engine
from models import *
from aml_controls import AMLControlEngine
from ml_engine import MLAnomlyEngine
from risk_scoring import RiskScoringEngine
from sanctions_screening import SanctionsScreeningEngine
from notification_service import NotificationService
from currency_service import CurrencyService
from case_management import CaseManagementService
from aml_processing import process_transaction_controls # New import
from config import settings


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
aml_engine = AMLControlEngine()
ml_engine = MLAnomlyEngine()
risk_engine = RiskScoringEngine()
sanctions_engine = SanctionsScreeningEngine()
notification_service = NotificationService()
currency_service = CurrencyService()
case_service = CaseManagementService()

# WebSocket connection manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

import asyncio

async def broadcast_updates():
    while True:
        await asyncio.sleep(60)
        db = next(get_db())
        transactions = db.query(Transaction, Alert, Case).outerjoin(Alert, Transaction.id == Alert.transaction_id).outerjoin(Case, Alert.id == Case.alert_id).order_by(desc(Transaction.created_at)).limit(100).all()
        db.close()
        
        transactions_data = []
        for transaction, alert, case in transactions:
            status = "Clear"
            if case:
                status = "Case"
            elif alert:
                status = "Alert"
            
            transactions_data.append({
                "id": transaction.id,
                "customer_id": transaction.customer_id,
                "amount": transaction.amount,
                "currency": transaction.currency,
                "channel": transaction.channel,
                "created_at": transaction.created_at.isoformat(),
                "status": status,
                "risk_score": transaction.risk_score,
                "ml_prediction": transaction.ml_prediction if hasattr(transaction, 'ml_prediction') else None
            })
        
        await manager.broadcast({"type": "transaction_stream", "data": transactions_data})

async def broadcast_system_metrics():
    while True:
        await asyncio.sleep(5) # Broadcast every 5 seconds
        # In a real system, you would fetch actual system metrics here
        # For now, we'll use dummy data or data from get_system_status API
        db = next(get_db())
        system_status = await get_system_status(db=db, current_user=None) # current_user=None for background task
        db.close()
        
        await manager.broadcast({"type": "system_metrics", "data": system_status})

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Banking AML Transaction Monitoring System")
    logger.info("Creating database tables...")
    try:
        
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")

        # Create default admin user
        db = next(get_db())
        admin_user = db.query(User).filter(User.username == "admin@mugonat.com").first()
        hashed_password = get_password_hash("Mugonat#99")
        if not admin_user:
            logger.info("Default admin user not found, creating it...")
            new_admin = User(
                username="admin@mugonat.com",
                hashed_password=hashed_password,
                full_name="Admin User",
                email="admin@mugonat.com",
                role="admin"
            )
            db.add(new_admin)
            db.commit()
            logger.info("Default admin user created.")
        else:
            logger.info("Default admin user already exists, ensuring password is correct.")
            admin_user.hashed_password = hashed_password # Force update password
            db.commit()
            db.refresh(admin_user)
            logger.info("Default admin user password ensured.")
        
        # Populate PEPList
        pep_list = [
            {"full_name": "Emmerson Mnangagwa", "country": "Zimbabwe", "position": "President"},
            {"full_name": "Constantino Chiwenga", "country": "Zimbabwe", "position": "Vice President"},
            {"full_name": "Donald Trump", "country": "USA", "position": "Former President"},
            {"full_name": "Joe Biden", "country": "USA", "position": "President"},
            {"full_name": "Theresa May", "country": "UK", "position": "Former Prime Minister"},
            {"full_name": "Angela Merkel", "country": "Germany", "position": "Former Chancellor"},
            {"full_name": "Xi Jinping", "country": "China", "position": "President"},
        ]
        for pep_data in pep_list:
            pep_exists = db.query(PEPList).filter(PEPList.full_name == pep_data["full_name"]).first()
            if not pep_exists:
                new_pep = PEPList(**pep_data)
                db.add(new_pep)
        
        # Populate SanctionsList
        sanctions_list = [
            {"entity_name": "Al-Qaeda", "list_name": "UN Sanctions", "entity_type": "Organization"},
            {"entity_name": "Islamic State of Iraq and the Levant (ISIL)", "list_name": "UN Sanctions", "entity_type": "Organization"},
        ]
        for sanction_data in sanctions_list:
            sanction_exists = db.query(SanctionsList).filter(SanctionsList.entity_name == sanction_data["entity_name"]).first()
            if not sanction_exists:
                new_sanction = SanctionsList(**sanction_data)
                db.add(new_sanction)
        
        # Ensure admin user also has a customer account for testing Control 1
        admin_customer_id = admin_user.username # Use admin's username as customer_id
        admin_customer = db.query(Customer).filter(Customer.username == admin_customer_id).first()
        if not admin_customer:
            logger.info(f"Creating customer account for admin user: {admin_customer_id}")
            new_customer = Customer(
                id=str(uuid.uuid4()),
                customer_id=admin_customer_id,
                username=admin_customer_id,
                hashed_password=admin_user.hashed_password, # Use admin's hashed password
                full_name=admin_user.full_name,
                email=admin_user.email,
                account_opening_date=datetime.now(),
                risk_rating="LOW" # Default risk rating
            )
            db.add(new_customer)
            db.commit()
            db.refresh(new_customer)
            logger.info(f"Customer account {admin_customer_id} created for admin user.")

            # Create a default account for this new customer
            account = Account(
                id=str(uuid.uuid4()),
                account_number=f"ACC{random.randint(100000000, 999999999)}",
                customer_id=admin_customer_id,
                account_type="SAVINGS",
                currency="USD",
                balance=1000000.0,  # Give a high balance for testing
                status="ACTIVE",
                opening_date=datetime.now(),
            )
            db.add(account)
            db.commit()
            logger.info(f"Default account created for admin customer {admin_customer_id}.")
        else:
            logger.info(f"Customer account for admin user {admin_customer_id} already exists.")
            # Ensure the password is in sync if admin_user.hashed_password was updated
            if admin_customer.hashed_password != admin_user.hashed_password:
                admin_customer.hashed_password = admin_user.hashed_password
                db.commit()
                db.refresh(admin_customer)
                logger.info("Admin customer password synced with admin user password.")

        

        db.commit()
        db.close()

    except Exception as e:
        logger.error(f"Error during startup: {e}")
    # ML models will be initialized on first use
    asyncio.create_task(broadcast_updates())
    asyncio.create_task(broadcast_system_metrics())
    yield
    # Shutdown
    logger.info("Shutting down system")

app = FastAPI(
    title="Banking AML Transaction Monitoring System",
    description="Professional AML compliance and transaction monitoring platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory="templates")

def risklevel(risk_score: float) -> str:
    if risk_score >= 0.9:
        return 'critical'
    elif risk_score >= 0.7:
        return 'high'
    elif risk_score >= 0.4:
        return 'medium'
    else:
        return 'low'

def format_currency(amount: float, currency: str = "USD") -> str:
    if currency == "USD":
        return f"${amount:,.2f}"
    elif currency == "ZWL":
        return f"Z${amount:,.2f}"
    elif currency == "ZAR":
        return f"R{amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"

templates.env.filters['risklevel'] = risklevel
templates.env.globals['format_currency'] = format_currency

# --- Security ---

# Password Hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Security Schemes
admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/token")
staff_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/staff/token")


# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    email: str
    role: str

class TransactionCreate(BaseModel):
    customer_id: str
    account_number: str
    transaction_type: str
    amount: float
    currency: str = "USD"
    channel: str
    counterparty_account: Optional[str] = None
    counterparty_name: Optional[str] = None
    counterparty_bank: Optional[str] = None
    reference: Optional[str] = None
    narrative: Optional[str] = None

class AlertResponse(BaseModel):
    id: str
    alert_type: str
    risk_score: float
    status: str
    created_at: datetime
    transaction_id: Optional[str] = None
    customer_id: Optional[str] = None
    description: str
    # Add transaction details
    transaction_amount: Optional[float] = None
    transaction_currency: Optional[str] = None

    class Config:
        from_attributes = True

class CaseResponse(BaseModel):
    id: str
    case_number: str
    status: str
    priority: str
    created_at: datetime
    target_completion_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    alert: Optional[AlertResponse] = None

    class Config:
        from_attributes = True

class CaseUpdate(BaseModel):
    status: str
    notes: str
    assigned_to: Optional[str] = None

class BulkAlertAction(BaseModel):
    alert_ids: List[str]
    action: str
    assigned_to: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None

class AssignAlert(BaseModel):
    user_id: str

class ReportFilters(BaseModel):
    report_period: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    report_type: Optional[str] = None
    risk_level: Optional[str] = None
    currency: Optional[str] = None

class ConfigurationUpdate(BaseModel):
    risk_threshold_low: float
    risk_threshold_medium: float
    risk_threshold_high: float
    email_notifications_enabled: bool
    sms_notifications_enabled: bool
    alert_retention_days: int
    ml_scoring_enabled: bool
    anomaly_threshold: float
    model_retrain_interval_days: int
    limit_usd_low: int
    limit_usd_medium: int
    limit_usd_high: int

class TransactionStatusUpdate(BaseModel):
    status: str

class CreateCaseRequest(BaseModel):
    alert_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: str = Field("MEDIUM") # Default value
    assigned_to: Optional[str] = None
    investigation_notes: Optional[str] = None
    target_completion_date: Optional[datetime] = None # Use datetime type

# --- Utility Functions ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)



def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=8)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# --- Dependencies ---

async def get_current_user_dependency(token: str = Depends(admin_oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    # Allow admin and aml_analyst roles to access this dependency
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Not authorized to perform this action",
        )
    return user

async def get_optional_user(request: Request, db: Session = Depends(get_db)):
    logger.info(f"Request headers: {request.headers}")
    logger.info(f"Request cookies: {request.cookies}")
    try:
        token = request.cookies.get("admin_token")
        if not token:
            logger.info("No admin_token cookie found.")
            return

        logger.info(f"Found admin_token cookie: {token}")

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        logger.info(f"Decoded token payload: {payload}")

        if username is None:
            logger.warning("Token payload does not contain username (sub).")
            return

        user = db.query(User).filter(User.username == username).first()
        if user:
            logger.info(f"User '{username}' successfully retrieved from token.")
        else:
            logger.warning(f"User '{username}' not found in DB after token decode.")
        return user

    except JWTError as e:
        logger.error(f"Error decoding token: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in get_optional_user: {e}")

async def get_current_customer(request: Request, db: Session = Depends(get_db)):
    logger.info(f"Attempting to get current customer. Request cookies: {request.cookies}")
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = request.cookies.get("customer_token")
        if not token:
            logger.warning("No customer_token cookie found.")
            raise credentials_exception

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        logger.info(f"Decoded JWT payload: {payload}")
        username: str = payload.get("sub")
        if username is None:
            logger.warning("JWT payload does not contain 'sub' (username).")
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError as e:
        logger.error(f"JWTError during token decoding: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error in get_current_customer: {e}")
        raise credentials_exception
    customer = db.query(Customer).filter(Customer.username == token_data.username).first()
    if customer is None:
        logger.warning(f"Customer '{token_data.username}' not found in DB.")
        raise credentials_exception
    logger.info(f"Customer '{customer.username}' successfully authenticated.")
    return customer

async def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)):
    logger.info("Entering get_current_user_from_cookie")
    logger.info(f"Attempting to get current user from cookie. Request headers: {request.headers}")
    logger.info(f"Attempting to get current user from cookie. Request cookies: {request.cookies}")
    
    # Try to get token from cookie
    cookie_token = request.cookies.get("admin_token")
    logger.info(f"Cookie token: {cookie_token}")

    # Try to get token from Authorization header (for localStorage approach)
    auth_header = request.headers.get("Authorization")
    header_token = None
    if auth_header and auth_header.startswith("Bearer "):
        header_token = auth_header.split(" ")[1]
        logger.info(f"Header token: {header_token[:10]}...")

    # Determine the token to use: header token takes precedence if present, otherwise cookie token
    auth_token = header_token if header_token else cookie_token
    logger.info(f"Auth token (after determining precedence): {auth_token[:10]}..." if auth_token else "No auth token found.")

    if not auth_token:
        logger.warning("No admin_token found in cookie or header. Raising 401 HTTPException.")
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        logger.info(f"Decoded JWT payload: {payload}")
        username: str = payload.get("sub")
        logger.info(f"Username from payload: {username}")
        if username is None:
            logger.warning("Token payload does not contain username (sub).")
            raise HTTPException(status_code=401, detail="Could not validate credentials")

        user = db.query(User).filter(User.username == username).first()
        logger.info(f"User found in DB: {user is not None}")
        if user is None:
            logger.warning(f"User {username} not found in DB.")
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        
        logger.info(f"User {username} successfully authenticated.")
        return user

    except JWTError as e:
        logger.error(f"JWTError during token decoding in get_current_user_from_cookie: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user_from_cookie: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during authentication")

async def get_current_staff_user(request: Request, db: Session = Depends(get_db)):
    logger.info("Entering get_current_staff_user")
    cookie_token = request.cookies.get("staff_token")
    auth_header = request.headers.get("Authorization")
    header_token = None
    if auth_header and auth_header.startswith("Bearer "): header_token = auth_header.split(" ")[1]
    auth_token = header_token if header_token else cookie_token

    if not auth_token: raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise HTTPException(status_code=401, detail="Could not validate credentials")

        user = db.query(User).filter(User.username == username).first()
        if user is None: raise HTTPException(status_code=401, detail="Could not validate credentials")
        
        # Check if the user has a staff role
        staff_roles = ["admin", "compliance_officer", "aml_analyst", "supervisor"]
        if user.role not in staff_roles:
            raise HTTPException(status_code=403, detail="Not authorized to access staff portal")

        return user

    except JWTError as e:
        logger.error(f"JWTError during token decoding in get_current_staff_user: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        logger.error(f"Unexpected error in get_current_staff_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during authentication")

async def get_report_filters(
    report_period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    report_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    currency: Optional[str] = None,
) -> ReportFilters:
    return ReportFilters(
        report_period=report_period,
        start_date=start_date,
        end_date=end_date,
        report_type=report_type,
        risk_level=risk_level,
        currency=currency,
    )


# --- Frontend Routes ---

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    users = db.query(User).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "users": users, "user": current_user})

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    current_user = await get_current_user_from_cookie(request, db=db)
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    # Fetch recent alerts
    recent_alerts = db.query(Alert).order_by(desc(Alert.created_at)).limit(10).all() # Limit to 10 for display
    
    return templates.TemplateResponse("admin.html", {"request": request, "user": current_user, "alerts": recent_alerts})

@app.get("/admin/profile", response_class=HTMLResponse)
async def admin_profile_page(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse("admin_profile.html", {"request": request, "user": current_user})

@app.get("/cases", response_class=HTMLResponse)
async def case_management(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse("case-management.html", {"request": request, "user": current_user})

@app.get("/alerts", response_class=HTMLResponse)
async def alerts_view(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse("alerts.html", {"request": request, "user": current_user})

@app.get("/reports", response_class=HTMLResponse)
async def reports_view(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse("reports.html", {"request": request, "user": current_user})









# --- Customer Portal Frontend Routes ---

@app.get("/portal/login", response_class=HTMLResponse)
async def customer_login_page(request: Request):
    return templates.TemplateResponse("customer/login.html", {"request": request})

@app.get("/portal/register", response_class=HTMLResponse)
async def customer_register_page(request: Request):
    return templates.TemplateResponse("customer/register.html", {"request": request})

@app.get("/portal/dashboard", response_class=HTMLResponse)
async def customer_dashboard_page(request: Request, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    accounts = db.query(Account).filter(Account.customer_id == current_customer.customer_id).all()
    transactions = db.query(Transaction).filter(Transaction.customer_id == current_customer.customer_id).order_by(desc(Transaction.created_at)).limit(10).all()
    
    transactions_data = [
        {
            "date": t.created_at.strftime('%Y-%m-%d %H:%M'),
            "type": t.transaction_type,
            "amount": f"{t.currency} {t.amount:.2f}",
            "description": t.narrative,
            "channel": t.channel
        } for t in transactions
    ]
    
    return templates.TemplateResponse("customer/dashboard.html", {"request": request, "customer": current_customer, "accounts": accounts, "transactions_data": transactions_data})

@app.get("/portal/payment", response_class=HTMLResponse)
async def customer_payment_page(request: Request, current_customer: Customer = Depends(get_current_customer)):
    return templates.TemplateResponse("customer/payment.html", {"request": request, "customer": current_customer})

@app.get("/portal/transfer", response_class=HTMLResponse)
async def customer_transfer_page(request: Request, current_customer: Customer = Depends(get_current_customer)):
    return templates.TemplateResponse("customer/transfer.html", {"request": request, "customer": current_customer})

# --- Monitoring ---
@app.get('/monitoring/real-time', response_class=HTMLResponse)
async def monotoring_real_time(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('monitoring/real-time.html', {"request": request, "user": current_user})

@app.get('/monitoring/transactions', response_class=HTMLResponse)
async def monotoring_transactions(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('monitoring/transactions.html', {"request": request, "user": current_user})

@app.get('/monitoring/customers', response_class=HTMLResponse)
async def monotoring_customers(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('monitoring/customers.html', {"request": request, "user": current_user})

# --- Sanctions ---
class ScreeningRequest(BaseModel):
    name: str
    country: Optional[str] = None

@app.get('/sanctions/screening', response_class=HTMLResponse)
async def sanctions_screening(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('sanctions/screening.html', {"request": request, "user": current_user})

@app.post("/api/sanctions/screen/single")
async def screen_single_entity(screening_request: ScreeningRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    logger.info(f"Received single screening request: {screening_request.dict()}")
    # The screen_transaction method expects transaction_data, so we'll adapt the screening_request
    # For single entity screening, we can construct a dummy transaction_data
    transaction_data = {
        "customer_id": "single_entity_screening", # Dummy ID
        "counterparty_name": screening_request.name,
        "counterparty_country": screening_request.country, # Pass country for screening
        "counterparty_bank": None, # Not provided in single screening
        "amount": 0, # Dummy value
        "currency": "USD", # Dummy value
        "channel": "ManualScreening" # Dummy value
    }
    logger.info(f"Constructed transaction_data for single screening: {transaction_data}")
    
    screening_results = await sanctions_engine.screen_transaction(transaction_data, db)
    logger.info(f"Sanctions engine returned for single screening: {screening_results}")
    
    # Extract relevant parts for the frontend
    return {
        "name": screening_request.name,
        "country": screening_request.country,
        "sanctions_matches": screening_results.get("matches", []),
        "pep_matches": screening_results.get("pep_matches", []),
        "adverse_media_hits": screening_results.get("adverse_media_hits", []),
        "matched": screening_results.get("matched", False),
        "risk_score": screening_results.get("risk_score", 0.0),
        "details": screening_results.get("details", "")
    }

@app.post("/api/sanctions/screen/bulk")
async def screen_bulk_entities(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    logger.info(f"Received bulk screening request for file: {file.filename}")
    results = []
    try:
        contents = await file.read()
        decoded_content = contents.decode('utf-8').splitlines()
        for line in decoded_content:
            line = line.strip()
            if not line:
                continue  # Skip empty lines

            parts = line.split(',')
            name = parts[0].strip()
            if not name:
                continue # Skip lines with no name

            country = parts[1].strip() if len(parts) > 1 else None
            
            logger.info(f"Processing bulk entry - Name: {name}, Country: {country}")
            
            # Construct dummy transaction_data for screen_transaction
            transaction_data = {
                "customer_id": "bulk_entity_screening", # Dummy ID
                "counterparty_name": name,
                "counterparty_country": country, # Pass country for screening
                "counterparty_bank": None,
                "amount": 0,
                "currency": "USD",
                "channel": "BulkScreening"
            }
            logger.info(f"Constructed transaction_data for bulk screening: {transaction_data}")
            
            screening_results = await sanctions_engine.screen_transaction(transaction_data, db)
            logger.info(f"Sanctions engine returned for bulk entry: {screening_results}")
            
            results.append({
                "name": name,
                "country": country,
                "sanctions_matches": screening_results.get("matches", []),
                "pep_matches": screening_results.get("pep_matches", []),
                "adverse_media_hits": screening_results.get("adverse_media_hits", []),
                "matched": screening_results.get("matched", False),
                "risk_score": screening_results.get("risk_score", 0.0),
                "details": screening_results.get("details", "")
            })
    except Exception as e:
        logger.error(f"Error during bulk screening: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")
    logger.info(f"Bulk screening completed. Total results: {len(results)}")
    return results

@app.get("/api/sanctions/lists")
async def get_sanctions_lists(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    params = request.query_params

    draw = int(params.get("draw", 1))
    start = int(params.get("start", 0))
    length = int(params.get("length", 10))
    search_value = params.get("search[value]", "")

    query = db.query(SanctionsList)

    # Apply search filter
    if search_value:
        query = query.filter(
            or_(
                SanctionsList.entity_name.ilike(f"%{search_value}%"),
                SanctionsList.list_name.ilike(f"%{search_value}%"),
                SanctionsList.entity_type.ilike(f"%{search_value}%"),
                SanctionsList.nationality.ilike(f"%{search_value}%"),
            )
        )

    # Total records before pagination
    total_records = query.count()

    # Apply ordering
    order_column_index = int(params.get("order[0][column]", 0))
    order_direction = params.get("order[0][dir]", "asc")
    order_column_name = params.get(f"columns[{order_column_index}][data]")

    if order_column_name and hasattr(SanctionsList, order_column_name):
        if order_direction == "asc":
            query = query.order_by(asc(getattr(SanctionsList, order_column_name)))
        else:
            query = query.order_by(desc(getattr(SanctionsList, order_column_name)))
    else: # Default ordering if column name is invalid or not provided
        query = query.order_by(desc(SanctionsList.created_at))

    # Apply pagination
    query = query.offset(start).limit(length)

    logger.info(f"Executing query for sanctions lists with start={start}, length={length}, search_value='{search_value}'")
    sanctions_lists = query.all()
    logger.info(f"Fetched {len(sanctions_lists)} sanctions list entries.")

    # Prepare data for DataTables
    data = []
    for item in sanctions_lists:
        data.append({
            "id": str(item.id),
            "list_name": item.list_name,
            "entity_name": item.entity_name,
            "entity_type": item.entity_type,
            "nationality": item.nationality,
            "list_date": item.list_date.isoformat() if item.list_date else None,
            "program": item.program,
            "remarks": item.remarks,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "actions": f"<button class='btn btn-sm btn-info view-btn' data-id='{item.id}'>View</button> <button class='btn btn-sm btn-warning edit-btn' data-id='{item.id}'>Edit</button>"
        })

    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records, # For now, recordsFiltered is same as recordsTotal after search filter
        "data": data,
    }

# PEP List API Endpoints
@app.get("/api/pep/lists")
async def get_pep_lists(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    params = request.query_params

    draw = int(params.get("draw", 1))
    start = int(params.get("start", 0))
    length = int(params.get("length", 10))
    search_value = params.get("search[value]", "")

    query = db.query(PEPList)

    # Apply search filter
    if search_value:
        query = query.filter(
            or_(
                PEPList.full_name.ilike(f"%{search_value}%"),
                PEPList.country.ilike(f"%{search_value}%"),
                PEPList.position.ilike(f"%{search_value}%"),
            )
        )

    # Total records before pagination
    total_records = query.count()

    # Apply ordering
    order_column_index = int(params.get("order[0][column]", 0))
    order_direction = params.get("order[0][dir]", "asc")
    order_column_name = params.get(f"columns[{order_column_index}][data]")

    # Map DataTables column names to model attributes
    pep_column_map = {
        "0": "full_name",
        "1": "country",
        "2": "position",
        "3": "start_date",
    }
    
    if order_column_name and pep_column_map.get(str(order_column_index)):
        mapped_column = pep_column_map[str(order_column_index)]
        if hasattr(PEPList, mapped_column):
            if order_direction == "asc":
                query = query.order_by(asc(getattr(PEPList, mapped_column)))
            else:
                query = query.order_by(desc(getattr(PEPList, mapped_column)))
    else: # Default ordering if column name is invalid or not provided
        query = query.order_by(desc(PEPList.created_at))

    # Apply pagination
    query = query.offset(start).limit(length)

    logger.info(f"Executing query for PEP lists with start={start}, length={length}, search_value='{search_value}'")
    pep_lists = query.all()
    logger.info(f"Fetched {len(pep_lists)} PEP list entries.")

    # Prepare data for DataTables
    data = []
    for item in pep_lists:
        data.append({
            "id": str(item.id),
            "name": item.full_name,
            "country": item.country,
            "position": item.position,
            "listed_since": item.start_date.isoformat() if item.start_date else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "actions": f"<button class='btn btn-sm btn-info view-btn' data-id='{item.id}'>View</button> <button class='btn btn-sm btn-warning edit-btn' data-id='{item.id}'>Edit</button>"
        })

    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records, # For now, recordsFiltered is same as recordsTotal after search filter
        "data": data,
    }

@app.get("/api/pep/lists/{pep_id}")
async def get_pep_list_details(
    pep_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    if isinstance(current_user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Not authenticated")

    pep_list_entry = db.query(PEPList).filter(PEPList.id == pep_id).first()
    if not pep_list_entry:
        raise HTTPException(status_code=404, detail="PEP list entry not found")

    return {
        "id": str(pep_list_entry.id),
        "full_name": pep_list_entry.full_name,
        "country": pep_list_entry.country,
        "position": pep_list_entry.position,
        "start_date": pep_list_entry.start_date.isoformat() if pep_list_entry.start_date else None,
        "created_at": pep_list_entry.created_at.isoformat() if pep_list_entry.created_at else None,
        "updated_at": pep_list_entry.updated_at.isoformat() if pep_list_entry.updated_at else None,
    }

@app.post("/api/pep/lists/add")
async def add_pep_list_entry(
    pep_list_data: PEPListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    logger.info(f"Received PEP list add request: {pep_list_data.dict()}")
    if isinstance(current_user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Not authenticated")

    new_entry = PEPList(
        full_name=pep_list_data.full_name,
        country=pep_list_data.country,
        position=pep_list_data.position,
        start_date=pep_list_data.start_date,
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return {"message": "PEP list entry added successfully!", "id": str(new_entry.id)}

@app.put("/api/pep/lists/{pep_id}")
async def update_pep_list_entry(
    pep_id: str,
    pep_list_data: PEPListUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    if isinstance(current_user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Not authenticated")

    existing_entry = db.query(PEPList).filter(PEPList.id == pep_id).first()
    if not existing_entry:
        raise HTTPException(status_code=404, detail="PEP list entry not found")

    for field, value in pep_list_data.dict(exclude_unset=True).items():
        setattr(existing_entry, field, value)

    db.commit()
    db.refresh(existing_entry)
    return {"message": "PEP list entry updated successfully!", "id": str(existing_entry.id)}

# Pydantic model for creating a new SanctionsList entry
class SanctionsListCreate(BaseModel):
    list_name: str
    entity_name: str
    entity_type: Optional[str] = None
    nationality: Optional[str] = None
    program: Optional[str] = None
    remarks: Optional[str] = None

class PEPListCreate(BaseModel):
    full_name: str
    country: Optional[str] = None
    position: Optional[str] = None
    start_date: Optional[datetime] = None

class PEPListUpdate(BaseModel):
    full_name: Optional[str] = None
    country: Optional[str] = None
    position: Optional[str] = None
    start_date: Optional[datetime] = None

@app.post("/api/sanctions/lists/add")
async def add_sanctions_list_entry(
    sanctions_list_data: SanctionsListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    if isinstance(current_user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Not authenticated")

    new_entry = SanctionsList(
        list_name=sanctions_list_data.list_name,
        entity_name=sanctions_list_data.entity_name,
        entity_type=sanctions_list_data.entity_type,
        nationality=sanctions_list_data.nationality,
        program=sanctions_list_data.program,
        remarks=sanctions_list_data.remarks,
        # list_date and created_at/updated_at will be set by default in the model
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return {"message": "Sanctions list entry added successfully!", "id": str(new_entry.id)}

@app.put("/api/sanctions/lists/{list_id}")
async def update_sanctions_list_entry(
    list_id: str,
    sanctions_list_data: SanctionsListCreate, # Re-use the create model for update
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    if isinstance(current_user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Not authenticated")

    existing_entry = db.query(SanctionsList).filter(SanctionsList.id == list_id).first()
    if not existing_entry:
        raise HTTPException(status_code=404, detail="Sanctions list entry not found")

    existing_entry.list_name = sanctions_list_data.list_name
    existing_entry.entity_name = sanctions_list_data.entity_name
    existing_entry.entity_type = sanctions_list_data.entity_type
    existing_entry.nationality = sanctions_list_data.nationality
    existing_entry.program = sanctions_list_data.program
    existing_entry.remarks = sanctions_list_data.remarks
    # updated_at will be set automatically by SQLAlchemy

    db.commit()
    db.refresh(existing_entry)
    return {"message": "Sanctions list entry updated successfully!", "id": str(existing_entry.id)}

@app.get("/api/sanctions/lists/{list_id}")
async def get_sanctions_list_details(
    list_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    if isinstance(current_user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Not authenticated")

    sanctions_list_entry = db.query(SanctionsList).filter(SanctionsList.id == list_id).first()
    if not sanctions_list_entry:
        raise HTTPException(status_code=404, detail="Sanctions list entry not found")

    return {
        "id": str(sanctions_list_entry.id),
        "list_name": sanctions_list_entry.list_name,
        "entity_name": sanctions_list_entry.entity_name,
        "entity_type": sanctions_list_entry.entity_type,
        "nationality": sanctions_list_entry.nationality,
        "program": sanctions_list_entry.program,
        "remarks": sanctions_list_entry.remarks,
        "list_date": sanctions_list_entry.list_date.isoformat() if sanctions_list_entry.list_date else None,
        "created_at": sanctions_list_entry.created_at.isoformat() if sanctions_list_entry.created_at else None,
        "updated_at": sanctions_list_entry.updated_at.isoformat() if sanctions_list_entry.updated_at else None,
    }

@app.get('/sanctions/lists', response_class=HTMLResponse)
async def sanctions_lists(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('sanctions/lists.html', {"request": request, "user": current_user})

@app.get('/sanctions/lists/add', response_class=HTMLResponse)
async def add_sanctions_list_page(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('sanctions/add_list.html', {"request": request, "user": current_user})

@app.get('/sanctions/lists/view/{list_id}', response_class=HTMLResponse)
async def view_sanctions_list_page(list_id: str, request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('sanctions/view_list.html', {"request": request, "user": current_user, "list_id": list_id})

@app.get('/sanctions/lists/edit/{list_id}', response_class=HTMLResponse)
async def edit_sanctions_list_page(list_id: str, request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('sanctions/edit_list.html', {"request": request, "user": current_user, "list_id": list_id})

@app.get('/sanctions/pep', response_class=HTMLResponse)
async def sanctions_pep(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('sanctions/pep.html', {"request": request, "user": current_user})

@app.get('/sanctions/pep/add', response_class=HTMLResponse)
async def add_pep_page(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('sanctions/add_pep.html', {"request": request, "user": current_user})

@app.get('/sanctions/pep/view/{pep_id}', response_class=HTMLResponse)
async def view_pep_page(pep_id: str, request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('sanctions/view_pep.html', {"request": request, "user": current_user, "pep_id": pep_id})

@app.get('/sanctions/pep/edit/{pep_id}', response_class=HTMLResponse)
async def edit_pep_page(pep_id: str, request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse('sanctions/edit_pep.html', {"request": request, "user": current_user, "pep_id": pep_id})

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- API Endpoints ---

# --- Admin API Endpoints ---

@app.post("/api/admin/register", response_model=Token)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        hashed_password=hashed_password,
        full_name=user.full_name,
        email=user.email,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/admin/token")
async def login_for_access_token_admin(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Set the admin_token as a non-HttpOnly cookie (accessible by JS)
    response.set_cookie(
        key="admin_token",
        value=access_token,
        httponly=False, # Changed to False for localStorage approach
        max_age=access_token_expires.total_seconds(),
        expires=access_token_expires.total_seconds(),
        samesite="Lax",
        secure=not settings.DEBUG, # True if not in debug mode (i.e., HTTPS), False for HTTP
        path="/"
    )
    logger.info(f"DEBUG setting: {settings.DEBUG}, Secure cookie flag: {not settings.DEBUG}")
    logger.info(f"Admin token cookie set for user: {user.username}")
    logger.info(f"Access token value (first 10 chars): {access_token[:10]}...")
    logger.info("response.set_cookie call executed.")
    logger.info(f"Set-Cookie header: {response.headers.get('Set-Cookie')}")
    logger.info(f"Set-Cookie header: {response.headers.get('Set-Cookie')}")

    redirect_url = "/admin"
    

    return {"message": "Login successful", "access_token": access_token, "token_type": "bearer", "redirect_url": redirect_url}

@app.post("/api/staff/token")
async def login_for_access_token_staff(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    staff_roles = ["admin", "compliance_officer", "aml_analyst", "supervisor"]
    if user.role not in staff_roles:
        raise HTTPException(status_code=403, detail="Not authorized to access staff portal")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    response.set_cookie(
        key="staff_token",
        value=access_token,
        httponly=False,
        max_age=access_token_expires.total_seconds(),
        expires=access_token_expires.total_seconds(),
        samesite="Lax",
        secure=not settings.DEBUG,
        path="/"
    )
    logger.info(f"Staff token cookie set for user: {user.username}")

    return {"message": "Login successful", "access_token": access_token, "token_type": "bearer", "redirect_url": "/staff/dashboard"}

@app.post("/api/staff/logout")
async def staff_logout(response: Response):
    response.delete_cookie(key="staff_token", path="/", samesite="Lax")
    logger.info("Staff token cookie deleted.")
    return {"message": "Logged out successfully"}

@app.get("/staff/login", response_class=HTMLResponse)
async def staff_login_page(request: Request):
    return templates.TemplateResponse("staff_login.html", {"request": request})

@app.get("/staff/dashboard", response_class=HTMLResponse)
async def staff_dashboard_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_staff_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse("staff_dashboard.html", {"request": request, "user": current_user})







@app.post("/api/admin/logout")
async def admin_logout(response: Response):
    response.delete_cookie(key="admin_token", path="/", samesite="Lax")
    logger.info("Admin token cookie deleted.")
    return {"message": "Logged out successfully"}

@app.post("/api/test/create_customer_with_account")
async def create_test_customer_with_account(
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(...),
    initial_balance: float = Form(1000.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Helper endpoint to create a test customer with a default account."""
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already registered as a user.")
    if db.query(Customer).filter(Customer.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered as a customer.")

    # Create Customer
    new_customer = Customer(
        id=str(uuid.uuid4()),
        customer_id=username, # Using username as customer_id for simplicity
        username=username,
        full_name=full_name,
        email=email,
        account_opening_date=datetime.now(),
        hashed_password=get_password_hash("password"), # Default password for test customer
        risk_rating=RiskRating.LOW
    )
    db.add(new_customer)
    db.flush() # Flush to get customer_id for account

    # Create Account for Customer
    new_account = Account(
        id=str(uuid.uuid4()),
        account_number=f"ACC{random.randint(100000000, 999999999)}",
        customer_id=new_customer.customer_id,
        account_type="SAVINGS",
        currency="USD",
        balance=initial_balance,
        status="ACTIVE",
        opening_date=datetime.now()
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_customer)
    db.refresh(new_account)

    logger.info(f"Test customer {username} and account {new_account.account_number} created.")
    return {"message": "Test customer and account created successfully", "customer_id": new_customer.customer_id, "account_number": new_account.account_number}

@app.post("/api/test/simulate_normal_incoming_transactions")
async def simulate_normal_incoming_transactions(
    customer_id: str = Form(...),
    account_number: str = Form(...),
    amount: float = Form(...),
    count: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Helper endpoint to simulate multiple normal incoming transactions for a customer."""
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    account = db.query(Account).filter(Account.account_number == account_number).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
    if not account or account.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Account not found or does not belong to customer.")

    transactions_created = []
    for i in range(count):
        db_transaction = Transaction(
            customer_id=customer_id,
            account_number=account_number,
            transaction_type="CREDIT",
            amount=amount,
            base_amount=await currency_service.convert_to_base(amount, "USD"),
            currency="USD",
            channel="Simulated",
            counterparty_account=f"SIMULATED_CP_{i}",
            counterparty_name="Simulated Counterparty",
            narrative=f"Simulated normal incoming transaction {i+1}",
            processed_by=current_user.username,
            status=TransactionStatus.COMPLETED
        )
        db.add(db_transaction)
        transactions_created.append(db_transaction)
    
    db.commit()
    for t in transactions_created: # Refresh to get IDs
        db.refresh(t)

    logger.info(f"Simulated {count} normal incoming transactions for customer {customer_id}.")
    return {"message": f"Successfully simulated {count} normal incoming transactions.", "transaction_ids": [str(t.id) for t in transactions_created]}

@app.post("/api/test/simulate_unusual_incoming_transaction")
async def simulate_unusual_incoming_transaction(
    customer_id: str = Form(...),
    account_number: str = Form(...),
    amount: float = Form(...),
    currency: str = Form("USD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Helper endpoint to simulate an unusual incoming transaction for a customer, triggering Control 2."""
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    account = db.query(Account).filter(Account.account_number == account_number).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
    if not account or account.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Account not found or does not belong to customer.")

    # Create the unusual transaction record
    db_transaction = Transaction(
        customer_id=customer_id,
        account_number=account_number,
        transaction_type="CREDIT",
        amount=amount,
        base_amount=await currency_service.convert_to_base(amount, currency),
        currency=currency,
        channel="Simulated_Unusual",
        counterparty_account="UNUSUAL_CP",
        counterparty_name="Unusual Counterparty",
        narrative="Simulated unusual incoming transaction to trigger Control 2",
        processed_by=current_user.username,
        status=TransactionStatus.PENDING
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    # Trigger AML controls in background
    background_tasks.add_task(
        process_transaction_controls,
        db_transaction.id,
        {
            "customer_id": customer_id,
            "base_amount": db_transaction.base_amount,
            "transaction_type": "CREDIT",
            "channel": "Simulated_Unusual",
            "id": str(db_transaction.id) # Pass transaction ID for logging
        }
    )

    logger.info(f"Simulated unusual incoming transaction for customer {customer_id} with amount {amount}.")
    return {"message": "Successfully simulated unusual incoming transaction.", "transaction_id": str(db_transaction.id)}

@app.get("/api/admin/users")
async def get_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    users = db.query(User).all()
    return users

@app.get("/api/admin/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/api/admin/users/{user_id}")
async def update_user(user_id: str, user_data: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.username = user_data.username
    user.full_name = user_data.full_name
    user.email = user_data.email
    user.role = user_data.role
    if user_data.password:
        user.hashed_password = get_password_hash(user_data.password)
    
    db.commit()
    return {"message": "User updated successfully"}

@app.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

class TransferRequest(BaseModel):
    recipient_account: str
    amount: float
    currency: str

@app.post("/api/admin/create_self_transaction")
async def create_admin_self_transaction(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Create a self-posting transaction for the logged-in admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # For demonstration, we'll find the admin's customer account
    admin_customer = db.query(Customer).filter(Customer.username == current_user.username).first()
    if not admin_customer:
        raise HTTPException(status_code=404, detail="Admin customer account not found.")

    # Find the admin's account
    admin_account = db.query(Account).filter(Account.customer_id == admin_customer.customer_id).first()
    if not admin_account:
        raise HTTPException(status_code=404, detail="Admin account not found.")

    # Create a self-posting transaction
    transaction_data = {
        "customer_id": admin_customer.customer_id,
        "account_number": admin_account.account_number,
        "transaction_type": "DEBIT",
        "amount": 100.0,
        "currency": "USD",
        "channel": "Internal",
        "counterparty_account": admin_account.account_number,
        "counterparty_name": admin_customer.full_name,
        "counterparty_bank": "Self",
        "reference": "Admin self-posting test",
        "narrative": "Admin self-posting transaction for control testing."
    }

    # Use the existing transaction processing logic
    # In a real app, you might want to refactor this to a common function
    db_transaction = Transaction(**transaction_data, base_amount=100.0, processed_by=current_user.username, status=TransactionStatus.PENDING)
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    # Background processing for AML controls
    background_tasks = BackgroundTasks()
    background_tasks.add_task(
        process_transaction_controls,
        db_transaction.id,
        transaction_data
    )

    return {"message": "Admin self-posting transaction created successfully", "transaction_id": db_transaction.id}



@app.post("/api/admin/sanctions/upload")
async def upload_sanctions_list(file: UploadFile = File(...), current_user: User = Depends(get_current_user_dependency)):
    # In a real application, this would process the uploaded file and add entries to the database
    logger.info(f"Sanctions list upload triggered by {current_user.username} for file: {file.filename}")
    return {"message": f"File {file.filename} uploaded successfully for sanctions processing."}

@app.post("/api/admin/system/restart")
async def restart_system(current_user: User = Depends(get_current_user_dependency)):
    logger.info(f"System restart triggered by {current_user.username}")
    # In a real application, this would trigger a graceful shutdown and restart of the application process
    # For demonstration, we just return a message. Actual restart logic is platform-dependent.
    return {"message": "System restart initiated. The application may become temporarily unavailable."}

@app.get("/api/admin/users/{user_id}/audit")
async def get_user_audit(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    audit_logs = db.query(AuditLog).filter(AuditLog.user_id == user_id).order_by(desc(AuditLog.timestamp)).all()
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "timestamp": log.timestamp.isoformat(),
            "performed_by": log.user_id # Assuming user_id is the performer
        } for log in audit_logs
    ]

@app.get("/api/admin/system-status")
async def get_system_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    today = datetime.now().date()
    transactions_processed_today = db.query(Transaction).filter(Transaction.created_at >= today).count()
    alerts_generated_today = db.query(Alert).filter(Alert.created_at >= today).count()
    cases_opened_today = db.query(Case).filter(Case.created_at >= today).count()
    return {
        "database_status": "OK",
        "ml_engine_status": "OK",
        "websocket_status": "OK",
        "email_service_status": "OK",
        "cpu_usage": 50,
        "memory_usage": 60,
        "disk_usage": 70,
        "active_connections": 10,
        "transactions_processed_today": transactions_processed_today,
        "alerts_generated_today": alerts_generated_today,
        "cases_opened_today": cases_opened_today,
        "ml_predictions_today": 200
    }

@app.get("/api/admin/configuration")
async def get_configuration(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    config_settings = db.query(SystemConfiguration).all()
    config_dict = {
        item.config_key: item.config_value for item in config_settings
    }

    # Provide default values if not found in DB
    return {
        "risk_threshold_low": float(config_dict.get("risk_threshold_low", 0.3)),
        "risk_threshold_medium": float(config_dict.get("risk_threshold_medium", 0.6)),
        "risk_threshold_high": float(config_dict.get("risk_threshold_high", 0.8)),
        "email_notifications_enabled": config_dict.get("email_notifications_enabled", "True").lower() == "true",
        "sms_notifications_enabled": config_dict.get("sms_notifications_enabled", "False").lower() == "true",
        "alert_retention_days": int(config_dict.get("alert_retention_days", 90)),
        "ml_scoring_enabled": config_dict.get("ml_scoring_enabled", "True").lower() == "true",
        "anomaly_threshold": float(config_dict.get("anomaly_threshold", 0.7)),
        "model_retrain_interval_days": int(config_dict.get("model_retrain_interval_days", 30)),
        "transaction_limits": {
            "USD": {
                "low_risk": float(config_dict.get("limit_usd_low", 1000)),
                "medium_risk": float(config_dict.get("limit_usd_medium", 10000)),
                "high_risk": float(config_dict.get("limit_usd_high", 50000))
            }
        }
    }

@app.post("/api/admin/configuration")
async def update_configuration(
    config_update: ConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    for key, value in config_update.dict().items():
        db_config = db.query(SystemConfiguration).filter(SystemConfiguration.config_key == key).first()
        if db_config:
            db_config.config_value = str(value)
        else:
            db_config = SystemConfiguration(config_key=key, config_value=str(value))
            db.add(db_config)
    db.commit()
    return {"message": "Configuration updated successfully"}

@app.post("/api/admin/users")
async def create_user(user: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        hashed_password=hashed_password,
        full_name=user.full_name,
        email=user.email,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/api/admin/ml-models")
async def get_ml_models(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    models = db.query(MLModel).all()
    return [
        {
            "id": str(m.id),
            "model_name": m.model_name,
            "model_type": m.model_type,
            "version": m.version,
            "accuracy": m.accuracy,
            "last_trained": m.updated_at.isoformat() if m.updated_at else None,
            "training_data_period": m.training_data_period,
            "is_active": m.is_active
        } for m in models
    ]

@app.post("/api/admin/ml-models/retrain")
async def retrain_ml_models(background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    logger.info(f"ML model retraining triggered by {current_user.username}")
    background_tasks.add_task(ml_engine.train_models, db)
    return {"message": "ML models retraining started successfully. Check logs for progress."}

@app.get("/api/admin/sanctions/lists")
async def get_sanctions_lists_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    ofac_sdn_count = db.query(SanctionsList).filter(SanctionsList.list_name == "OFAC_SDN").count()
    un_sanctions_count = db.query(SanctionsList).filter(SanctionsList.list_name == "UN_SANCTIONS").count()
    pep_count = db.query(PEPList).count()

    # Placeholder for last updated dates, ideally these would be stored in a config or metadata table
    last_updated_ofac = datetime.now() - timedelta(days=random.randint(1, 10))
    last_updated_un = datetime.now() - timedelta(days=random.randint(1, 10))
    last_updated_pep = datetime.now() - timedelta(days=random.randint(1, 10))

    return [
        {
            "list_name": "OFAC SDN List",
            "entries": ofac_sdn_count,
            "last_updated": last_updated_ofac.isoformat(),
            "status": "Active"
        },
        {
            "list_name": "UN Sanctions List",
            "entries": un_sanctions_count,
            "last_updated": last_updated_un.isoformat(),
            "status": "Active"
        },
        {
            "list_name": "PEP Lists",
            "entries": pep_count,
            "last_updated": last_updated_pep.isoformat(),
            "status": "Active"
        }
    ]

@app.post("/api/admin/sanctions/update")
async def update_sanctions(background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    logger.info(f"Sanctions list update triggered by {current_user.username}")
    background_tasks.add_task(sanctions_engine.update_sanctions_lists, db)
    return {"message": "Sanctions lists update started successfully."}


@app.get("/api/monitoring/transactions/recent")
async def get_recent_transactions(db: Session = Depends(get_db), limit: int = 50, current_user: User = Depends(get_current_user_dependency)):
    transactions = db.query(Transaction).order_by(desc(Transaction.created_at)).limit(limit).all()
    return [
        {
            "id": str(t.id),
            "customer_id": t.customer_id,
            "amount": t.amount,
            "currency": t.currency,
            "channel": t.channel,
            "risk_score": t.risk_score, # Assuming Transaction model has risk_score
            "timestamp": t.created_at.isoformat(),
            "ml_prediction": t.ml_prediction if hasattr(t, 'ml_prediction') else None # Assuming ML prediction can be part of transaction
        } for t in transactions
    ]

@app.get("/api/monitoring/alerts/recent")
async def get_recent_alerts(db: Session = Depends(get_db), limit: int = 50, current_user: User = Depends(get_current_user_dependency)):
    alerts = db.query(Alert).order_by(desc(Alert.created_at)).limit(limit).all()
    return [
        {
            "id": str(a.id),
            "alert_type": a.alert_type,
            "risk_score": a.risk_score,
            "description": a.description,
            "customer_id": a.transaction.customer_id if a.transaction else None,
            "timestamp": a.created_at.isoformat()
        } for a in alerts
    ]



@app.get("/api/admin/transactions/recent")
async def get_admin_recent_transactions(db: Session = Depends(get_db), limit: int = 100, time_range: str = "30d"):
    end_date = datetime.utcnow()
    if time_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30d":
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(hours=24)

    logger.info(f"Fetching recent transactions for time_range={time_range}, start_date={start_date}, end_date={end_date}")

    transactions = db.query(Transaction).filter(Transaction.created_at.between(start_date, end_date)).order_by(desc(Transaction.created_at)).limit(limit).all()
    
    logger.info(f"Returned {len(transactions)} transactions.")

    return [
        {
            "id": str(t.id),
            "customer_id": t.customer_id,
            "amount": t.amount,
            "currency": t.currency,
            "channel": t.channel,
            "risk_score": t.risk_score,
            "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
            "timestamp": t.created_at.isoformat(),
        } for t in transactions
    ]

@app.get("/api/monitoring/transactions")
async def api_get_transactions(request: Request, db: Session = Depends(get_db),
                                 search_term: Optional[str] = None,
                                 transaction_type: Optional[str] = None,
                                 status: Optional[str] = None,
                                 date: Optional[str] = None):
    params = request.query_params
    
    draw = int(params.get("draw", 1))
    start = int(params.get("start", 0))
    length = int(params.get("length", 10))
    
    query = db.query(Transaction)
    
    # Apply filters
    if search_term:
        query = query.filter(or_(
            Transaction.customer_id.ilike(f"%{search_term}%"),
            Transaction.id.ilike(f"%{search_term}%"),
            Transaction.account_number.ilike(f"%{search_term}%")
        ))
    
    if transaction_type and transaction_type != "all":
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    if status and status != "all":
        query = query.filter(Transaction.status == status)
    
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(Transaction.created_at) == filter_date)
        except ValueError:
            pass # Ignore invalid date format

    total_records = db.query(Transaction).count() # Total records before filtering
    records_filtered = query.count() # Total records after filtering
    
    transactions = query.order_by(desc(Transaction.created_at)).offset(start).limit(length).all()
    
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": records_filtered,
        "data": [
            {
                "id": str(t.id),
                "customer_id": t.customer_id,
                "transaction_type": t.transaction_type,
                "amount": t.amount,
                "currency": t.currency,
                "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
                "created_at": t.created_at.isoformat(),
            } for t in transactions
        ]
    }



@app.get("/monitoring/transactions/{transaction_id}", response_class=HTMLResponse)
async def view_transaction_details(transaction_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return templates.TemplateResponse("monitoring/transaction_detail.html", {"request": request, "transaction": transaction, "user": current_user})

@app.get("/api/transactions/{transaction_id}")
async def get_transaction_by_id(transaction_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return {
        "id": str(transaction.id),
        "customer_id": transaction.customer_id,
        "account_number": transaction.account_number,
        "transaction_type": transaction.transaction_type,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "channel": transaction.channel,
        "counterparty_account": transaction.counterparty_account,
        "counterparty_name": transaction.counterparty_name,
        "counterparty_bank": transaction.counterparty_bank,
        "reference": transaction.reference,
        "narrative": transaction.narrative,
        "processed_by": transaction.processed_by,
        "status": transaction.status.value if hasattr(transaction.status, 'value') else str(transaction.status),
        "created_at": transaction.created_at.isoformat(),
        "risk_score": transaction.risk_score,
        "ml_prediction": transaction.ml_prediction if hasattr(transaction, 'ml_prediction') else None
    }

@app.put("/api/transactions/{transaction_id}/status")
async def update_transaction_status(
    transaction_id: str,
    status_update: TransactionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    transaction.status = status_update.status
    db.commit()
    
    return {"message": "Transaction status updated successfully"}

@app.get("/api/monitoring/customers")
async def api_get_customers(request: Request, db: Session = Depends(get_db),
                              search_term: Optional[str] = None,
                              risk_rating: Optional[str] = None):
    params = request.query_params
    
    draw = int(params.get("draw", 1))
    start = int(params.get("start", 0))
    length = int(params.get("length", 10))
    
    query = db.query(Customer)
    
    # Apply filters
    if search_term:
        query = query.filter(or_(
            Customer.full_name.ilike(f"%{search_term}%"),
            Customer.customer_id.ilike(f"%{search_term}%")
        ))
    
    if risk_rating and risk_rating != "all":
        query = query.filter(Customer.risk_rating == risk_rating)

    total_records = db.query(Customer).count() # Total records before filtering
    records_filtered = query.count() # Total records after filtering
    
    customers = query.order_by(desc(Customer.account_opening_date)).offset(start).limit(length).all()
    
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": records_filtered,
        "data": [
            {
                "customer_id": c.customer_id,
                "full_name": c.full_name,
                "risk_rating": c.risk_rating.value if hasattr(c.risk_rating, 'value') else str(c.risk_rating),
                "last_login": c.last_login.isoformat() if c.last_login else None
            } for c in customers
        ]
    }



@app.get("/customers/{customer_id}/profile", response_class=HTMLResponse)
async def view_customer_profile(customer_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return templates.TemplateResponse("monitoring/customer_profile.html", {"request": request, "customer": customer, "user": current_user})

@app.post("/api/admin/backup")
async def create_backup(current_user: User = Depends(get_current_user_dependency)):
    logger.info(f"System backup triggered by {current_user.username}")
    # In a real application, this would trigger a database backup and potentially other system files
    # For demonstration, we just return a message. Actual backup logic is complex.
    return {"message": "System backup initiated. Backup file will be available shortly."}

@app.get("/api/admin/logs/export")
async def export_logs(current_user: User = Depends(get_current_user_dependency)):
    logger.info(f"System logs export triggered by {current_user.username}")
    # In a real application, this would fetch logs from a logging system and return them as a file
    # For demonstration, we return a dummy CSV content.
    dummy_log_content = "timestamp,level,message\n"
    dummy_log_content += f"{datetime.now().isoformat()},INFO,User {current_user.username} exported logs\n"
    dummy_log_content += f"{datetime.now().isoformat()},WARNING,Dummy warning message\n"
    return Response(content=dummy_log_content, media_type="text/csv")




@app.post("/api/transactions/")
async def create_transaction(
    transaction: TransactionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Process new transaction and run AML controls"""
    
    # Convert currency if needed
    base_amount = await currency_service.convert_to_base(
        transaction.amount, transaction.currency
    )
    
    # Create transaction record
    db_transaction = Transaction(
        customer_id=transaction.customer_id,
        account_number=transaction.account_number,
        transaction_type=transaction.transaction_type,
        amount=transaction.amount,
        base_amount=base_amount,
        currency=transaction.currency,
        channel=transaction.channel,
        counterparty_account=transaction.counterparty_account,
        counterparty_name=transaction.counterparty_name,
        counterparty_bank=transaction.counterparty_bank,
        reference=transaction.reference,
        narrative=transaction.narrative,
        processed_by=current_user.username,
        status=TransactionStatus.PENDING
    )
    
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    
    # Background processing for AML controls
    background_tasks.add_task(
        process_transaction_controls,
        db_transaction.id,
        transaction.dict()
    )
    
    return {"message": "Transaction processed", "transaction_id": db_transaction.id}


    

@app.get("/api/alerts/", response_model=List[AlertResponse])
async def get_alerts(
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    time_range: Optional[str] = None,
    risk_level: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    start_date: Optional[str] = None, # Added for custom date range
    end_date: Optional[str] = None,   # Added for custom date range
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user) # Changed dependency to staff user
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    """Get alerts with optional filtering"""
    query = db.query(Alert)
    
    if status:
        query = query.filter(Alert.status == status)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    if priority:
        query = query.filter(Alert.priority == priority)
    if assigned_to:
        if assigned_to == "me":
            query = query.filter(Alert.assigned_to == current_user.username)
        elif assigned_to == "unassigned":
            query = query.filter(Alert.assigned_to == None)
    
    # Handle time_range and custom date range
    if time_range:
        current_time = datetime.now()
        if time_range == "today":
            start_date_filter = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date_filter = current_time
        elif time_range == "7d":
            start_date_filter = current_time - timedelta(days=7)
            end_date_filter = current_time
        elif time_range == "30d":
            start_date_filter = current_time - timedelta(days=30)
            end_date_filter = current_time
        elif time_range == "90d":
            start_date_filter = current_time - timedelta(days=90)
            end_date_filter = current_time
        else: # Default to 24h if time_range is not recognized
            start_date_filter = current_time - timedelta(hours=24)
            end_date_filter = current_time
        query = query.filter(Alert.created_at.between(start_date_filter, end_date_filter))
    elif start_date and end_date:
        try:
            start_date_filter = datetime.fromisoformat(start_date)
            end_date_filter = datetime.fromisoformat(end_date)
            query = query.filter(Alert.created_at.between(start_date_filter, end_date_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for start_date or end_date. Use ISO format (YYYY-MM-DD).")

    if risk_level:
        if risk_level == "low":
            query = query.filter(Alert.risk_score < 0.4)
        elif risk_level == "medium":
            query = query.filter(and_(Alert.risk_score >= 0.4, Alert.risk_score < 0.7))
        elif risk_level == "high":
            query = query.filter(and_(Alert.risk_score >= 0.7, Alert.risk_score < 0.9))
        elif risk_level == "critical":
            query = query.filter(Alert.risk_score >= 0.9)

    alerts = query.options(joinedload(Alert.transaction)).order_by(desc(Alert.created_at))
    if limit is not None:
        alerts = alerts.limit(limit)
    alerts = alerts.all()
    
    return [
        AlertResponse(
            id=alert.id,
            alert_type=alert.alert_type,
            risk_score=alert.risk_score,
            status=alert.status.value if hasattr(alert.status, 'value') else str(alert.status),
            created_at=alert.created_at,
            transaction_id=alert.transaction_id,
            customer_id=alert.transaction.customer_id if alert.transaction else "",
            description=alert.description,
            transaction_amount=alert.transaction.amount if alert.transaction else None,
            transaction_currency=alert.transaction.currency if alert.transaction else None,
        )
        for alert in alerts
    ]

@app.get("/api/alerts/{alert_id}")
async def get_alert(alert_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_staff_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    alert = db.query(Alert).options(joinedload(Alert.transaction)).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

class AlertUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    resolution_notes: Optional[str] = None

@app.get("/api/cases/", response_model=List[CaseResponse])
async def get_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user) # Use staff user dependency
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    """Get cases with optional filtering"""
    query = db.query(Case).options(joinedload(Case.alert).joinedload(Alert.transaction)) # Eager load alert and transaction

    if status:
        query = query.filter(Case.status == status)
    if priority:
        query = query.filter(Case.priority == priority)
    if assigned_to:
        if assigned_to == "me":
            query = query.filter(Case.assigned_to == current_user.username)
        elif assigned_to == "unassigned":
            query = query.filter(Case.assigned_to == None)

    cases = query.order_by(desc(Case.created_at))
    if limit is not None:
        cases = cases.limit(limit)
    cases = cases.all()

    return [
        CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            status=case.status.value if hasattr(case.status, 'value') else str(case.status),
            priority=case.priority,
            assigned_to=case.assigned_to,
            created_at=case.created_at,
            target_completion_date=case.target_completion_date,
            alert=AlertResponse(
                id=case.alert.id,
                alert_type=case.alert.alert_type,
                risk_score=case.alert.risk_score,
                status=case.alert.status.value if hasattr(case.alert.status, 'value') else str(case.alert.status),
                created_at=case.alert.created_at,
                transaction_id=case.alert.transaction_id,
                customer_id=case.alert.transaction.customer_id if case.alert.transaction else "",
                description=case.alert.description,
                transaction_amount=case.alert.transaction.amount if case.alert.transaction else None,
                transaction_currency=case.alert.transaction.currency if case.alert.transaction else None,
            ) if case.alert else None
        )
        for case in cases
    ]

@app.get("/api/cases/{case_id}")
async def get_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    case = db.query(Case).options(joinedload(Case.alert).joinedload(Alert.transaction), joinedload(Case.activities)).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@app.put("/api/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    alert_update: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if alert_update.status:
        alert.status = AlertStatus[alert_update.status] # Convert string to Enum
    if alert_update.assigned_to:
        alert.assigned_to = alert_update.assigned_to
    if alert_update.priority:
        alert.priority = alert_update.priority
    if alert_update.resolution_notes:
        alert.resolution_notes = alert_update.resolution_notes
    
    db.commit()
    db.refresh(alert)
    return {"message": "Alert updated successfully"}

@app.get("/api/cases/", response_model=List[CaseResponse])
async def get_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user) # Changed dependency to staff user
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    """Get cases with optional filtering"""
    query = db.query(Case)

    if status:
        query = query.filter(Case.status == status)
    if priority:
        query = query.filter(Case.priority == priority)
    if assigned_to:
        if assigned_to == "me":
            query = query.filter(Case.assigned_to == current_user.username)
        elif assigned_to == "unassigned":
            query = query.filter(Case.assigned_to == None)

    cases = query.options(joinedload(Case.alert)).order_by(desc(Case.created_at))
    if limit is not None:
        cases = cases.limit(limit)
    cases = cases.all()

    return [
        CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            status=case.status.value if hasattr(case.status, 'value') else str(case.status),
            priority=case.priority,
            assigned_to=case.assigned_to,
            created_at=case.created_at,
            target_completion_date=case.target_completion_date,
            alert=AlertResponse(
                id=case.alert.id,
                alert_type=case.alert.alert_type,
                risk_score=case.alert.risk_score,
                status=case.alert.status.value if hasattr(case.alert.status, 'value') else str(case.alert.status),
                created_at=case.alert.created_at,
                transaction_id=case.alert.transaction_id,
                customer_id=case.alert.transaction.customer_id if case.alert.transaction else "",
                description=case.alert.description,
                transaction_amount=case.alert.transaction.amount if case.alert.transaction else None,
                transaction_currency=case.alert.transaction.currency if case.alert.transaction else None,
            ) if case.alert else None
        )
        for case in cases
    ]

@app.get("/api/cases/{case_id}")
async def get_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    case = db.query(Case).options(joinedload(Case.alert).joinedload(Alert.transaction)).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@app.put("/api/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    alert_update: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if alert_update.status:
        alert.status = AlertStatus[alert_update.status] # Convert string to Enum
    if alert_update.assigned_to:
        alert.assigned_to = alert_update.assigned_to
    if alert_update.priority:
        alert.priority = alert_update.priority
    if alert_update.resolution_notes:
        alert.resolution_notes = alert_update.resolution_notes
    
    db.commit()
    db.refresh(alert)
    return {"message": "Alert updated successfully"}

@app.get("/api/cases/", response_model=List[CaseResponse])
async def get_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie) # Or get_current_staff_user
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    """Get cases with optional filtering"""
    query = db.query(Case)

    if status:
        query = query.filter(Case.status == status)
    if priority:
        query = query.filter(Case.priority == priority)
    if assigned_to:
        if assigned_to == "me":
            query = query.filter(Case.assigned_to == current_user.username)
        elif assigned_to == "unassigned":
            query = query.filter(Case.assigned_to == None)

    cases = query.options(joinedload(Case.alert)).order_by(desc(Case.created_at))
    if limit is not None:
        cases = cases.limit(limit)
    cases = cases.all()

    return [
        CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            status=case.status.value if hasattr(case.status, 'value') else str(case.status),
            priority=case.priority,
            assigned_to=case.assigned_to,
            created_at=case.created_at,
            target_completion_date=case.target_completion_date,
            alert=AlertResponse(
                id=case.alert.id,
                alert_type=case.alert.alert_type,
                risk_score=case.alert.risk_score,
                status=case.alert.status.value if hasattr(case.alert.status, 'value') else str(case.alert.status),
                created_at=case.alert.created_at,
                transaction_id=case.alert.transaction_id,
                customer_id=case.alert.transaction.customer_id if case.alert.transaction else "",
                description=case.alert.description,
                transaction_amount=case.alert.transaction.amount if case.alert.transaction else None,
                transaction_currency=case.alert.transaction.currency if case.alert.transaction else None,
            ) if case.alert else None
        )
        for case in cases
    ]

@app.get("/api/cases/{case_id}")
async def get_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    case = db.query(Case).options(joinedload(Case.alert).joinedload(Alert.transaction)).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@app.put("/api/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    alert_update: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if alert_update.status:
        alert.status = AlertStatus[alert_update.status] # Convert string to Enum
    if alert_update.assigned_to:
        alert.assigned_to = alert_update.assigned_to
    if alert_update.priority:
        alert.priority = alert_update.priority
    if alert_update.resolution_notes:
        alert.resolution_notes = alert_update.resolution_notes
    
    db.commit()
    db.refresh(alert)
    return {"message": "Alert updated successfully"}

@app.put("/api/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    alert_update: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert_update.status:
        alert.status = alert_update.status
    if alert_update.assigned_to:
        alert.assigned_to = alert_update.assigned_to
    if alert_update.priority:
        alert.priority = alert_update.priority
    if alert_update.resolution_notes:
        alert.resolution_notes = alert_update.resolution_notes

    db.add(alert)
    db.commit()
    db.refresh(alert)
    return {"message": "Alert updated successfully", "alert_id": alert.id}

@app.get("/api/alerts/metrics")
async def get_alerts_metrics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    open_alerts = db.query(Alert).filter(Alert.status == "OPEN").count()
    closed_alerts = db.query(Alert).filter(Alert.status == "CLOSED").count()
    total_alerts = open_alerts + closed_alerts
    sanctions_hits = db.query(Alert).filter(Alert.alert_type == "SANCTIONS_HIT").count()
    avg_response_time_minutes = db.query(func.avg(Alert.response_time_minutes)).filter(Alert.status == "CLOSED").scalar() or 0.0
    false_positive_alerts = db.query(Alert).filter(Alert.status == "FALSE_POSITIVE").count()
    false_positive_rate = (false_positive_alerts / closed_alerts * 100) if closed_alerts > 0 else 0.0

    return {
        "open_alerts": open_alerts,
        "closed_alerts": closed_alerts,
        "total_alerts": total_alerts,
        "average_risk_score": db.query(func.avg(Alert.risk_score)).scalar() or 0.0,
        "sanctions_hits": sanctions_hits,
        "avg_response_time": avg_response_time_minutes / 60, # Convert to hours
        "false_positive_rate": false_positive_rate
    }

@app.get("/api/alerts/export")
async def export_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    output = "alert_id,alert_type,risk_score,status,created_at,transaction_id,customer_id,description\n"
    
    try:
        alerts = db.query(Alert).options(joinedload(Alert.transaction)).all() # Eager load transaction
        for alert in alerts:
            customer_id = alert.transaction.customer_id if alert.transaction else ""
            transaction_id = alert.transaction_id if alert.transaction_id else ""
            
            # Sanitize description to prevent CSV breaking
            description = alert.description.replace(",", ";").replace("\n", " ").replace("\r", "")
            
            output += f'{alert.id},{alert.alert_type},{alert.risk_score},{alert.status},{alert.created_at},{transaction_id},{customer_id},{description}\n'
        
        return Response(content=output, media_type="text/csv")
    except Exception as e:
        # Re-raise as HTTPException to send a proper error response to the frontend
        raise HTTPException(status_code=500, detail=f"Failed to export alerts due to an internal server error: {e}")


@app.post("/api/alerts/bulk")
async def bulk_alert_action(
    action_data: BulkAlertAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    updated_count = 0
    for alert_id in action_data.alert_ids:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            logger.warning(f"Alert {alert_id} not found for bulk action.")
            continue

        if action_data.action == "assign" and action_data.assigned_to:
            alert.assigned_to = action_data.assigned_to
            updated_count += 1
        elif action_data.action == "update_status" and action_data.status:
            alert.status = action_data.status
            updated_count += 1
        elif action_data.action == "update_priority" and action_data.priority:
            alert.priority = action_data.priority
            updated_count += 1
        elif action_data.action == "mark_false_positive":
            alert.status = "FALSE_POSITIVE"
            updated_count += 1
        elif action_data.action == "create_cases":
            # This would typically involve creating a case for each selected alert
            # For simplicity, we'll just log for now
            logger.info(f"Creating case for alert {alert_id} (bulk action)")
            # Example: await case_service.create_case_from_alert(alert_id, db)
            updated_count += 1
        
        if action_data.notes:
            alert.resolution_notes = action_data.notes # Assuming notes apply to all actions

        db.add(alert)
    db.commit()
    return {"message": f"Bulk action completed for {updated_count} alerts.", "updated_count": updated_count}

@app.post("/api/alerts/{alert_id}/assign")
async def assign_alert(
    alert_id: str,
    assign_data: AssignAlert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.assigned_to = assign_data.user_id
    db.add(alert)
    db.commit()
    return {"message": f"Alert {alert_id} assigned to {assign_data.user_id}"}

@app.get("/api/dashboard/aml-control-summary")
async def get_aml_control_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    """Get AML control summary"""
    aml_summary = db.query(
        Alert.alert_type,
        func.avg(Alert.risk_score).label('avg_risk'),
        func.count(Alert.id).label('count')
    ).group_by(Alert.alert_type).all()

    return [
        {
            "control_type": item.alert_type,
            "average_risk_score": float(item.avg_risk or 0),
            "triggered_count": item.count
        }
        for item in aml_summary
    ]



@app.get("/api/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    """Get dashboard statistics"""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    # Transaction stats
    total_transactions = db.query(Transaction).count()
    today_transactions = db.query(Transaction).filter(func.date(Transaction.created_at) == today).count()
    yesterday_transactions = db.query(Transaction).filter(func.date(Transaction.created_at) == yesterday).count()
    transactions_change = ((today_transactions - yesterday_transactions) / yesterday_transactions * 100) if yesterday_transactions > 0 else 0

    # Alert stats
    open_alerts = db.query(Alert).filter(Alert.status == "OPEN").count()
    high_risk_alerts = db.query(Alert).filter(
        and_(Alert.status == "OPEN", Alert.risk_score >= 0.8)
    ).count()
    today_alerts = db.query(Alert).filter(func.date(Alert.created_at) == today).count()
    yesterday_alerts = db.query(Alert).filter(func.date(Alert.created_at) == yesterday).count()
    alerts_change = ((today_alerts - yesterday_alerts) / yesterday_alerts * 100) if yesterday_alerts > 0 else 0

    # Case stats
    cases_opened_today = db.query(Case).filter(func.date(Case.created_at) == today).count()
    cases_opened_yesterday = db.query(Case).filter(func.date(Case.created_at) == yesterday).count()
    cases_change = ((cases_opened_today - cases_opened_yesterday) / cases_opened_yesterday * 100) if cases_opened_yesterday > 0 else 0

    # Risk distribution
    risk_distribution = db.query(
        Alert.alert_type,
        func.avg(Alert.risk_score).label('avg_risk'),
        func.count(Alert.id).label('count')
    ).group_by(Alert.alert_type).all()
    
    # Alert Trends
    alert_trends = db.query(func.date(Alert.created_at), func.sum(case((Alert.risk_score >= 0.8, 1), else_=0)), func.sum(case((Alert.risk_score >= 0.6, 1), else_=0))).group_by(func.date(Alert.created_at)).order_by(func.date(Alert.created_at)).all()

    response_data = {
        "total_transactions": total_transactions,
        "today_transactions": today_transactions,
        "transactions_change": round(transactions_change, 2),
        "open_alerts": open_alerts,
        "high_risk_alerts": high_risk_alerts,
        "alerts_change": round(alerts_change, 2),
        "cases_opened_today": cases_opened_today,
        "cases_change": round(cases_change, 2),
        "risk_distribution": [
            {
                "type": item.alert_type,
                "avg_risk": float(item.avg_risk or 0),
                "count": item.count
            }
            for item in risk_distribution
        ],
        "alert_trends": {
            "labels": [str(row[0]) for row in alert_trends],
            "high_risk": [row[1] for row in alert_trends],
            "medium_risk": [row[2] for row in alert_trends]
        }
    }
    logger.info(f"Dashboard stats: {response_data}")
    return response_data



@app.get("/api/cases/metrics")
async def get_cases_metrics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    """Get case management metrics"""
    metrics = await case_service.get_case_metrics(db)
    return metrics

@app.get("/api/cases/", response_model=List[CaseResponse])
async def get_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    """Get cases with optional filtering"""
    query = db.query(Case).options(joinedload(Case.alert).joinedload(Alert.transaction))
    
    if status:
        query = query.filter(Case.status == status)
    if priority:
        query = query.filter(Case.priority == priority)
    if assigned_to:
        if assigned_to == "me":
            query = query.filter(Case.assigned_to == current_user.username)
        elif assigned_to == "unassigned":
            query = query.filter(Case.assigned_to == None)
    
    cases = query.order_by(desc(Case.created_at)).limit(limit).all()
    
    return cases

@app.put("/api/cases/{case_id}")
async def update_case(
    case_id: str,
    update: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Update case status and notes"""
    case = await case_service.update_case(case_id, update.dict(), current_user.username, db)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {"message": "Case updated"}

@app.post("/api/cases/")
async def create_case(
    case_data: CreateCaseRequest, # Use the Pydantic model
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    logger.info(f"Creating case with data: {case_data.dict()}") # Log the Pydantic model dict
    try:
        new_case = await case_service.create_case(
            db=db,
            alert_id=case_data.alert_id,
            title=case_data.title,
            description=case_data.description,
            priority=case_data.priority,
            assigned_to=case_data.assigned_to,
            investigation_notes=case_data.investigation_notes,
            target_completion_date=case_data.target_completion_date # Pass datetime object
        )
        return {"message": "Case created successfully", "case_id": new_case.id}
    except HTTPException as e:
        logger.error(f"Error creating case: {e.status_code}: {e.detail}")
        return JSONResponse(status_code=e.status_code, content={"message": e.detail})
    except ValueError as ve:
        logger.error(f"Validation error creating case: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating case: {e}", exc_info=True) # Log traceback
        raise HTTPException(status_code=500, detail="Internal Server Error during case creation")

@app.get("/api/cases/{case_id}")
async def get_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    case = db.query(Case).options(joinedload(Case.alert).joinedload(Alert.transaction), joinedload(Case.activities)).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@app.get("/api/cases/export")
async def export_cases(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    cases = db.query(Case).all()
    output = "case_number,title,status,priority,assigned_to,created_at\n"
    for case in cases:
        output += f"{case.case_number},{case.title},{case.status},{case.priority},{case.assigned_to},{case.created_at}\n"
    return Response(content=output, media_type="text/csv")

@app.get("/api/cases/distribution")
async def get_case_distribution(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_from_cookie)):
    logger.info("Getting case distribution")
    if isinstance(current_user, RedirectResponse):
        return current_user
    case_distribution = db.query(
        Case.status,
        func.count(Case.id).label('count')
    ).group_by(Case.status).all()

    return {
        "labels": [item.status.value for item in case_distribution],
        "data": [item.count for item in case_distribution]
    }




@app.get("/api/reports/suspicious-activity")
async def generate_sar_report(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Generate Suspicious Activity Report"""
    
    # Get high-risk alerts in date range
    alerts = db.query(Alert).filter(
        and_(
            Alert.created_at >= start_date,
            Alert.created_at <= end_date,
            Alert.risk_score >= 0.7
        )
    ).all()
    
    report_data = []
    for alert in alerts:
        transaction = alert.transaction
        customer = db.query(Customer).filter(
            Customer.customer_id == transaction.customer_id
        ).first()
        
        report_data.append({
            "alert_id": alert.id,
            "transaction_id": transaction.id,
            "customer_name": customer.full_name if customer else "Unknown",
            "account_number": transaction.account_number,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "risk_score": alert.risk_score,
            "alert_type": alert.alert_type,
            "description": alert.description,
            "created_at": alert.created_at.isoformat()
        })
    
    return {
        "report_period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "total_alerts": len(report_data),
        "alerts": report_data
    }

def apply_report_filters(query, filters: ReportFilters, db: Session):
    start_date_filter = None
    end_date_filter = None

    if filters.report_period:
        current_time = datetime.now()
        if filters.report_period == "today":
            start_date_filter = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date_filter = current_time
        elif filters.report_period == "7d":
            start_date_filter = current_time - timedelta(days=7)
            end_date_filter = current_time
        elif filters.report_period == "30d":
            start_date_filter = current_time - timedelta(days=30)
            end_date_filter = current_time
        elif filters.report_period == "90d":
            start_date_filter = current_time - timedelta(days=90)
            end_date_filter = current_time
        elif filters.report_period == "year":
            start_date_filter = current_time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date_filter = current_time
    elif filters.start_date and filters.end_date:
        try:
            start_date_filter = datetime.fromisoformat(filters.start_date)
            end_date_filter = datetime.fromisoformat(filters.end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for start_date or end_date. Use ISO format (YYYY-MM-DD).")

    if start_date_filter and end_date_filter:
        query = query.filter(and_(Transaction.created_at >= start_date_filter, Transaction.created_at <= end_date_filter))

    if filters.risk_level:
        if filters.risk_level == "low":
            query = query.filter(Alert.risk_score < 0.4)
        elif filters.risk_level == "medium":
            query = query.filter(and_(Alert.risk_score >= 0.4, Alert.risk_score < 0.7))
        elif filters.risk_level == "high":
            query = query.filter(and_(Alert.risk_score >= 0.7, Alert.risk_score < 0.9))
        elif filters.risk_level == "critical":
            query = query.filter(Alert.risk_score >= 0.9)
            
    if filters.currency:
        query = query.filter(Transaction.currency == filters.currency)

    return query

@app.get("/api/reports/executive-summary")
async def get_executive_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
    filters: ReportFilters = Depends(get_report_filters),
):
    transaction_query = db.query(Transaction)
    alert_query = db.query(Alert)
    case_query = db.query(Case)

    if filters:
        transaction_query = apply_report_filters(transaction_query, filters, db)
        alert_query = apply_report_filters(alert_query.join(Transaction), filters, db)
        case_query = apply_report_filters(case_query.join(Alert).join(Transaction), filters, db)

    total_transactions = transaction_query.count()
    total_volume = transaction_query.with_entities(func.sum(Transaction.base_amount)).scalar()
    alerts_generated = alert_query.count()
    cases_opened = case_query.count()
    sars_filed = case_query.filter(Case.sar_filed == True).count()
    
    return {
        "total_transactions": total_transactions,
        "total_volume": total_volume,
        "alerts_generated": alerts_generated,
        "cases_opened": cases_opened,
        "sars_filed": sars_filed,
        "compliance_score": 95, # Placeholder
        "transactions_change": 5, # Placeholder
        "volume_change": 10, # Placeholder
        "alerts_change": -2, # Placeholder
        "cases_change": 1, # Placeholder
        "sars_change": 0, # Placeholder
        "compliance_change": 1 # Placeholder
    }

@app.get("/api/reports/charts-data")
async def get_charts_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
    filters: ReportFilters = Depends(get_report_filters),
):
    transaction_query = db.query(Transaction)
    alert_query = db.query(Alert)
    customer_query = db.query(Customer)

    if filters:
        transaction_query = apply_report_filters(transaction_query, filters, db)
        alert_query = apply_report_filters(alert_query.join(Transaction), filters, db)
        # customer_query is not filtered by date, risk, or currency

    # Volume Trends
    volume_trends_query = apply_report_filters(db.query(func.date(Transaction.created_at), func.sum(Transaction.base_amount), func.sum(case((Transaction.risk_score >= 0.7, Transaction.base_amount), else_=0)) ), filters, db)
    volume_trends = volume_trends_query.group_by(func.date(Transaction.created_at)).order_by(func.date(Transaction.created_at)).all()
    
    # Alert Distribution
    alert_distribution_query = db.query(Alert.alert_type, func.count(Alert.id)).join(Transaction, Alert.transaction_id == Transaction.id)
    alert_distribution_query = apply_report_filters(alert_distribution_query, filters, db)
    alert_distribution = alert_distribution_query.group_by(Alert.alert_type).all()
    
    # Risk Trends
    risk_trends_query = db.query(func.date(Alert.created_at), func.sum(case((Alert.risk_score >= 0.9, 1), else_=0)), func.sum(case((Alert.risk_score >= 0.7, 1), else_=0)), func.sum(case((Alert.risk_score >= 0.4, 1), else_=0))).join(Transaction, Alert.transaction_id == Transaction.id)
    risk_trends_query = apply_report_filters(risk_trends_query, filters, db)
    risk_trends = risk_trends_query.group_by(func.date(Alert.created_at)).order_by(func.date(Alert.created_at)).all()
    
    # Channel Analysis
    channel_analysis_query = apply_report_filters(db.query(Transaction.channel, func.count(Transaction.id)), filters, db)
    channel_analysis = channel_analysis_query.group_by(Transaction.channel).all()
    
    # Customer Risk
    customer_risk = customer_query.group_by(Customer.risk_rating).with_entities(Customer.risk_rating, func.count(Customer.id)).all()
    
    customer_risk_data = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for rating, count in customer_risk:
        if rating:
            customer_risk_data[rating.value] = count

    return {
        "volume_trends": {
            "labels": [str(row[0]) for row in volume_trends],
            "total_volume": [row[1] for row in volume_trends],
            "high_risk_volume": [row[2] for row in volume_trends]
        },
        "alert_distribution": {
            "labels": [row[0] for row in alert_distribution],
            "data": [row[1] for row in alert_distribution]
        },
        "risk_trends": {
            "labels": [str(row[0]) for row in risk_trends],
            "critical": [row[1] for row in risk_trends],
            "high": [row[2] for row in risk_trends],
            "medium": [row[3] for row in risk_trends]
        },
        "channel_analysis": {
            "labels": [row[0] for row in channel_analysis],
            "data": [row[1] for row in channel_analysis]
        },
        "customer_risk": {
            "labels": ["Low Risk", "Medium Risk", "High Risk", "Critical Risk"],
            "data": [customer_risk_data["LOW"], customer_risk_data["MEDIUM"], customer_risk_data["HIGH"], customer_risk_data["CRITICAL"]]
        }
    }

@app.get("/api/reports/{tab_name}")
async def get_report_tab_data(
    tab_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
    filters: ReportFilters = Depends(get_report_filters),
):
    if tab_name == "alerts_report":
        alert_summary_query = apply_report_filters(db.query(Alert.alert_type, func.count(Alert.id), func.avg(Alert.risk_score), func.avg(case((Alert.status == 'CLOSED', 1), else_=0))), filters, db)
        alert_summary = alert_summary_query.group_by(Alert.alert_type).all()
        
        top_risk_customers_query = apply_report_filters(db.query(Transaction.customer_id, func.count(Alert.id), func.max(Alert.risk_score), Customer.status).join(Alert.transaction).join(Customer), filters, db)
        top_risk_customers = top_risk_customers_query.group_by(Transaction.customer_id, Customer.status).order_by(func.max(Alert.risk_score).desc()).limit(10).all()
        
        return {
            "alert_summary": [
                {"alert_type": row[0], "count": row[1], "avg_risk_score": row[2], "resolution_rate": row[3] * 100 if row[3] else 0} for row in alert_summary
            ],
            "top_risk_customers": [
                {"customer_id": row[0], "alert_count": row[1], "max_risk_score": row[2], "status": row[3]} for row in top_risk_customers
            ]
        }
    elif tab_name == "transactions_report":
        high_value_transactions_query = apply_report_filters(db.query(Transaction).filter(Transaction.is_high_value == True), filters, db)
        high_value_transactions = high_value_transactions_query.order_by(desc(Transaction.created_at)).limit(100).all()
        return {"high_value_transactions": high_value_transactions}
    elif tab_name == "customers_report":
        pep_customers_query = apply_report_filters(db.query(Customer).filter(Customer.is_pep == True), filters, db)
        pep_customers = pep_customers_query.order_by(desc(Customer.last_review_date)).limit(100).all()
        return {"pep_customers": pep_customers}
    elif tab_name == "compliance_report":
        alert_query = apply_report_filters(db.query(Alert), filters, db)
        case_query = apply_report_filters(db.query(Case), filters, db)

        total_alerts = alert_query.count()
        closed_alerts = alert_query.filter(Alert.status == "CLOSED").count()
        total_cases = case_query.count()
        closed_cases = case_query.filter(Case.status == "CLOSED").count()
        sars_filed = case_query.filter(Case.sar_filed == True).count()

        alert_response_sla = (closed_alerts / total_alerts * 100) if total_alerts > 0 else 100
        case_resolution_sla = (closed_cases / total_cases * 100) if total_cases > 0 else 100
        sar_filing_sla = 90 # Placeholder
        total_sars = sars_filed
        total_ctrs = 0 # Placeholder
        sanctions_coverage = 100 # Placeholder
        false_positive_rate = alert_query.filter(Alert.status == "FALSE_POSITIVE").count() / closed_alerts * 100 if closed_alerts > 0 else 0.0
        investigation_rate = (alert_query.filter(Alert.status == "INVESTIGATING").count() + closed_alerts) / total_alerts * 100 if total_alerts > 0 else 0.0
        system_uptime = 99.9 # Placeholder

        return {
            "compliance_metrics": {
                "alert_response_sla": alert_response_sla,
                "case_resolution_sla": case_resolution_sla,
                "sar_filing_sla": sar_filing_sla,
                "total_sars": total_sars,
                "total_ctrs": total_ctrs,
                "sanctions_coverage": sanctions_coverage,
                "false_positive_rate": false_positive_rate,
                "investigation_rate": investigation_rate,
                "system_uptime": system_uptime
            }
        }
    return {}

@app.get("/api/test")
async def test_endpoint():
    return {"message": "test"}

@app.post("/api/reports/generate")
async def generate_report(report: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    start_date = datetime.fromisoformat(report.get("start_date"))
    end_date = datetime.fromisoformat(report.get("end_date"))
    
    if report.get("report_type") == "SAR":
        alerts = db.query(Alert).filter(
            and_(
                Alert.created_at >= start_date,
                Alert.created_at <= end_date,
                Alert.risk_score >= 0.7
            )
        ).all()
        
        output = "alert_id,transaction_id,customer_name,account_number,amount,currency,risk_score,alert_type,description,created_at\n"
        for alert in alerts:
            transaction = alert.transaction
            customer = db.query(Customer).filter(
                Customer.customer_id == transaction.customer_id
            ).first()
            output += f'{alert.id},{transaction.id},{customer.full_name if customer else "Unknown"},{transaction.account_number},{transaction.amount},{transaction.currency},{alert.risk_score},{alert.alert_type},{alert.description},{alert.created_at}\n'
        return Response(content=output, media_type="text/csv")
    
    return {"message": "Report generated successfully"}


@app.get("/api/customers/{customer_id}/profile")
async def get_customer_profile(customer_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    """Get customer transaction profile and risk assessment"""
    
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get recent transactions
    transactions = db.query(Transaction).filter(
        Transaction.customer_id == customer_id
    ).order_by(desc(Transaction.created_at)).limit(50).all()
    
    # Calculate profile metrics
    total_volume = sum(t.base_amount for t in transactions)
    avg_transaction = total_volume / len(transactions) if transactions else 0
    
    # Get alerts for this customer
    customer_alerts = db.query(Alert).join(Transaction).filter(
        Transaction.customer_id == customer_id
    ).order_by(desc(Alert.created_at)).limit(10).all()
    
    return {
        "customer_id": customer.customer_id,
        "full_name": customer.full_name,
        "risk_rating": customer.risk_rating.value if hasattr(customer.risk_rating, 'value') else str(customer.risk_rating),
        "email": customer.email,
        "account_opening_date": customer.account_opening_date.isoformat(),
        "last_activity": customer.last_login.isoformat() if customer.last_login else None,
        "is_pep": customer.is_pep,
        "last_review_date": customer.last_review_date.isoformat() if customer.last_review_date else None,
        "transaction_count": len(transactions),
        "total_volume": total_volume,
        "average_transaction": avg_transaction,
        "recent_alerts": len(customer_alerts),
        "transactions": [
            {
                "id": str(t.id),
                "amount": t.amount,
                "currency": t.currency,
                "transaction_type": t.transaction_type,
                "channel": t.channel,
                "created_at": t.created_at.isoformat(),
                "status": t.status.value if hasattr(t.status, 'value') else str(t.status)
            }
            for t in transactions  # All transactions for display
        ]
    }

# --- Customer Portal API Endpoints ---

import random

class CustomerCreate(BaseModel):
    username: str
    password: str
    full_name: str
    email: str

@app.post("/api/customer/register")
async def register_customer(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    db_customer = db.query(Customer).filter(Customer.username == username).first()
    if db_customer:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    customer_id = str(uuid.uuid4())
    hashed_password = get_password_hash(password)
    db_customer = Customer(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        username=username,
        hashed_password=hashed_password,
        full_name=full_name,
        email=email,
        account_opening_date=datetime.now(),
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)

    # Create a default account for the new customer
    account = Account(
        id=str(uuid.uuid4()),
        account_number=f"ACC{random.randint(100000000, 999999999)}",
        customer_id=customer_id,
        account_type="SAVINGS",
        currency="USD",
        balance=1000.0,  # Starting balance
        status="ACTIVE",
        opening_date=datetime.now(),
    )
    db.add(account)
    db.commit()

    return RedirectResponse(url="/portal/login", status_code=302)

@app.post("/api/customer/token")
async def login_for_access_token_customer(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.username == form_data.username).first()
    if not customer or not verify_password(form_data.password, customer.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last_login timestamp
    try:
        customer.last_login = datetime.utcnow()
        db.add(customer)
        db.commit()
        db.refresh(customer)
        logger.info(f"Customer {customer.username} last_login updated to {customer.last_login}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating last_login for customer {customer.username}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during login")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": customer.username}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/portal/dashboard", status_code=302)
    response.set_cookie(
        key="customer_token",
        value=access_token,
        httponly=True,
        max_age=access_token_expires.total_seconds(),
        expires=access_token_expires.total_seconds(),
        samesite="Lax", # or "Strict"
        secure=False, # Set to True in production with HTTPS
        path="/" # Ensure cookie is available across the entire domain
    )
    logger.info(f"Customer token cookie set for user: {customer.username}")
    return response

@app.post("/api/customer/logout")
async def customer_logout(response: Response):
    response.delete_cookie(key="customer_token")
    logger.info("Customer token cookie deleted.")
    return {"message": "Logged out successfully"}




@app.get("/api/customer/me")
async def read_customer_me(current_customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    # Load the customer with their associated accounts
    customer_with_accounts = db.query(Customer).options(joinedload(Customer.accounts)).filter(Customer.id == current_customer.id).first()
    if not customer_with_accounts:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer_with_accounts

@app.get("/api/customer/me/transactions")
async def read_customer_transactions(current_customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    transactions = db.query(Transaction).filter(Transaction.customer_id == current_customer.customer_id, Transaction.status.in_([TransactionStatus.COMPLETED, TransactionStatus.FLAGGED])).order_by(desc(Transaction.created_at)).limit(50).all()
    return transactions

@app.post("/api/customer/me/transactions")
async def create_customer_transaction(
    transaction: TransactionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer)
):
    # Ensure the transaction is for the logged-in customer
    if transaction.customer_id != current_customer.customer_id:
        raise HTTPException(status_code=403, detail="Cannot create transactions for other customers")

    # Reuse the existing create_transaction logic, but with the customer's identity
    fake_current_user = {"user_id": f"customer:{current_customer.username}", "role": "customer"}

    # Convert currency if needed
    base_amount = await currency_service.convert_to_base(
        transaction.amount, transaction.currency
    )

    # Create transaction record
    db_transaction = Transaction(
        customer_id=transaction.customer_id,
        account_number=transaction.account_number,
        transaction_type=transaction.transaction_type,
        amount=transaction.amount,
        base_amount=base_amount,
        currency=transaction.currency,
        channel=transaction.channel,
        counterparty_account=transaction.counterparty_account,
        counterparty_name=transaction.counterparty_name,
        counterparty_bank=transaction.counterparty_bank,
        reference=transaction.reference,
        narrative=transaction.narrative,
        processed_by=fake_current_user["user_id"],
        status=TransactionStatus.PENDING
    )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    # Background processing for AML controls
    background_tasks.add_task(
        process_transaction_controls,
        db_transaction.id,
        transaction.dict()
    )

    return {"message": "Transaction processed", "transaction_id": db_transaction.id}


class PaymentRequest(BaseModel):
    source_account_number: str
    amount: float
    currency: str
    reference: str
    payee_account: Optional[str] = None
    payee_name: Optional[str] = None
    payee_bank: Optional[str] = None

class TransferRequest(BaseModel):
    source_account_number: str
    destination_account_number: str
    amount: float
    currency: str
    reference: str

@app.post("/api/customer/make_payment")
async def make_customer_payment(
    payment_request: PaymentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer)
):
    if current_customer is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Validate source account belongs to the customer
    source_account = db.query(Account).filter(
        Account.account_number == payment_request.source_account_number,
        Account.customer_id == current_customer.customer_id
    ).first()

    if not source_account:
        raise HTTPException(status_code=400, detail="Invalid source account or account does not belong to you")

    if source_account.balance < payment_request.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # Deduct amount from source account (simplified for now)
    source_account.balance -= payment_request.amount
    db.add(source_account)
    db.commit()
    db.refresh(source_account)

    # Create a TransactionCreate object for the existing transaction processing logic
    transaction_data = TransactionCreate(
        customer_id=current_customer.customer_id,
        account_number=payment_request.source_account_number,
        transaction_type="DEBIT", # Assuming payments are debits
        amount=payment_request.amount,
        currency=payment_request.currency,
        channel="ONLINE_PAYMENT", # Specific channel for payments
        counterparty_account=payment_request.payee_account,
        counterparty_name=payment_request.payee_name,
        counterparty_bank=payment_request.payee_bank,
        reference=payment_request.reference,
        narrative=f"Payment to {payment_request.payee_name or payment_request.payee_account}"
    )

    # Reuse the existing transaction processing logic
    db_transaction = Transaction(
        customer_id=transaction_data.customer_id,
        account_number=transaction_data.account_number,
        transaction_type=transaction_data.transaction_type,
        amount=transaction_data.amount,
        base_amount=await currency_service.convert_to_base(transaction_data.amount, transaction_data.currency),
        currency=transaction_data.currency,
        channel=transaction_data.channel,
        counterparty_account=transaction_data.counterparty_account,
        counterparty_name=transaction_data.counterparty_name,
        counterparty_bank=transaction_data.counterparty_bank,
        reference=transaction_data.reference,
        narrative=transaction_data.narrative,
        processed_by=f"customer:{current_customer.username}",
        status=TransactionStatus.PENDING
    )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    background_tasks.add_task(
        process_transaction_controls,
        db_transaction.id,
        transaction_data.dict()
    )

    return {"message": "Payment processed successfully", "transaction_id": db_transaction.id}

@app.post("/api/customer/make_transfer")
async def make_customer_transfer(
    transfer_request: TransferRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer)
):
    if current_customer is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Validate source account belongs to the customer
    source_account = db.query(Account).filter(
        Account.account_number == transfer_request.source_account_number,
        Account.customer_id == current_customer.customer_id
    ).first()

    if not source_account:
        raise HTTPException(status_code=400, detail="Invalid source account or account does not belong to you")

    # Validate destination account belongs to the customer
    destination_account = db.query(Account).filter(
        Account.account_number == transfer_request.destination_account_number,
        Account.customer_id == current_customer.customer_id
    ).first()

    if not destination_account:
        raise HTTPException(status_code=400, detail="Invalid destination account or account does not belong to you")

    if source_account.balance < transfer_request.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # Perform the transfer
    source_account.balance -= transfer_request.amount
    destination_account.balance += transfer_request.amount
    db.add(source_account)
    db.add(destination_account)
    db.commit()
    db.refresh(source_account)
    db.refresh(destination_account)

    # Create a debit transaction
    debit_transaction_data = TransactionCreate(
        customer_id=current_customer.customer_id,
        account_number=transfer_request.source_account_number,
        transaction_type="DEBIT",
        amount=transfer_request.amount,
        currency=transfer_request.currency,
        channel="INTERNAL_TRANSFER",
        counterparty_account=transfer_request.destination_account_number,
        counterparty_name=current_customer.full_name,
        counterparty_bank="SAME",
        reference=transfer_request.reference,
        narrative=f"Transfer to {transfer_request.destination_account_number}"
    )

    db_debit_transaction = Transaction(
        customer_id=debit_transaction_data.customer_id,
        account_number=debit_transaction_data.account_number,
        transaction_type=debit_transaction_data.transaction_type,
        amount=debit_transaction_data.amount,
        base_amount=await currency_service.convert_to_base(debit_transaction_data.amount, debit_transaction_data.currency),
        currency=debit_transaction_data.currency,
        channel=debit_transaction_data.channel,
        counterparty_account=debit_transaction_data.counterparty_account,
        counterparty_name=debit_transaction_data.counterparty_name,
        counterparty_bank=debit_transaction_data.counterparty_bank,
        reference=debit_transaction_data.reference,
        narrative=debit_transaction_data.narrative,
        processed_by=f"customer:{current_customer.username}",
        status=TransactionStatus.PENDING
    )
    db.add(db_debit_transaction)
    db.commit()
    db.refresh(db_debit_transaction)

    background_tasks.add_task(
        process_transaction_controls,
        db_debit_transaction.id,
        debit_transaction_data.dict()
    )

    # Create a credit transaction
    credit_transaction_data = TransactionCreate(
        customer_id=current_customer.customer_id,
        account_number=transfer_request.destination_account_number,
        transaction_type="CREDIT",
        amount=transfer_request.amount,
        currency=transfer_request.currency,
        channel="INTERNAL_TRANSFER",
        counterparty_account=transfer_request.source_account_number,
        counterparty_name=current_customer.full_name,
        counterparty_bank="SAME",
        reference=transfer_request.reference,
        narrative=f"Transfer from {transfer_request.source_account_number}"
    )

    db_credit_transaction = Transaction(
        customer_id=credit_transaction_data.customer_id,
        account_number=credit_transaction_data.account_number,
        transaction_type=credit_transaction_data.transaction_type,
        amount=credit_transaction_data.amount,
        base_amount=await currency_service.convert_to_base(credit_transaction_data.amount, credit_transaction_data.currency),
        currency=credit_transaction_data.currency,
        channel=credit_transaction_data.channel,
        counterparty_account=credit_transaction_data.counterparty_account,
        counterparty_name=credit_transaction_data.counterparty_name,
        counterparty_bank=credit_transaction_data.counterparty_bank,
        reference=credit_transaction_data.reference,
        narrative=credit_transaction_data.narrative,
        processed_by=f"customer:{current_customer.username}",
        status=TransactionStatus.COMPLETED # Credit is completed immediately
    )
    db.add(db_credit_transaction)
    db.commit()
    db.refresh(db_credit_transaction)

    background_tasks.add_task(
        process_transaction_controls,
        db_credit_transaction.id,
        credit_transaction_data.dict()
    )

    return {"message": "Transfer processed successfully", "transaction_id": db_debit_transaction.id}