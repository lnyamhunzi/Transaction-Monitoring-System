"""
Configuration settings for the AML Transaction Monitoring System
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

class Settings:
    """Application settings and configuration"""
    
    # Database Configuration
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD","Mugonat#99")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "aml_system")

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+mysqlconnector://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Application Settings
    APP_NAME: str = "Banking AML Transaction Monitoring System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    APP_SECRET_KEY: str = os.getenv("SECRET_KEY", "aml-system-secret-key-change-in-production")
    
    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5000"))
    
    # Security Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a-very-secret-key-that-should-be-in-env-file")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email Configuration
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "aml-system@bank.com")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "password")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "aml-system@bank.com")
    
    # Notification Recipients
    COMPLIANCE_EMAILS: str = os.getenv("COMPLIANCE_EMAILS", "compliance@bank.com")
    MANAGEMENT_EMAILS: str = os.getenv("MANAGEMENT_EMAILS", "management@bank.com")
    AML_OFFICERS: str = os.getenv("AML_OFFICERS", "aml-officer@bank.com")
    TECH_EMAILS: str = os.getenv("TECH_EMAILS", "tech@bank.com")
    
    # External API Configuration
    EXCHANGE_RATE_API_KEY: str = os.getenv("EXCHANGE_RATE_API_KEY", "demo_key")
    
    # AML Configuration
    DEFAULT_RISK_THRESHOLD: float = 0.7
    HIGH_VALUE_THRESHOLD_USD: float = 10000.0
    
    # Transaction Monitoring Thresholds
    THRESHOLDS: Dict[str, Dict[str, float]] = {
        "USD": {
            "low_risk": 1000.0,
            "medium_risk": 10000.0,
            "high_risk": 50000.0,
            "reporting_threshold": 10000.0
        },
        "ZWL": {
            "low_risk": 1000000.0,
            "medium_risk": 10000000.0,
            "high_risk": 50000000.0,
            "reporting_threshold": 10000000.0
        },
        "ZAR": {
            "low_risk": 15000.0,
            "medium_risk": 150000.0,
            "high_risk": 750000.0,
            "reporting_threshold": 150000.0
        },
        "EUR": {
            "low_risk": 900.0,
            "medium_risk": 9000.0,
            "high_risk": 45000.0,
            "reporting_threshold": 9000.0
        },
        "GBP": {
            "low_risk": 800.0,
            "medium_risk": 8000.0,
            "high_risk": 40000.0,
            "reporting_threshold": 8000.0
        }
    }
    
    # Channel Risk Weights
    CHANNEL_RISK_WEIGHTS: Dict[str, float] = {
        "INTERNAL": 0.1,
        "ATM": 0.2,
        "POS": 0.2,
        "MOBILE": 0.3,
        "INTERNET": 0.4,
        "BRANCH": 0.3,
        "RTGS": 0.6,
        "SWIFT": 0.8,
        "ZIPIT": 0.5
    }
    
    # ML Model Configuration
    ML_MODEL_PATH: str = os.getenv("ML_MODEL_PATH", "models/")
    MODEL_RETRAIN_INTERVAL_DAYS: int = 30
    ANOMALY_DETECTION_THRESHOLD: float = 0.7
    
    # System Monitoring
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    METRICS_ENABLED: bool = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    
    # SLA Configuration (in hours)
    SLA_HOURS: Dict[str, int] = {
        "CRITICAL": 4,
        "HIGH": 24,
        "MEDIUM": 72,
        "LOW": 168
    }
    
    # Sanctions Screening Configuration
    SANCTIONS_SIMILARITY_THRESHOLD: float = 0.8
    PEP_SIMILARITY_THRESHOLD: float = 0.85
    SANCTIONS_UPDATE_INTERVAL_HOURS: int = 24
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # File Upload Configuration
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set = {'.csv', '.xlsx', '.json'}
    
    # Cache Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TTL_SECONDS: int = 3600
    
    # Backup Configuration
    BACKUP_ENABLED: bool = os.getenv("BACKUP_ENABLED", "true").lower() == "true"
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_RETENTION_DAYS: int = 30
    
    # Audit Configuration
    AUDIT_LOG_RETENTION_DAYS: int = 2555  # 7 years
    SENSITIVE_DATA_FIELDS: list = [
        "account_number", "id_number", "phone_number", "email"
    ]
    
    # Banking Integration Configuration
    CBS_API_URL: str = os.getenv("CBS_API_URL", "http://localhost:8080/api")
    CBS_API_KEY: str = os.getenv("CBS_API_KEY", "cbs_api_key")
    CBS_TIMEOUT_SECONDS: int = 30
    
    GOAML_API_URL: str = os.getenv("GOAML_API_URL", "http://localhost:8081/api")
    GOAML_API_KEY: str = os.getenv("GOAML_API_KEY", "goaml_api_key")
    
    # Data Retention Policy
    TRANSACTION_RETENTION_YEARS: int = 7
    ALERT_RETENTION_YEARS: int = 7
    CASE_RETENTION_YEARS: int = 10
    
    # Performance Configuration
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    
    # Feature Flags
    ENABLE_ML_SCORING: bool = os.getenv("ENABLE_ML_SCORING", "true").lower() == "true"
    ENABLE_REAL_TIME_SCREENING: bool = os.getenv("ENABLE_REAL_TIME_SCREENING", "true").lower() == "true"
    ENABLE_AUTO_CASE_CREATION: bool = os.getenv("ENABLE_AUTO_CASE_CREATION", "true").lower() == "true"
    
    # Compliance Reporting
    REGULATORY_REPORTING_ENABLED: bool = True
    SAR_AUTO_FILING_ENABLED: bool = os.getenv("SAR_AUTO_FILING", "false").lower() == "true"
    
    # Geographic Risk Configuration
    HIGH_RISK_COUNTRIES: list = [
        "IRAN", "NORTH KOREA", "SYRIA", "CUBA", "AFGHANISTAN",
        "YEMEN", "SOMALIA", "LIBYA", "IRAQ", "LEBANON"
    ]
    
    MEDIUM_RISK_COUNTRIES: list = [
        "RUSSIA", "BELARUS", "MYANMAR", "VENEZUELA", "NICARAGUA",
        "ZIMBABWE", "ERITREA", "CENTRAL AFRICAN REPUBLIC"
    ]
    
    # Industry Risk Configuration
    HIGH_RISK_INDUSTRIES: list = [
        "CASINO", "GAMING", "CRYPTOCURRENCY", "MONEY_EXCHANGE",
        "PRECIOUS_METALS", "JEWELRY", "ARMS_DEALING", "ART_DEALING"
    ]
    
    # Customer Risk Configuration
    PEP_ENHANCED_DUE_DILIGENCE: bool = True
    NEW_CUSTOMER_MONITORING_DAYS: int = 90
    DORMANT_ACCOUNT_THRESHOLD_DAYS: int = 365

# Create settings instance
settings = Settings()

# Configuration validation
def validate_config():
    """Validate configuration settings"""
    errors = []
    
    # Required environment variables
    required_vars = [
        "DB_USER",
        "DB_PASSWORD",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "SECRET_KEY"
    ]
    
    for var in required_vars:
        if not getattr(settings, var):
            errors.append(f"Required environment variable {var} is not set")
    
    # Validate thresholds
    for currency, thresholds in settings.THRESHOLDS.items():
        if thresholds["low_risk"] >= thresholds["medium_risk"]:
            errors.append(f"Invalid threshold configuration for {currency}: low_risk >= medium_risk")
        if thresholds["medium_risk"] >= thresholds["high_risk"]:
            errors.append(f"Invalid threshold configuration for {currency}: medium_risk >= high_risk")
    
    # Validate SLA hours
    for priority, hours in settings.SLA_HOURS.items():
        if hours <= 0:
            errors.append(f"Invalid SLA hours for {priority}: must be positive")
    
    if errors:
        raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

# Validate configuration on import
validate_config()
