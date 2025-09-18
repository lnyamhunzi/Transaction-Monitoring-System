"""
AML Control Engine - Implementation of all 7 banking AML controls
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from models import Transaction, Customer, Alert, User, Account
from utils import calculate_transaction_velocity, get_customer_transaction_history
from sanctions_screening import SanctionsScreeningEngine

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
        self.sanctions_engine = SanctionsScreeningEngine()
    
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
        Flags transactions where:
        1. Staff post transactions onto their own accounts from the admin panel.
        2. Suspense account is debited to credit a staff account.
        3. Staff, using the customer portal, transfer funds to their own account.
        4. A transfer is made where the source and destination accounts are the same.
        """
        logger.info("Running control: staff_posting")
        processed_by = transaction_data.get('processed_by')
        customer_id = transaction_data.get('customer_id')
        counterparty_account = transaction_data.get('counterparty_account')
        account_number = transaction_data.get('account_number')

        # FORCED VIOLATION FOR ADMIN CUSTOMER ID (as per user request)
        if customer_id == "admin@mugonat.com":
            return {
                'triggered': True,
                'risk_score': 1.0, # High risk for forced violation
                'description': "FORCED VIOLATION: Transaction from admin customer ID triggered Control 1.",
                'metadata': {'customer_id': customer_id, 'violation_type': 'forced_admin_violation'}
            }
        
        staff_roles = ["admin", "compliance_officer", "aml_analyst", "supervisor"]
        staff_users = db.query(User).filter(User.role.in_(staff_roles)).all()
        staff_usernames = {user.username for user in staff_users}

        # Scenario: Admin panel self-posting
        if processed_by and processed_by in staff_usernames:
            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if customer and customer.username == processed_by:
                return {
                    'triggered': True,
                    'risk_score': 0.9,
                    'description': "Staff member posting transaction to own account from admin panel.",
                    'metadata': {'staff_id': processed_by, 'customer_id': customer_id, 'violation_type': 'admin_self_posting'}
                }

        # Scenario: Suspense account to staff
        suspense_accounts = ['SUSPENSE', 'SUSP', '999999']
        if any(susp in str(counterparty_account or '').upper() for susp in suspense_accounts):
            credited_account = db.query(Account).filter(Account.account_number == account_number).first()
            if credited_account:
                credited_customer = db.query(Customer).filter(Customer.customer_id == credited_account.customer_id).first()
                if credited_customer and credited_customer.username in staff_usernames:
                    return {
                        'triggered': True,
                        'risk_score': 0.85,
                        'description': "Suspense account debited to credit staff account.",
                        'metadata': {'suspense_account': counterparty_account, 'staff_account': account_number, 'violation_type': 'suspense_to_staff'}
                    }

        # Scenario: Staff self-posting from customer portal
        if processed_by and processed_by.startswith("customer:"):
            customer_username = processed_by.split(":", 1)[1]
            if customer_username in staff_usernames:
                if counterparty_account:
                    recipient_account = db.query(Account).filter(Account.account_number == counterparty_account).first()
                    if recipient_account:
                        recipient_customer = db.query(Customer).filter(Customer.customer_id == recipient_account.customer_id).first()
                        if recipient_customer and recipient_customer.username == customer_username:
                            return {
                                'triggered': True,
                                'risk_score': 0.8,
                                'description': "Staff member transferring funds to their own account from the customer portal.",
                                'metadata': {'staff_id': customer_username, 'customer_id': customer_id, 'violation_type': 'portal_self_posting'}
                            }

        # # Scenario: Source and destination accounts are the same
        # if account_number and counterparty_account and account_number == counterparty_account:
        #     return {
        #         'triggered': True,
        #         'risk_score': 0.7,
        #         'description': "Transaction where source and destination accounts are the same.",
        #         'metadata': {'account_number': account_number, 'violation_type': 'same_account_transfer'}
        #     }
        
        # Scenario: Source and destination accounts are the same AND it's customer-initiated
        if (account_number and counterparty_account and 
            account_number == counterparty_account and
            processed_by and processed_by.startswith("customer:")):
            
            return {
                'triggered': True,
                'risk_score': 0.7,
                'description': "Customer attempting to transfer to the same account.",
                'metadata': {'account_number': account_number, 'violation_type': 'same_account_transfer'}
            }

        # New Scenario: Counterparty Bank is "SAME"
        counterparty_bank = transaction_data.get('counterparty_bank')
        if counterparty_bank and counterparty_bank.upper() == "SAME":
            return {
                'triggered': True,
                'risk_score': 0.6, # Moderate risk for this type of internal transfer
                'description': "Transaction with counterparty bank explicitly marked as 'SAME'.",
                'metadata': {'counterparty_bank': counterparty_bank, 'violation_type': 'same_bank_transfer'}
            }
        
        return {'triggered': False, 'risk_score': 0.0, 'description': '', 'metadata': {}}
    
    async def _control_unusual_incoming(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 2: AML Unusual Transaction Customer - incoming transactions
        Flags customers performing incoming transactions out of their normal historical profile
        """
        logger.info("Running control: unusual_incoming")
        customer_id = transaction_data.get('customer_id')
        amount = transaction_data.get('base_amount', 0)
        transaction_type = transaction_data.get('transaction_type')
        
        if transaction_type != 'CREDIT':
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Not an incoming transaction', 'metadata': {}}
        
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
            logger.info(f"Insufficient history for unusual_incoming: {len(historical_transactions)} transactions")
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Insufficient transaction history', 'metadata': {}}
        
        historical_amounts = [t.base_amount for t in historical_transactions]
        avg_amount = sum(historical_amounts) / len(historical_amounts)
        max_amount = max(historical_amounts)
        variance = sum((x - avg_amount) ** 2 for x in historical_amounts) / len(historical_amounts)
        std_dev = variance ** 0.5
        
        triggered = False
        risk_score = 0.0
        description = ""
        
        if amount > avg_amount + (3 * std_dev):
            triggered = True
            risk_score = min(0.8, (amount - avg_amount) / max_amount)
            description = f"Incoming transaction of {amount} significantly exceeds historical average of {avg_amount:.2f}"
            logger.info(f"Unusual amount detected: {amount} vs avg {avg_amount:.2f}")

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
            logger.info(f"Unusual frequency detected: {today_transactions} vs avg {avg_daily_frequency:.1f}")
        
        return {
            'triggered': triggered, 'risk_score': risk_score, 'description': description,
            'metadata': {'historical_average': avg_amount, 'current_amount': amount, 'std_deviation': std_dev}
        }
    
    async def _control_small_profile_incoming(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 3: AML Small profile incoming transactions
        Flags incoming transactions that deviate from usual customer profile 
        for accounts with less than 7 transactions in history
        """
        logger.info("Running control: small_profile_incoming")
        customer_id = transaction_data.get('customer_id')
        amount = transaction_data.get('base_amount', 0)
        transaction_type = transaction_data.get('transaction_type')
        
        if transaction_type != 'CREDIT':
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Not an incoming transaction', 'metadata': {}}
        
        total_transactions = db.query(Transaction).filter(Transaction.customer_id == customer_id).count()
        
        if total_transactions >= 7:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Customer has sufficient transaction history', 'metadata': {}}
        
        historical_transactions = db.query(Transaction).filter(and_(Transaction.customer_id == customer_id, Transaction.transaction_type == 'CREDIT')).all()
        
        if not historical_transactions:
            if amount > 10000:
                logger.info(f"First transaction {amount} exceeds threshold 10000")
                return {'triggered': True, 'risk_score': 0.8, 'description': f"First incoming transaction of {amount} exceeds new customer threshold", 'metadata': {'transaction_count': 0, 'threshold_applied': 10000}}
            return {'triggered': False, 'risk_score': 0.0, 'description': 'First transaction within acceptable range', 'metadata': {}}
        
        historical_amounts = [t.base_amount for t in historical_transactions]
        max_historical = max(historical_amounts)
        avg_historical = sum(historical_amounts) / len(historical_amounts)
        
        triggered = False
        risk_score = 0.0
        description = ""
        
        if amount > max_historical * 2:
            triggered = True
            risk_score = 0.75
            description = f"Transaction amount {amount} is {amount/max_historical:.1f}x the previous maximum of {max_historical}"
            logger.info(f"Small profile amount {amount} is > 2x max {max_historical}")
        
        elif amount > avg_historical * 5:
            triggered = True
            risk_score = 0.65
            description = f"Transaction amount {amount} is {amount/avg_historical:.1f}x the historical average of {avg_historical:.2f}"
            logger.info(f"Small profile amount {amount} is > 5x avg {avg_historical}")
        
        return {'triggered': triggered, 'risk_score': risk_score, 'description': description, 'metadata': {'transaction_count': total_transactions, 'historical_max': max_historical, 'current_amount': amount}}

    async def _control_unusual_outgoing_swift(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 4: SWIFT Unusual outgoing MT103 SWIFT transactions
        """
        logger.info("Running control: unusual_outgoing_swift")
        customer_id = transaction_data.get('customer_id')
        amount = transaction_data.get('base_amount', 0)
        channel = transaction_data.get('channel', '').upper()
        transaction_type = transaction_data.get('transaction_type')
        
        if transaction_type != 'DEBIT' or 'SWIFT' not in channel:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Not an outgoing SWIFT transaction', 'metadata': {}}
        
        total_transactions = db.query(Transaction).filter(Transaction.customer_id == customer_id).count()
        
        if total_transactions <= 7:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Insufficient transaction history for this control', 'metadata': {}}
        
        ninety_days_ago = datetime.now() - timedelta(days=90)
        historical_swift = db.query(Transaction).filter(and_(Transaction.customer_id == customer_id, Transaction.transaction_type == 'DEBIT', Transaction.channel.like('%SWIFT%'), Transaction.created_at >= ninety_days_ago)).all()
        
        if len(historical_swift) < 3:
            logger.info(f"Unusual SWIFT for established customer with little SWIFT history ({len(historical_swift)} transactions)")
            return {'triggered': True, 'risk_score': 0.7, 'description': f"Unusual SWIFT transaction - customer has no recent SWIFT history", 'metadata': {'historical_swift_count': len(historical_swift), 'amount': amount}}
        
        historical_amounts = [t.base_amount for t in historical_swift]
        avg_amount = sum(historical_amounts) / len(historical_amounts)
        max_amount = max(historical_amounts)
        
        triggered = False
        risk_score = 0.0
        description = ""
        
        if amount > max_amount * 2:
            triggered = True
            risk_score = 0.8
            description = f"SWIFT amount {amount} exceeds 2x historical maximum {max_amount}"
            logger.info(f"Unusual SWIFT amount {amount} > 2x max {max_amount}")

        return {'triggered': triggered, 'risk_score': risk_score, 'description': description, 'metadata': {'avg_amount': avg_amount, 'max_amount': max_amount}}

    async def _control_small_profile_outgoing_swift(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 5: SWIFT Small profile outgoing MT103 SWIFT transactions
        """
        logger.info("Running control: small_profile_outgoing_swift")
        customer_id = transaction_data.get('customer_id')
        amount = transaction_data.get('base_amount', 0)
        channel = transaction_data.get('channel', '').upper()
        transaction_type = transaction_data.get('transaction_type')
        
        if transaction_type != 'DEBIT' or 'SWIFT' not in channel:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Not an outgoing SWIFT transaction', 'metadata': {}}
        
        total_transactions = db.query(Transaction).filter(Transaction.customer_id == customer_id).count()
        
        if total_transactions >= 7:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Customer has sufficient transaction history', 'metadata': {}}
        
        logger.info(f"Small profile customer ({total_transactions} transactions) attempting SWIFT")
        return {'triggered': True, 'risk_score': 0.8, 'description': f"Small profile customer ({total_transactions} total transactions) attempting SWIFT transfer of {amount}", 'metadata': {'total_transactions': total_transactions, 'amount': amount}}

    async def _control_cross_currency(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 6: Cross currency transactions
        """
        logger.info("Running control: cross_currency")
        channel = transaction_data.get('channel', '').upper()
        currency = transaction_data.get('currency', 'USD')
        base_currency = 'USD'
        
        monitored_channels = ['RTGS', 'INTERNAL', 'ZIPIT']
        if not any(ch in channel for ch in monitored_channels):
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Channel not monitored for cross-currency', 'metadata': {}}
        
        if currency == base_currency:
            return {'triggered': False, 'risk_score': 0.0, 'description': 'Same currency transaction', 'metadata': {}}
        
        logger.info(f"Cross-currency transaction detected: {currency} to {base_currency} on {channel}")
        return {'triggered': True, 'risk_score': 0.5, 'description': f"Cross-currency transaction: {currency} to {base_currency} on {channel}", 'metadata': {'from_currency': currency, 'to_currency': base_currency}}

    async def _control_sanctions_screening(self, transaction_data: Dict[str, Any], db: Session) -> Dict:
        """
        Control 7: AML sanction screening
        """
        logger.info("Running control: sanctions_screening")
        screening_result = await self.sanctions_engine.screen_transaction(transaction_data, db)
        
        if screening_result['matched']:
            logger.info(f"Sanctions screening triggered: {screening_result['details']}")
            return {
                'triggered': True,
                'risk_score': screening_result['risk_score'],
                'description': screening_result['details'],
                'metadata': {'matches': screening_result['matches']}
            }
        
        return {'triggered': False, 'risk_score': 0.0, 'description': 'No sanctions match', 'metadata': {}}
