"""
Utility functions for the AML Transaction Monitoring System
"""

import logging
import hashlib
import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from models import Transaction, Customer, Alert

logger = logging.getLogger(__name__)

def generate_transaction_id() -> str:
    """Generate unique transaction ID"""
    return f"TXN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

def generate_alert_id() -> str:
    """Generate unique alert ID"""
    return f"ALT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for storage"""
    if not data:
        return ""
    return hashlib.sha256(data.encode()).hexdigest()

def mask_account_number(account_number: str) -> str:
    """Mask account number for display"""
    if not account_number or len(account_number) < 4:
        return account_number
    return "*" * (len(account_number) - 4) + account_number[-4:]

def mask_id_number(id_number: str) -> str:
    """Mask ID number for display"""
    if not id_number or len(id_number) < 4:
        return id_number
    return id_number[:2] + "*" * (len(id_number) - 4) + id_number[-2:]

def validate_email(email: str) -> bool:
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    # Check if it's between 7 and 15 digits
    return 7 <= len(digits_only) <= 15

def standardize_name(name: str) -> str:
    """Standardize name for comparison"""
    if not name:
        return ""
    
    # Convert to uppercase and remove extra spaces
    standardized = ' '.join(name.upper().split())
    
    # Remove common prefixes and suffixes
    prefixes = ['MR', 'MRS', 'MS', 'DR', 'PROF', 'REV']
    suffixes = ['JR', 'SR', 'III', 'IV', 'PhD', 'MD']
    
    words = standardized.split()
    
    # Remove prefixes
    if words and words[0] in prefixes:
        words = words[1:]
    
    # Remove suffixes
    if words and words[-1] in suffixes:
        words = words[:-1]
    
    return ' '.join(words)

def calculate_age(date_of_birth: datetime) -> int:
    """Calculate age from date of birth"""
    if not date_of_birth:
        return 0
    
    today = datetime.now()
    age = today.year - date_of_birth.year
    
    # Adjust if birthday hasn't occurred this year
    if today.month < date_of_birth.month or (today.month == date_of_birth.month and today.day < date_of_birth.day):
        age -= 1
    
    return age

def format_currency(amount: float, currency: str = "USD") -> str:
    """Format currency amount for display"""
    currency_symbols = {
        'USD': '$',
        'ZWL': 'Z$',
        'ZAR': 'R',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'CNY': '¥',
        'AUD': 'A$',
        'CAD': 'C$',
        'CHF': 'Fr'
    }
    
    symbol = currency_symbols.get(currency, currency)
    
    if currency in ['JPY']:
        return f"{symbol}{amount:,.0f}"
    else:
        return f"{symbol}{amount:,.2f}"

def parse_amount(amount_str: str) -> Optional[float]:
    """Parse amount string to float"""
    if not amount_str:
        return None
    
    # Remove currency symbols and spaces
    cleaned = re.sub(r'[^\d.,\-]', '', str(amount_str))
    
    try:
        # Handle different decimal separators
        if ',' in cleaned and '.' in cleaned:
            # Assume comma is thousands separator
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Could be decimal separator (European style)
            parts = cleaned.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                cleaned = cleaned.replace(',', '.')
        
        return float(cleaned)
    except (ValueError, TypeError):
        logger.error(f"Could not parse amount: {amount_str}")
        return None

def calculate_transaction_velocity(customer_id: str, hours: int, db: Session) -> float:
    """Calculate transaction velocity for a customer"""
    try:
        start_time = datetime.now() - timedelta(hours=hours)
        
        transaction_count = db.query(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Transaction.created_at >= start_time
            )
        ).count()
        
        return transaction_count / hours
        
    except Exception as e:
        logger.error(f"Error calculating transaction velocity: {e}")
        return 0.0

def get_customer_transaction_history(customer_id: str, days: int, db: Session) -> List[Transaction]:
    """Get customer transaction history"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        transactions = db.query(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Transaction.created_at >= start_date
            )
        ).order_by(desc(Transaction.created_at)).all()
        
        return transactions
        
    except Exception as e:
        logger.error(f"Error getting customer transaction history: {e}")
        return []

def calculate_customer_risk_factors(customer_id: str, db: Session) -> Dict[str, Any]:
    """Calculate various risk factors for a customer"""
    try:
        customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if not customer:
            return {}
        
        # Recent transaction analysis
        recent_transactions = get_customer_transaction_history(customer_id, 30, db)
        
        # Calculate metrics
        total_volume = sum(t.base_amount for t in recent_transactions)
        avg_transaction = total_volume / len(recent_transactions) if recent_transactions else 0
        max_transaction = max(t.base_amount for t in recent_transactions) if recent_transactions else 0
        
        # Velocity metrics
        velocity_24h = calculate_transaction_velocity(customer_id, 24, db)
        velocity_7d = calculate_transaction_velocity(customer_id, 168, db)  # 7 days in hours
        
        # Channel diversity
        channels_used = set(t.channel for t in recent_transactions)
        channel_diversity = len(channels_used)
        
        # Time pattern analysis
        transaction_hours = [t.created_at.hour for t in recent_transactions]
        unusual_hours = sum(1 for hour in transaction_hours if hour < 6 or hour > 22)
        unusual_hours_ratio = unusual_hours / len(transaction_hours) if transaction_hours else 0
        
        # Recent alerts
        recent_alerts = db.query(Alert).join(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Alert.created_at >= datetime.now() - timedelta(days=30)
            )
        ).count()
        
        # Customer age (days since account opening)
        account_age_days = 0
        if customer.account_opening_date:
            account_age_days = (datetime.now() - customer.account_opening_date).days
        
        return {
            'total_volume_30d': total_volume,
            'transaction_count_30d': len(recent_transactions),
            'avg_transaction_amount': avg_transaction,
            'max_transaction_amount': max_transaction,
            'velocity_24h': velocity_24h,
            'velocity_7d': velocity_7d,
            'channel_diversity': channel_diversity,
            'unusual_hours_ratio': unusual_hours_ratio,
            'recent_alerts_count': recent_alerts,
            'account_age_days': account_age_days,
            'is_pep': customer.is_pep,
            'risk_rating': customer.risk_rating.value if customer.risk_rating else 'LOW'
        }
        
    except Exception as e:
        logger.error(f"Error calculating customer risk factors: {e}")
        return {}

def extract_transaction_features(transaction_data: Dict[str, Any]) -> Dict[str, float]:
    """Extract numerical features from transaction data for ML models"""
    try:
        features = {}
        
        # Basic transaction features
        features['amount'] = float(transaction_data.get('base_amount', 0))
        features['amount_log'] = float(np.log1p(features['amount']))
        
        # Time-based features
        timestamp = transaction_data.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        features['hour'] = float(timestamp.hour)
        features['day_of_week'] = float(timestamp.weekday())
        features['day_of_month'] = float(timestamp.day)
        features['month'] = float(timestamp.month)
        features['is_weekend'] = float(timestamp.weekday() >= 5)
        features['is_business_hours'] = float(9 <= timestamp.hour <= 17)
        
        # Channel encoding
        channel = transaction_data.get('channel', '').upper()
        channel_mapping = {
            'INTERNAL': 1, 'ATM': 2, 'POS': 3, 'MOBILE': 4,
            'INTERNET': 5, 'BRANCH': 6, 'RTGS': 7, 'SWIFT': 8, 'ZIPIT': 9
        }
        features['channel_encoded'] = float(channel_mapping.get(channel, 0))
        
        # Transaction type encoding
        txn_type = transaction_data.get('transaction_type', '').upper()
        type_mapping = {'CREDIT': 1, 'DEBIT': 2, 'TRANSFER': 3}
        features['transaction_type_encoded'] = float(type_mapping.get(txn_type, 0))
        
        # Currency encoding
        currency = transaction_data.get('currency', 'USD')
        currency_mapping = {
            'USD': 1, 'ZWL': 2, 'ZAR': 3, 'EUR': 4, 'GBP': 5,
            'JPY': 6, 'CNY': 7, 'AUD': 8, 'CAD': 9, 'CHF': 10
        }
        features['currency_encoded'] = float(currency_mapping.get(currency, 0))
        
        # Cross-border indicator
        features['is_cross_border'] = float(bool(transaction_data.get('counterparty_country')))
        
        # High-value indicator
        features['is_high_value'] = float(features['amount'] > 10000)
        
        return features
        
    except Exception as e:
        logger.error(f"Error extracting transaction features: {e}")
        return {}

def calculate_similarity_score(text1: str, text2: str) -> float:
    """Calculate similarity score between two text strings"""
    if not text1 or not text2:
        return 0.0
    
    # Simple Levenshtein distance-based similarity
    def levenshtein_distance(s1, s2):
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    text1 = text1.upper().strip()
    text2 = text2.upper().strip()
    
    max_len = max(len(text1), len(text2))
    if max_len == 0:
        return 1.0
    
    distance = levenshtein_distance(text1, text2)
    similarity = 1 - (distance / max_len)
    
    return max(0.0, similarity)

def validate_iban(iban: str) -> bool:
    """Validate IBAN format"""
    if not iban:
        return False
    
    # Remove spaces and convert to uppercase
    iban = iban.replace(' ', '').upper()
    
    # Check length (should be between 15 and 34 characters)
    if not (15 <= len(iban) <= 34):
        return False
    
    # Check if starts with two letters
    if not iban[:2].isalpha():
        return False
    
    # Check if next two characters are digits
    if not iban[2:4].isdigit():
        return False
    
    # Simple format validation (full IBAN validation requires country-specific rules)
    return True

def validate_swift_code(swift_code: str) -> bool:
    """Validate SWIFT/BIC code format"""
    if not swift_code:
        return False
    
    swift_code = swift_code.upper().strip()
    
    # SWIFT codes are 8 or 11 characters
    if len(swift_code) not in [8, 11]:
        return False
    
    # First 4 characters should be letters (bank code)
    if not swift_code[:4].isalpha():
        return False
    
    # Next 2 characters should be letters (country code)
    if not swift_code[4:6].isalpha():
        return False
    
    # Next 2 characters should be alphanumeric (location code)
    if not swift_code[6:8].isalnum():
        return False
    
    # If 11 characters, last 3 should be alphanumeric (branch code)
    if len(swift_code) == 11 and not swift_code[8:11].isalnum():
        return False
    
    return True

def format_large_number(number: float) -> str:
    """Format large numbers with appropriate suffixes"""
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    elif number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    elif number >= 1_000:
        return f"{number / 1_000:.1f}K"
    else:
        return f"{number:.0f}"

def get_business_days_between(start_date: datetime, end_date: datetime) -> int:
    """Calculate business days between two dates"""
    business_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days

def is_business_day(date: datetime) -> bool:
    """Check if a date is a business day"""
    return date.weekday() < 5

def get_next_business_day(date: datetime) -> datetime:
    """Get the next business day"""
    next_day = date + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day

def sanitize_input(input_string: str) -> str:
    """Sanitize input string to prevent XSS"""
    if not input_string:
        return ""
    
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', input_string)
    
    # Remove potential script injections
    clean = re.sub(r'javascript:', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'vbscript:', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'on\w+\s*=', '', clean, flags=re.IGNORECASE)
    
    return clean.strip()

# Import numpy for logarithmic calculations
try:
    import numpy as np
except ImportError:
    # Fallback implementation if numpy is not available
    import math
    
    class NumpyFallback:
        @staticmethod
        def log1p(x):
            return math.log(1 + x)
    
    np = NumpyFallback()
