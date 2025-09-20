"""
Risk Scoring Engine for transaction risk assessment
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from models import RiskRating

from models import Transaction, Customer, Alert
from utils import calculate_customer_risk_factors

logger = logging.getLogger(__name__)

class RiskScoringEngine:
    """Comprehensive risk scoring engine for transactions"""
    
    def __init__(self):
        self.risk_weights = {
            'amount_risk': 0.25,
            'frequency_risk': 0.20,
            'customer_risk': 0.20,
            'channel_risk': 0.15,
            'geographic_risk': 0.10,
            'behavioral_risk': 0.10
        }
        
        # Risk thresholds by currency
        self.amount_thresholds = {
            'USD': {'low': 1000, 'medium': 10000, 'high': 50000},
            'ZWL': {'low': 1000000, 'medium': 10000000, 'high': 50000000},
            'ZAR': {'low': 15000, 'medium': 150000, 'high': 750000},
            'EUR': {'low': 900, 'medium': 9000, 'high': 45000},
            'GBP': {'low': 800, 'medium': 8000, 'high': 40000}
        }
        
        # Channel risk levels
        self.channel_risks = {
            'INTERNAL': 0.1,
            'ATM': 0.2,
            'POS': 0.2,
            'MOBILE': 0.3,
            'INTERNET': 0.4,
            'BRANCH': 0.3,
            'RTGS': 0.6,
            'SWIFT': 0.8,
            'ZIPIT': 0.5
        }
    
    async def calculate_risk_score(self, transaction_data: Dict[str, Any], db: Session) -> float:
        """Calculate comprehensive risk score for a transaction"""
        try:
            # Calculate individual risk components
            amount_risk = await self.calculate_amount_risk(transaction_data, db)
            frequency_risk = await self.calculate_frequency_risk(transaction_data, db)
            customer_risk = await self.calculate_customer_risk(transaction_data, db)
            channel_risk = await self.calculate_channel_risk(transaction_data)
            geographic_risk = await self.calculate_geographic_risk(transaction_data)
            behavioral_risk = await self.calculate_behavioral_risk(transaction_data, db)
            
            # Calculate weighted risk score
            total_score = (
                (amount_risk * self.risk_weights['amount_risk']) +
                (frequency_risk * self.risk_weights['frequency_risk']) +
                (customer_risk * self.risk_weights['customer_risk']) +
                (channel_risk * self.risk_weights['channel_risk']) +
                (geographic_risk * self.risk_weights['geographic_risk']) +
                (behavioral_risk * self.risk_weights['behavioral_risk'])
            )
            
            # Ensure score is between 0 and 1
            final_score = max(0.0, min(1.0, total_score))
            
            logger.info(f"Risk score calculated: {final_score:.3f} (Amount: {amount_risk:.2f}, "
                       f"Frequency: {frequency_risk:.2f}, Customer: {customer_risk:.2f}, "
                       f"Channel: {channel_risk:.2f}, Geographic: {geographic_risk:.2f}, "
                       f"Behavioral: {behavioral_risk:.2f})")
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return 0.5  # Default medium risk
    
    async def calculate_amount_risk(self, transaction_data: Dict[str, Any], db: Session) -> float:
        """Calculate risk based on transaction amount"""
        try:
            amount = transaction_data.get('base_amount', 0)
            currency = transaction_data.get('currency', 'USD')
            customer_id = transaction_data.get('customer_id')
            
            # Get currency-specific thresholds
            thresholds = self.amount_thresholds.get(currency, self.amount_thresholds['USD'])
            
            # Base amount risk
            if amount >= thresholds['high']:
                amount_risk = 0.9
            elif amount >= thresholds['medium']:
                amount_risk = 0.6
            elif amount >= thresholds['low']:
                amount_risk = 0.3
            else:
                amount_risk = 0.1
            
            # Adjust based on customer's historical amounts
            customer_avg = await self.get_customer_average_amount(customer_id, db)
            if customer_avg > 0:
                ratio = amount / customer_avg
                if ratio > 10:  # 10x higher than average
                    amount_risk = min(1.0, amount_risk + 0.3)
                elif ratio > 5:  # 5x higher than average
                    amount_risk = min(1.0, amount_risk + 0.2)
                elif ratio > 2:  # 2x higher than average
                    amount_risk = min(1.0, amount_risk + 0.1)
            
            return amount_risk
            
        except Exception as e:
            logger.error(f"Error calculating amount risk: {e}")
            return 0.3
    
    async def calculate_frequency_risk(self, transaction_data: Dict[str, Any], db: Session) -> float:
        """Calculate risk based on transaction frequency"""
        try:
            customer_id = transaction_data.get('customer_id')
            
            # Count transactions in different time windows
            now = datetime.now()
            
            # Transactions in last hour
            txn_1h = db.query(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= now - timedelta(hours=1)
                )
            ).count()
            
            # Transactions today
            txn_today = db.query(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= now.replace(hour=0, minute=0, second=0)
                )
            ).count()
            
            # Transactions this week
            week_start = now - timedelta(days=now.weekday())
            txn_week = db.query(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= week_start
                )
            ).count()
            
            # Calculate frequency risk
            frequency_risk = 0.0
            
            # High frequency in short time periods is suspicious
            if txn_1h >= 5:
                frequency_risk = 0.9
            elif txn_1h >= 3:
                frequency_risk = 0.7
            elif txn_today >= 20:
                frequency_risk = max(frequency_risk, 0.8)
            elif txn_today >= 10:
                frequency_risk = max(frequency_risk, 0.6)
            elif txn_week >= 100:
                frequency_risk = max(frequency_risk, 0.5)
            elif txn_week >= 50:
                frequency_risk = max(frequency_risk, 0.3)
            else:
                frequency_risk = 0.1
            
            return frequency_risk
            
        except Exception as e:
            logger.error(f"Error calculating frequency risk: {e}")
            return 0.2
    
    async def calculate_customer_risk(self, transaction_data: Dict[str, Any], db: Session) -> float:
        """Calculate risk based on customer profile"""
        try:
            customer_id = transaction_data.get('customer_id')
            
            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if not customer:
                return 0.7  # High risk for unknown customer
            
            customer_risk = 0.0
            
            # Start with a base risk based on customer's current rating, but allow other factors to override
            if customer.risk_rating.value == 'CRITICAL':
                customer_risk = max(customer_risk, 0.7)
            elif customer.risk_rating.value == 'HIGH':
                customer_risk = max(customer_risk, 0.5)
            elif customer.risk_rating.value == 'MEDIUM':
                customer_risk = max(customer_risk, 0.4)
            # If LOW, customer_risk remains 0.0 initially, and other factors will increase it
            
            # PEP status significantly increases risk
            if customer.is_pep:
                customer_risk = max(customer_risk, 0.8) # High inherent risk for PEP
            
            # New customer risk
            if customer.account_opening_date:
                days_since_opening = (datetime.now() - customer.account_opening_date).days
                if days_since_opening < 30:  # New customer
                    customer_risk = max(customer_risk, 0.6) # Medium-high risk for new customers
                elif days_since_opening < 90:  # Recently opened
                    customer_risk = max(customer_risk, 0.3) # Medium risk for recently opened
            
            # High-risk occupations
            high_risk_occupations = [
                'POLITICIAN', 'GOVERNMENT', 'CASINO', 'EXCHANGE', 'DEALER',
                'BROKER', 'ARMS', 'JEWELRY', 'PRECIOUS METALS'
            ]
            if customer.occupation:
                for occupation in high_risk_occupations:
                    if occupation in customer.occupation.upper():
                        customer_risk = max(customer_risk, 0.7) # High risk for high-risk occupation
                        break
            
            return min(1.0, customer_risk) # Ensure it doesn't exceed 1.0
            
        except Exception as e:
            logger.error(f"Error calculating customer risk: {e}")
            return 0.5
    
    async def calculate_channel_risk(self, transaction_data: Dict[str, Any]) -> float:
        """Calculate risk based on transaction channel"""
        try:
            channel = transaction_data.get('channel', '').upper()
            
            # Find matching channel risk
            for channel_pattern, risk in self.channel_risks.items():
                if channel_pattern in channel:
                    return risk
            
            # Default risk for unknown channels
            return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating channel risk: {e}")
            return 0.3
    
    async def calculate_geographic_risk(self, transaction_data: Dict[str, Any]) -> float:
        """Calculate risk based on geographic factors"""
        try:
            counterparty_bank = transaction_data.get('counterparty_bank', '')
            counterparty_country = transaction_data.get('counterparty_country', '')
            
            # High-risk countries
            high_risk_countries = [
                'IRAN', 'NORTH KOREA', 'SYRIA', 'CUBA', 'AFGHANISTAN',
                'YEMEN', 'SOMALIA', 'LIBYA', 'IRAQ', 'LEBANON'
            ]
            
            # Medium-risk countries
            medium_risk_countries = [
                'RUSSIA', 'BELARUS', 'MYANMAR', 'VENEZUELA', 'NICARAGUA',
                'ZIMBABWE', 'ERITREA', 'CENTRAL AFRICAN REPUBLIC'
            ]
            
            geographic_risk = 0.1  # Default low risk
            
            # Check counterparty country
            if counterparty_country:
                country_upper = counterparty_country.upper()
                if any(country in country_upper for country in high_risk_countries):
                    geographic_risk = 0.9
                elif any(country in country_upper for country in medium_risk_countries):
                    geographic_risk = 0.6
            
            # Check counterparty bank for geographic indicators
            if counterparty_bank:
                bank_upper = counterparty_bank.upper()
                if any(country in bank_upper for country in high_risk_countries):
                    geographic_risk = max(geographic_risk, 0.8)
                elif any(country in bank_upper for country in medium_risk_countries):
                    geographic_risk = max(geographic_risk, 0.5)
            
            return geographic_risk
            
        except Exception as e:
            logger.error(f"Error calculating geographic risk: {e}")
            return 0.2
    
    async def calculate_behavioral_risk(self, transaction_data: Dict[str, Any], db: Session) -> float:
        """Calculate risk based on behavioral patterns"""
        try:
            customer_id = transaction_data.get('customer_id')
            current_hour = datetime.now().hour
            current_day = datetime.now().weekday()
            
            behavioral_risk = 0.0
            
            # Time-based risk (unusual hours)
            if current_hour < 6 or current_hour > 22:  # Very early or very late
                behavioral_risk += 0.3
            elif current_hour < 8 or current_hour > 20:  # Early or late
                behavioral_risk += 0.1
            
            # Weekend transaction risk
            if current_day >= 5:  # Saturday = 5, Sunday = 6
                behavioral_risk += 0.2
            
            # Pattern deviation analysis
            customer_patterns = await self.analyze_customer_patterns(customer_id, db)
            
            # Check if current transaction deviates from patterns
            if customer_patterns:
                # Time pattern deviation
                usual_hours = customer_patterns.get('usual_hours', [])
                if usual_hours and current_hour not in usual_hours:
                    behavioral_risk += 0.2
                
                # Day pattern deviation
                usual_days = customer_patterns.get('usual_days', [])
                if usual_days and current_day not in usual_days:
                    behavioral_risk += 0.1
                
                # Channel pattern deviation
                current_channel = transaction_data.get('channel', '')
                usual_channels = customer_patterns.get('usual_channels', [])
                if usual_channels and current_channel not in usual_channels:
                    behavioral_risk += 0.15
            
            # Recent alert history increases risk
            recent_alerts = db.query(Alert).join(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Alert.created_at >= datetime.now() - timedelta(days=30)
                )
            ).count()
            
            if recent_alerts > 0:
                behavioral_risk += min(0.3, recent_alerts * 0.1)
            
            return min(1.0, behavioral_risk)
            
        except Exception as e:
            logger.error(f"Error calculating behavioral risk: {e}")
            return 0.2
    
    async def get_customer_average_amount(self, customer_id: str, db: Session) -> float:
        """Get customer's average transaction amount"""
        try:
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            result = db.query(func.avg(Transaction.base_amount)).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= thirty_days_ago
                )
            ).scalar()
            
            return float(result) if result else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating customer average amount: {e}")
            return 0.0

    async def update_customer_overall_risk_rating(self, customer_id: str, db: Session):
        """Calculate and update a customer's overall risk rating based on recent activity and alerts."""
        try:
            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if not customer:
                logger.warning(f"Customer {customer_id} not found for risk rating update.")
                return

            # Factors for overall customer risk:
            # 1. Average risk score of recent transactions
            # 2. Highest risk score of any active alerts
            # 3. Number of recent alerts

            overall_risk_score = 0.0
            contributing_factors = []

            # Factor 1: Average risk score of recent transactions (e.g., last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_transactions = db.query(Transaction.risk_score).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= thirty_days_ago
                )
            ).all()

            if recent_transactions:
                avg_txn_risk = sum([t.risk_score for t in recent_transactions]) / len(recent_transactions)
                overall_risk_score += avg_txn_risk * 0.6  # Increased weight for average transaction risk
                contributing_factors.append(f"Avg Txn Risk: {avg_txn_risk:.2f}")

            # Factor 2: Highest risk score of any active alerts
            active_alerts = db.query(Alert).join(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Alert.status.in_(['OPEN', 'INVESTIGATING'])
                )
            ).all()

            if active_alerts:
                max_alert_risk = max([alert.risk_score for alert in active_alerts])
                overall_risk_score += max_alert_risk * 0.4  # Increased weight for highest alert risk
                contributing_factors.append(f"Max Alert Risk: {max_alert_risk:.2f}")

            # Factor 3: Number of recent alerts (e.g., last 30 days)
            recent_alerts_count = db.query(Alert).join(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Alert.created_at >= thirty_days_ago
                )
            ).count()

            if recent_alerts_count > 0:
                overall_risk_score += min(0.3, recent_alerts_count * 0.1) # Increased contribution per alert, capped
                contributing_factors.append(f"Recent Alerts: {recent_alerts_count}")

            # Ensure overall_risk_score is within [0, 1] range
            overall_risk_score = max(0.0, min(1.0, overall_risk_score))

            new_risk_category_str = self.get_risk_category(overall_risk_score)
            new_risk_category_enum = RiskRating[new_risk_category_str] # Convert string to Enum member
            
            if customer.risk_rating != new_risk_category_enum:
                logger.info(f"Updating customer {customer_id} risk rating from {customer.risk_rating.value} to {new_risk_category_enum.value} (Score: {overall_risk_score:.2f}). Factors: {', '.join(contributing_factors)}")
                customer.risk_rating = new_risk_category_enum # Update the enum value
                db.add(customer)
                db.commit()
                db.refresh(customer)
            else:
                logger.info(f"Customer {customer_id} risk rating remains {customer.risk_rating.value} (Score: {overall_risk_score:.2f}). Factors: {', '.join(contributing_factors)}")

        except Exception as e:
            logger.error(f"Error updating customer overall risk rating for {customer_id}: {e}")

    async def analyze_customer_patterns(self, customer_id: str, db: Session) -> Dict[str, List]:
        """Analyze customer's transaction patterns"""
        try:
            sixty_days_ago = datetime.now() - timedelta(days=60)
            
            transactions = db.query(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= sixty_days_ago
                )
            ).all()
            
            if len(transactions) < 5:  # Need minimum transactions for pattern analysis
                return {}
            
            # Analyze patterns
            hours = [t.created_at.hour for t in transactions]
            days = [t.created_at.weekday() for t in transactions]
            channels = [t.channel for t in transactions]
            
            # Find most common patterns (appearing in at least 30% of transactions)
            threshold = len(transactions) * 0.3
            
            usual_hours = [h for h in set(hours) if hours.count(h) >= threshold]
            usual_days = [d for d in set(days) if days.count(d) >= threshold]
            usual_channels = [c for c in set(channels) if channels.count(c) >= threshold]
            
            return {
                'usual_hours': usual_hours,
                'usual_days': usual_days,
                'usual_channels': usual_channels
            }
            
        except Exception as e:
            logger.error(f"Error analyzing customer patterns: {e}")
            return {}
    
    def get_risk_category(self, risk_score: float) -> str:
        """Convert risk score to risk category"""
        if risk_score >= 0.7: # Lowered from 0.8
            return "CRITICAL"
        elif risk_score >= 0.50: # Lowered from 0.6
            return "HIGH"
        elif risk_score >= 0.35: # Lowered from 0.4
            return "MEDIUM"
        else:
            return "LOW"
    
    def get_risk_description(self, risk_score: float) -> str:
        """Get risk description based on score"""
        category = self.get_risk_category(risk_score)
        
        descriptions = {
            "CRITICAL": "Critical risk - immediate investigation required",
            "HIGH": "High risk - priority investigation required",
            "MEDIUM": "Medium risk - review recommended",
            "LOW": "Low risk - routine monitoring"
        }
        
        return descriptions.get(category, "Unknown risk level")
