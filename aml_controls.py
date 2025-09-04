"""
AML Control Engine - Implementation of all 7 banking AML controls
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from models import Transaction, Customer, Alert
from utils import calculate_transaction_velocity, get_customer_transaction_history

logger = logging.getLogger(__name__)

class AMLControlEngine:
    """Comprehensive AML Control Engine implementing all banking controls"""
    
    def __init__(self):
        self.controls = {
            "staff_posting": self._control_staff_posting,
            "unusual_incoming": self._control_unusual_incoming,
            "small_profile_incoming": self._control_small_profile_incoming,
            "unusual_outgoing_swift": self._control_unusual_outgoing_swift,
            "small_profile_outgoing_swift": self._control_small_profile_outgoing_swift,
            "cross_currency": self._control_cross_currency,
            "sanctions_screening": self._control_sanctions_screening
        }
    
    async def run_all_controls(self, transaction_data: Dict[str, Any], db: Session) -> Dict[str, Dict]:
        """Run all AML controls on a transaction"""
        results = {}
        
        for control_name, control_func in self.controls.items():
            try:
                result = await control_func(transaction_data, db)
                results[control_name] = result
                
                if result['triggered']:
                    logger.info(f"AML Control {control_name} triggered for transaction {transaction_data.get('id', 'unknown')}")
                
            except Exception as e:
                logger.error(f"Error running AML control {control_name}: {e}")
                results[control_name] = {
                    'triggered': False,
                    'risk_score': 0.0,
                    'description': f"Control error: {str(e)}",
                    'metadata': {}
                }
        
        return results
    
    async def _control_staff_posting(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 1: AML Staff posting transactions into their own accounts
        Flags transactions where staff post transactions onto their own accounts
        or where suspense account is debited to credit a staff account
        """
        processed_by = transaction_data.get('processed_by')
        customer_id = transaction_data.get('customer_id')
        counterparty_account = transaction_data.get('counterparty_account')
        account_number = transaction_data.get('account_number')
        
        triggered = False
        risk_score = 0.0
        description = ""
        metadata = {}
        
        # Check if staff is posting to their own account
        if processed_by and customer_id:
            # Assuming staff IDs follow a pattern or we have a staff table
            if processed_by == customer_id or processed_by in customer_id:
                triggered = True
                risk_score = 0.9
                description = "Staff member posting transaction to own account"
                metadata = {
                    'staff_id': processed_by,
                    'customer_id': customer_id,
                    'violation_type': 'self_posting'
                }
        
        # Check for suspense account to staff account transfers
        suspense_accounts = ['SUSPENSE', 'SUSP', '999999']
        if any(susp in str(counterparty_account or '').upper() for susp in suspense_accounts):
            # Check if destination is staff account
            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if customer and any(staff_indicator in customer.full_name.upper() 
                             for staff_indicator in ['STAFF', 'EMPLOYEE', 'EMP']):
                triggered = True
                risk_score = 0.85
                description = "Suspense account debited to credit staff account"
                metadata = {
                    'suspense_account': counterparty_account,
                    'staff_account': account_number,
                    'violation_type': 'suspense_to_staff'
                }
        
        return {
            'triggered': triggered,
            'risk_score': risk_score,
            'description': description,
            'metadata': metadata
        }
    
    async def _control_unusual_incoming(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 2: AML Unusual Transaction Customer - incoming transactions
        Flags customers performing incoming transactions out of their normal historical profile
        """
        customer_id = transaction_data.get('customer_id')
        amount = transaction_data.get('base_amount', 0)
        transaction_type = transaction_data.get('transaction_type')
        
        if transaction_type != 'CREDIT':
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Not an incoming transaction', 'metadata': {}}
        
        # Get customer's historical incoming transaction profile
        thirty_days_ago = datetime.now() - timedelta(days=30)
        historical_transactions = db.query(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Transaction.transaction_type == 'CREDIT',
                Transaction.created_at >= thirty_days_ago,
                Transaction.created_at < datetime.now()
            )
        ).all()
        
        if len(historical_transactions) < 7:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Insufficient transaction history', 'metadata': {}}
        
        # Calculate statistical measures
        historical_amounts = [t.base_amount for t in historical_transactions]
        avg_amount = sum(historical_amounts) / len(historical_amounts)
        max_amount = max(historical_amounts)
        
        # Calculate standard deviation
        variance = sum((x - avg_amount) ** 2 for x in historical_amounts) / len(historical_amounts)
        std_dev = variance ** 0.5
        
        triggered = False
        risk_score = 0.0
        description = ""
        
        # Flag if current transaction is significantly higher than historical pattern
        if amount > avg_amount + (3 * std_dev):
            triggered = True
            risk_score = min(0.8, (amount - avg_amount) / max_amount)
            description = f"Incoming transaction of {amount} significantly exceeds historical average of {avg_amount:.2f}"
        
        # Additional check for frequency
        today_transactions = db.query(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Transaction.transaction_type == 'CREDIT',
                Transaction.created_at >= datetime.now().date()
            )
        ).count()
        
        avg_daily_frequency = len(historical_transactions) / 30
        if today_transactions > avg_daily_frequency * 3:
            triggered = True
            risk_score = max(risk_score, 0.7)
            description += f" Unusual frequency: {today_transactions} transactions today vs average {avg_daily_frequency:.1f}"
        
        return {
            'triggered': triggered,
            'risk_score': risk_score,
            'description': description,
            'metadata': {
                'historical_average': avg_amount,
                'current_amount': amount,
                'std_deviation': std_dev,
                'frequency_today': today_transactions,
                'avg_daily_frequency': avg_daily_frequency
            }
        }
    
    async def _control_small_profile_incoming(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 3: AML Small profile incoming transactions
        Flags incoming transactions that deviate from usual customer profile 
        for accounts with less than 7 transactions in history
        """
        customer_id = transaction_data.get('customer_id')
        amount = transaction_data.get('base_amount', 0)
        transaction_type = transaction_data.get('transaction_type')
        
        if transaction_type != 'CREDIT':
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Not an incoming transaction', 'metadata': {}}
        
        # Get total transaction history
        total_transactions = db.query(Transaction).filter(
            Transaction.customer_id == customer_id
        ).count()
        
        if total_transactions >= 7:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Customer has sufficient transaction history', 'metadata': {}}
        
        # Get all historical transactions for limited profile analysis
        historical_transactions = db.query(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Transaction.transaction_type == 'CREDIT'
            )
        ).all()
        
        if not historical_transactions:
            # First transaction - apply basic threshold
            if amount > 10000:  # USD 10,000 threshold for new customers
                return {
                    'triggered': True,
                    'risk_score': 0.8,
                    'description': f"First incoming transaction of {amount} exceeds new customer threshold",
                    'metadata': {'transaction_count': 0, 'threshold_applied': 10000}
                }
            return {'triggered': False, 'risk_score': 0.0, 'description': 'First transaction within acceptable range', 'metadata': {}}
        
        # For customers with 1-6 transactions, apply stricter deviation rules
        historical_amounts = [t.base_amount for t in historical_transactions]
        max_historical = max(historical_amounts)
        avg_historical = sum(historical_amounts) / len(historical_amounts)
        
        triggered = False
        risk_score = 0.0
        description = ""
        
        # Flag if current transaction is 200% higher than previous maximum
        if amount > max_historical * 2:
            triggered = True
            risk_score = 0.75
            description = f"Transaction amount {amount} is {amount/max_historical:.1f}x the previous maximum of {max_historical}"
        
        # Flag if amount is 5x the historical average
        elif amount > avg_historical * 5:
            triggered = True
            risk_score = 0.65
            description = f"Transaction amount {amount} is {amount/avg_historical:.1f}x the historical average of {avg_historical:.2f}"
        
        return {
            'triggered': triggered,
            'risk_score': risk_score,
            'description': description,
            'metadata': {
                'transaction_count': total_transactions,
                'historical_max': max_historical,
                'historical_avg': avg_historical,
                'current_amount': amount
            }
        }
    
    async def _control_unusual_outgoing_swift(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 4: SWIFT Unusual outgoing MT103 SWIFT transactions
        Flags outgoing MX messages (ISO 20022) on SWIFT CBPR+ transactions 
        that deviate from usual customer profile for customers with >7 transactions
        """
        customer_id = transaction_data.get('customer_id')
        amount = transaction_data.get('base_amount', 0)
        channel = transaction_data.get('channel', '').upper()
        transaction_type = transaction_data.get('transaction_type')
        counterparty_bank = transaction_data.get('counterparty_bank', '')
        
        # Only process outgoing SWIFT transactions
        if transaction_type != 'DEBIT' or 'SWIFT' not in channel:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Not an outgoing SWIFT transaction', 'metadata': {}}
        
        # Check if customer has sufficient transaction history
        total_transactions = db.query(Transaction).filter(
            Transaction.customer_id == customer_id
        ).count()
        
        if total_transactions <= 7:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Insufficient transaction history for this control', 'metadata': {}}
        
        # Get historical SWIFT outgoing transactions
        ninety_days_ago = datetime.now() - timedelta(days=90)
        historical_swift = db.query(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Transaction.transaction_type == 'DEBIT',
                Transaction.channel.like('%SWIFT%'),
                Transaction.created_at >= ninety_days_ago
            )
        ).all()
        
        if len(historical_swift) < 3:
            # Flag unusual SWIFT activity for customers without SWIFT history
            return {
                'triggered': True,
                'risk_score': 0.7,
                'description': f"Unusual SWIFT transaction - customer has no recent SWIFT history",
                'metadata': {'historical_swift_count': len(historical_swift), 'amount': amount}
            }
        
        # Analyze historical SWIFT patterns
        historical_amounts = [t.base_amount for t in historical_swift]
        historical_banks = [t.counterparty_bank for t in historical_swift if t.counterparty_bank is not None]
        
        avg_amount = sum(historical_amounts) / len(historical_amounts)
        max_amount = max(historical_amounts)
        
        # Calculate monthly SWIFT frequency
        monthly_frequency = len(historical_swift) / 3  # 90 days = ~3 months
        current_month_swift = db.query(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Transaction.transaction_type == 'DEBIT',
                Transaction.channel.like('%SWIFT%'),
                Transaction.created_at >= datetime.now().replace(day=1)
            )
        ).count()
        
        triggered = False
        risk_score = 0.0
        description = ""
        metadata = {
            'historical_swift_count': len(historical_swift),
            'avg_amount': avg_amount,
            'max_amount': max_amount,
            'monthly_frequency': monthly_frequency,
            'current_month_swift': current_month_swift
        }
        
        # Flag unusual amount
        if amount > max_amount * 2:
            triggered = True
            risk_score = 0.8
            description = f"SWIFT amount {amount} exceeds 2x historical maximum {max_amount}"
        elif amount > avg_amount * 5:
            triggered = True
            risk_score = 0.7
            description = f"SWIFT amount {amount} exceeds 5x historical average {avg_amount:.2f}"
        
        # Flag unusual frequency
        if current_month_swift > monthly_frequency * 3:
            triggered = True
            risk_score = max(risk_score, 0.65)
            description += f" Unusual SWIFT frequency: {current_month_swift} this month vs average {monthly_frequency:.1f}"
        
        # Flag new destination bank
        if counterparty_bank and counterparty_bank not in historical_banks:
            risk_score = max(risk_score, 0.6)
            if triggered:
                description += f" New destination bank: {counterparty_bank}"
            else:
                triggered = True
                risk_score = 0.6
                description = f"SWIFT to new destination bank: {counterparty_bank}"
        
        return {
            'triggered': triggered,
            'risk_score': risk_score,
            'description': description,
            'metadata': metadata
        }
    
    async def _control_small_profile_outgoing_swift(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 5: SWIFT Small profile outgoing MT103 SWIFT transactions
        Flags outgoing SWIFT transactions for customers with <7 transactions in history
        """
        customer_id = transaction_data.get('customer_id')
        amount = transaction_data.get('base_amount', 0)
        channel = transaction_data.get('channel', '').upper()
        transaction_type = transaction_data.get('transaction_type')
        
        # Only process outgoing SWIFT transactions
        if transaction_type != 'DEBIT' or 'SWIFT' not in channel:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Not an outgoing SWIFT transaction', 'metadata': {}}
        
        # Check transaction history
        total_transactions = db.query(Transaction).filter(
            Transaction.customer_id == customer_id
        ).count()
        
        if total_transactions >= 7:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Customer has sufficient transaction history', 'metadata': {}}
        
        # For small profile customers, SWIFT transactions are inherently suspicious
        swift_history = db.query(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Transaction.channel.like('%SWIFT%')
            )
        ).count()
        
        triggered = True
        risk_score = 0.8  # High risk for new customers doing SWIFT
        description = f"Small profile customer ({total_transactions} total transactions) attempting SWIFT transfer of {amount}"
        
        # Increase risk score based on amount and lack of SWIFT history
        if amount > 50000:  # High value SWIFT
            risk_score = 0.9
            description += f" - High value SWIFT transaction"
        
        if swift_history == 0:  # First SWIFT transaction
            risk_score = min(0.95, risk_score + 0.1)
            description += f" - First SWIFT transaction for customer"
        
        return {
            'triggered': triggered,
            'risk_score': risk_score,
            'description': description,
            'metadata': {
                'total_transactions': total_transactions,
                'swift_history_count': swift_history,
                'amount': amount
            }
        }
    
    async def _control_cross_currency(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 6: Cross currency transactions
        Flags cross-currency transactions on RTGS, Internal transfers, Zipit channels
        """
        channel = transaction_data.get('channel', '').upper()
        currency = transaction_data.get('currency', 'USD')
        amount = transaction_data.get('amount', 0)
        base_currency = 'USD'  # System base currency
        
        # Only monitor specific channels
        monitored_channels = ['RTGS', 'INTERNAL', 'ZIPIT']
        if not any(ch in channel for ch in monitored_channels):
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Channel not monitored for cross-currency', 'metadata': {}}
        
        # Check if transaction involves currency conversion
        if currency == base_currency:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Same currency transaction', 'metadata': {}}
        
        # Flag cross-currency transaction
        triggered = True
        risk_score = 0.5  # Base risk for cross-currency
        description = f"Cross-currency transaction: {currency} to {base_currency} on {channel}"
        
        # Increase risk based on amount and currency
        if amount > 10000:
            risk_score = 0.7
            description += f" - High value cross-currency transaction"
        
        # Higher risk for certain currency pairs
        high_risk_currencies = ['ZWL', 'ZAR', 'GBP', 'EUR']
        if currency in high_risk_currencies:
            risk_score = min(0.8, risk_score + 0.2)
            description += f" - Involves high-risk currency {currency}"
        
        # Check customer's cross-currency history
        customer_id = transaction_data.get('customer_id')
        historical_cross_currency = db.query(Transaction).filter(
            and_(
                Transaction.customer_id == customer_id,
                Transaction.currency != base_currency
            )
        ).count()
        
        if historical_cross_currency == 0:
            risk_score = min(0.85, risk_score + 0.15)
            description += f" - First cross-currency transaction for customer"
        
        return {
            'triggered': triggered,
            'risk_score': risk_score,
            'description': description,
            'metadata': {
                'from_currency': currency,
                'to_currency': base_currency,
                'channel': channel,
                'amount': amount,
                'cross_currency_history': historical_cross_currency
            }
        }
    
    async def _control_sanctions_screening(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 7: AML sanction screening
        Screens real-time customer transactions and onboarding against sanctions lists
        Note: This is a simplified version - full implementation would involve 
        dedicated sanctions screening service
        """
        customer_id = transaction_data.get('customer_id')
        counterparty_name = transaction_data.get('counterparty_name', '')
        counterparty_bank = transaction_data.get('counterparty_bank', '')
        
        # Get customer information
        customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        
        # Basic sanctions keywords (in production, use comprehensive sanctions lists)
        sanctions_keywords = [
            'OFAC', 'SDN', 'BLOCKED', 'DENIED', 'TERRORIST', 'SANCTIONS',
            'EMBARGO', 'FROZEN', 'IRAN', 'NORTH KOREA', 'SYRIA', 'CUBA'
        ]
        
        triggered = False
        risk_score = 0.0
        description = ""
        metadata = {}
        
        # Screen customer name
        if customer:
            customer_name_upper = customer.full_name.upper()
            for keyword in sanctions_keywords:
                if keyword in customer_name_upper:
                    triggered = True
                    risk_score = 1.0
                    description = f"Customer name contains sanctions keyword: {keyword}"
                    metadata['matched_entity'] = customer.full_name
                    metadata['matched_keyword'] = keyword
                    break
        
        # Screen counterparty name
        if counterparty_name:
            counterparty_upper = counterparty_name.upper()
            for keyword in sanctions_keywords:
                if keyword in counterparty_upper:
                    triggered = True
                    risk_score = 1.0
                    description = f"Counterparty name contains sanctions keyword: {keyword}"
                    metadata['matched_entity'] = counterparty_name
                    metadata['matched_keyword'] = keyword
                    break
        
        # Screen counterparty bank
        if counterparty_bank:
            bank_upper = counterparty_bank.upper()
            for keyword in sanctions_keywords:
                if keyword in bank_upper:
                    triggered = True
                    risk_score = 1.0
                    description = f"Counterparty bank contains sanctions keyword: {keyword}"
                    metadata['matched_entity'] = counterparty_bank
                    metadata['matched_keyword'] = keyword
                    break
        
        # Additional screening for high-risk countries
        high_risk_countries = ['IRAN', 'NORTH KOREA', 'SYRIA', 'CUBA', 'RUSSIA', 'BELARUS']
        narrative = transaction_data.get('narrative', '').upper()
        for country in high_risk_countries:
            if country in narrative or (counterparty_bank and country in counterparty_bank.upper()):
                triggered = True
                risk_score = max(risk_score, 0.9)
                description += f" Transaction involves high-risk country: {country}"
                metadata['high_risk_country'] = country
                break
        
        return {
            'triggered': triggered,
            'risk_score': risk_score,
            'description': description,
            'metadata': metadata
        }
