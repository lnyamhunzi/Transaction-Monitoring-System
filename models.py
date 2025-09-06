"""
Database models for Banking AML Transaction Monitoring System
"""

from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer, Text, ForeignKey, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()

class RiskRating(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AlertStatus(enum.Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CLOSED = "CLOSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"

class CaseStatus(enum.Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    PENDING_REVIEW = "PENDING_REVIEW"
    CLOSED = "CLOSED"
    ESCALATED = "ESCALATED"

class TransactionStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FLAGGED = "FLAGGED"
    FAILED = "FAILED"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(512), nullable=False)
    role = Column(String(255), nullable=False)  # e.g., "admin", "compliance_officer"
    full_name = Column(String(255))
    email = Column(String(255), unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    date_of_birth = Column(DateTime)
    nationality = Column(String(255))
    id_number = Column(String(255))
    phone_number = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    address = Column(Text)
    occupation = Column(String(255))
    employer = Column(String(255))
    risk_rating = Column(Enum(RiskRating), default=RiskRating.LOW)
    is_pep = Column(Boolean, default=False)
    account_opening_date = Column(DateTime, nullable=False)
    kyc_completion_date = Column(DateTime)
    last_review_date = Column(DateTime)

    # New fields for customer portal
    username = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(512))
    last_login = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transactions = relationship("Transaction", back_populates="customer")
    accounts = relationship("Account", back_populates="customer")

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_number = Column(String(255), unique=True, nullable=False, index=True)
    customer_id = Column(String(255), ForeignKey("customers.customer_id"), nullable=False)
    account_type = Column(String(255), nullable=False)  # SAVINGS, CURRENT, LOAN, etc.
    currency = Column(String(3), default="USD")
    balance = Column(Float, default=0.0)
    status = Column(String(255), default="ACTIVE")  # ACTIVE, DORMANT, CLOSED, FROZEN
    opening_date = Column(DateTime, nullable=False)
    closing_date = Column(DateTime)
    monthly_turnover_limit = Column(Float)
    daily_transaction_limit = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    customer = relationship("Customer", back_populates="accounts")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(255), ForeignKey("customers.customer_id"), nullable=False, index=True)
    account_number = Column(String(255), nullable=False, index=True)
    transaction_type = Column(String(255), nullable=False)  # CREDIT, DEBIT, TRANSFER
    amount = Column(Float, nullable=False)
    base_amount = Column(Float, nullable=False)  # Amount in base currency (USD)
    currency = Column(String(3), default="USD")
    exchange_rate = Column(Float, default=1.0)
    channel = Column(String(255), nullable=False)  # RTGS, ZIPIT, INTERNAL, CARD, MOBILE
    
    # Counterparty information
    counterparty_account = Column(String(255))
    counterparty_name = Column(String(255))
    counterparty_bank = Column(String(255))
    counterparty_country = Column(String(255))
    
    # Transaction details
    reference = Column(String(255))
    narrative = Column(Text)
    processing_date = Column(DateTime, server_default=func.now())
    value_date = Column(DateTime)
    
    # Processing information
    processed_by = Column(String(255))  # Staff member who processed
    authorized_by = Column(String(255))  # Staff member who authorized
    batch_id = Column(String(255))
    
    # Risk and compliance flags
    risk_score = Column(Float, default=0.0)
    is_suspicious = Column(Boolean, default=False)
    is_cross_border = Column(Boolean, default=False)
    is_high_value = Column(Boolean, default=False)
    ml_prediction = Column(String(255))
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, index=True)
    processing_status = Column(String(255))
    
    # Audit trail
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    customer = relationship("Customer", back_populates="transactions")
    alerts = relationship("Alert", back_populates="transaction")

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False, index=True)
    alert_type = Column(String(255), nullable=False, index=True)
    risk_score = Column(Float, nullable=False)
    priority = Column(String(255), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(Enum(AlertStatus), default=AlertStatus.OPEN, index=True)
    
    # Alert details
    description = Column(Text, nullable=False)
    triggered_rule = Column(String(255))
    alert_metadata = Column(JSON)  # Additional alert-specific data
    
    # Assignment and workflow
    assigned_to = Column(String(255))  # Compliance officer assigned
    reviewed_by = Column(String(255))
    reviewed_at = Column(DateTime)
    resolution_notes = Column(Text)
    
    # Escalation
    escalated_to = Column(String(255))
    escalated_at = Column(DateTime)
    escalation_reason = Column(Text)
    
    # SLA tracking
    sla_deadline = Column(DateTime)
    response_time_minutes = Column(Integer)
    resolution_time_minutes = Column(Integer)
    
    # Audit trail
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transaction = relationship("Transaction", back_populates="alerts")
    case = relationship("Case", back_populates="alert", uselist=False)

class Case(Base):
    __tablename__ = "cases"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_id = Column(String(36), ForeignKey("alerts.id"), nullable=False, unique=True)
    case_number = Column(String(255), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum(CaseStatus), default=CaseStatus.OPEN, index=True)
    priority = Column(String(255), default="MEDIUM")
    
    # Assignment
    assigned_to = Column(String(255), nullable=False)
    supervisor = Column(String(255))
    
    # Investigation details
    investigation_notes = Column(Text)
    evidence_collected = Column(JSON)
    external_references = Column(JSON)  # Links to external systems
    
    # Decision and outcome
    decision = Column(String(255))  # SAR_FILED, NO_ACTION, ACCOUNT_CLOSURE, etc.
    decision_rationale = Column(Text)
    decided_by = Column(String(255))
    decided_at = Column(DateTime)
    
    # Regulatory reporting
    sar_filed = Column(Boolean, default=False)
    sar_reference = Column(String(255))
    sar_filed_date = Column(DateTime)
    
    # SLA and metrics
    target_completion_date = Column(DateTime)
    actual_completion_date = Column(DateTime)
    total_hours_spent = Column(Float, default=0.0)
    
    # Audit trail
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    alert = relationship("Alert", back_populates="case")
    activities = relationship("CaseActivity", back_populates="case")

class CaseActivity(Base):
    __tablename__ = "case_activities"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    activity_type = Column(String(255), nullable=False)  # NOTE, STATUS_CHANGE, ASSIGNMENT, etc.
    description = Column(Text, nullable=False)
    performed_by = Column(String(255), nullable=False)
    performed_at = Column(DateTime, server_default=func.now())
    activity_metadata = Column(JSON)
    
    # Relationships
    case = relationship("Case", back_populates="activities")

class SanctionsList(Base):
    __tablename__ = "sanctions_lists"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    list_name = Column(String(255), nullable=False)  # OFAC, UN, EU, etc.
    entity_name = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(255))  # INDIVIDUAL, ENTITY, VESSEL, etc.
    aliases = Column(JSON)  # Alternative names
    addresses = Column(JSON)
    date_of_birth = Column(String(255))
    place_of_birth = Column(String(255))
    nationality = Column(String(255))
    id_numbers = Column(JSON)
    
    # List metadata
    list_date = Column(DateTime)
    program = Column(String(255))
    remarks = Column(Text)
    
    # System metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class PEPList(Base):
    __tablename__ = "pep_lists"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String(255), nullable=False, index=True)
    position = Column(String(255))
    country = Column(String(255))
    category = Column(String(255))  # HEAD_OF_STATE, MINISTER, JUDGE, etc.
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Additional information
    aliases = Column(JSON)
    family_members = Column(JSON)
    close_associates = Column(JSON)
    
    # Source information
    source = Column(String(255))
    source_date = Column(DateTime)
    
    # System metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_currency = Column(String(3), nullable=False, index=True)
    to_currency = Column(String(3), nullable=False, index=True)
    rate = Column(Float, nullable=False)
    rate_date = Column(DateTime, nullable=False, index=True)
    source = Column(String(255))  # CBZ, XE, BLOOMBERG, etc.
    
    # System metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class SystemConfiguration(Base):
    __tablename__ = "system_configurations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_key = Column(String(255), unique=True, nullable=False)
    config_value = Column(String(255), nullable=False)
    config_type = Column(String(255), default="STRING")  # STRING, INTEGER, FLOAT, BOOLEAN, JSON
    description = Column(Text)
    category = Column(String(255))  # THRESHOLDS, ML_PARAMS, NOTIFICATIONS, etc.
    
    # Audit trail
    created_by = Column(String(255))
    updated_by = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), nullable=False, index=True)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(255), nullable=False)  # TRANSACTION, ALERT, CASE, etc.
    resource_id = Column(String(255), nullable=False)
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(String(255))
    user_agent = Column(String(255))
    timestamp = Column(DateTime, server_default=func.now(), index=True)

class MLModel(Base):
    __tablename__ = "ml_models"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_name = Column(String(255), unique=True, nullable=False)
    model_type = Column(String(255), nullable=False)  # ANOMALY_DETECTION, RISK_SCORING, etc.
    version = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    
    # Model performance metrics
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    auc_score = Column(Float)
    
    # Model metadata
    training_data_period = Column(String(255))
    features_used = Column(JSON)
    hyperparameters = Column(JSON)
    
    # Deployment information
    is_active = Column(Boolean, default=False)
    deployed_at = Column(DateTime)
    deployed_by = Column(String(255))
    
    # System metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())