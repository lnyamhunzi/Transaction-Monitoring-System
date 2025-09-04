"""
Currency Service for exchange rate management and conversion
"""

import logging
import requests
import os
from typing import Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from models import ExchangeRate

logger = logging.getLogger(__name__)

class CurrencyService:
    """Service for currency conversion and exchange rate management"""
    
    def __init__(self):
        self.base_currency = "USD"
        self.api_key = os.getenv("EXCHANGE_RATE_API_KEY", "demo_key")
        self.api_url = "https://api.exchangerate-api.com/v4/latest"
        
        # Supported currencies with their symbols
        self.supported_currencies = {
            'USD': {'symbol': '$', 'name': 'US Dollar'},
            'ZWL': {'symbol': 'Z$', 'name': 'Zimbabwean Dollar'},
            'ZAR': {'symbol': 'R', 'name': 'South African Rand'},
            'EUR': {'symbol': '€', 'name': 'Euro'},
            'GBP': {'symbol': '£', 'name': 'British Pound'},
            'JPY': {'symbol': '¥', 'name': 'Japanese Yen'},
            'CNY': {'symbol': '¥', 'name': 'Chinese Yuan'},
            'AUD': {'symbol': 'A$', 'name': 'Australian Dollar'},
            'CAD': {'symbol': 'C$', 'name': 'Canadian Dollar'},
            'CHF': {'symbol': 'Fr', 'name': 'Swiss Franc'}
        }
        
        # Manual exchange rates for currencies not available via API
        self.manual_rates = {
            'ZWL': 350.0  # ZWL to USD (highly volatile, manual update needed)
        }
    
    async def convert_to_base(self, amount: float, from_currency: str) -> float:
        """Convert amount from given currency to base currency (USD)"""
        try:
            if from_currency == self.base_currency:
                return amount
            
            # Get current exchange rate
            rate = await self.get_exchange_rate(from_currency, self.base_currency)
            
            if rate is None:
                logger.error(f"Could not get exchange rate for {from_currency} to {self.base_currency}")
                return amount  # Return original amount if conversion fails
            
            converted_amount = amount / rate
            
            logger.info(f"Converted {amount} {from_currency} to {converted_amount:.2f} {self.base_currency} at rate {rate}")
            
            return converted_amount
            
        except Exception as e:
            logger.error(f"Error converting currency: {e}")
            return amount
    
    async def convert_amount(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """Convert amount between any two supported currencies"""
        try:
            if from_currency == to_currency:
                return amount
            
            # First convert to base currency, then to target currency
            if from_currency != self.base_currency:
                base_amount = await self.convert_to_base(amount, from_currency)
            else:
                base_amount = amount
            
            if to_currency == self.base_currency:
                return base_amount
            
            # Convert from base to target currency
            rate = await self.get_exchange_rate(self.base_currency, to_currency)
            if rate is None:
                return None
            
            return base_amount * rate
            
        except Exception as e:
            logger.error(f"Error converting between currencies: {e}")
            return None
    
    async def get_exchange_rate(self, from_currency: str, to_currency: str, db: Session = None) -> Optional[float]:
        """Get current exchange rate between two currencies"""
        try:
            # Check manual rates first
            if from_currency in self.manual_rates:
                return self.manual_rates[from_currency]
            
            # Check database for recent rates (less than 1 hour old)
            if db:
                recent_rate = db.query(ExchangeRate).filter(
                    and_(
                        ExchangeRate.from_currency == from_currency,
                        ExchangeRate.to_currency == to_currency,
                        ExchangeRate.rate_date >= datetime.now() - timedelta(hours=1)
                    )
                ).order_by(desc(ExchangeRate.rate_date)).first()
                
                if recent_rate:
                    return recent_rate.rate
            
            # Fetch from API
            rate = await self.fetch_rate_from_api(from_currency, to_currency)
            
            # Save to database if available
            if rate and db:
                await self.save_exchange_rate(from_currency, to_currency, rate, db)
            
            return rate
            
        except Exception as e:
            logger.error(f"Error getting exchange rate: {e}")
            return None
    
    async def fetch_rate_from_api(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Fetch exchange rate from external API"""
        try:
            # Use different approach based on base currency
            if from_currency == self.base_currency:
                url = f"{self.api_url}/{from_currency}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    rates = data.get('rates', {})
                    return rates.get(to_currency)
            else:
                # Get rate via USD
                usd_rate_from = await self.fetch_rate_from_api(from_currency, 'USD')
                usd_rate_to = await self.fetch_rate_from_api('USD', to_currency)
                
                if usd_rate_from and usd_rate_to:
                    return usd_rate_to / usd_rate_from
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching rate from API: {e}")
            return None
    
    async def save_exchange_rate(self, from_currency: str, to_currency: str, rate: float, db: Session):
        """Save exchange rate to database"""
        try:
            exchange_rate = ExchangeRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                rate_date=datetime.now(),
                source="API"
            )
            
            db.add(exchange_rate)
            db.commit()
            
        except Exception as e:
            logger.error(f"Error saving exchange rate: {e}")
            db.rollback()
    
    async def get_supported_currencies(self) -> Dict[str, Dict[str, str]]:
        """Get list of supported currencies"""
        return self.supported_currencies
    
    async def update_manual_rates(self, rates: Dict[str, float]):
        """Update manual exchange rates"""
        try:
            self.manual_rates.update(rates)
            logger.info(f"Updated manual rates: {rates}")
        except Exception as e:
            logger.error(f"Error updating manual rates: {e}")
    
    async def get_currency_symbol(self, currency_code: str) -> str:
        """Get currency symbol"""
        return self.supported_currencies.get(currency_code, {}).get('symbol', currency_code)
    
    async def get_currency_name(self, currency_code: str) -> str:
        """Get currency full name"""
        return self.supported_currencies.get(currency_code, {}).get('name', currency_code)
    
    async def format_amount(self, amount: float, currency: str) -> str:
        """Format amount with currency symbol"""
        try:
            symbol = await self.get_currency_symbol(currency)
            
            # Format with appropriate decimal places
            if currency in ['JPY']:  # Currencies without decimal places
                return f"{symbol}{amount:,.0f}"
            else:
                return f"{symbol}{amount:,.2f}"
                
        except Exception as e:
            logger.error(f"Error formatting amount: {e}")
            return f"{currency} {amount:.2f}"
    
    async def validate_currency(self, currency_code: str) -> bool:
        """Validate if currency is supported"""
        return currency_code in self.supported_currencies
    
    async def get_historical_rates(self, from_currency: str, to_currency: str, days: int, db: Session) -> list:
        """Get historical exchange rates"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            rates = db.query(ExchangeRate).filter(
                and_(
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency,
                    ExchangeRate.rate_date >= start_date
                )
            ).order_by(ExchangeRate.rate_date).all()
            
            return [
                {
                    'date': rate.rate_date.strftime('%Y-%m-%d'),
                    'rate': rate.rate,
                    'source': rate.source
                }
                for rate in rates
            ]
            
        except Exception as e:
            logger.error(f"Error getting historical rates: {e}")
            return []
    
    async def calculate_fx_risk(self, amount: float, from_currency: str, to_currency: str, db: Session) -> Dict:
        """Calculate foreign exchange risk metrics"""
        try:
            # Get historical rates for volatility calculation
            historical_rates = await self.get_historical_rates(from_currency, to_currency, 30, db)
            
            if len(historical_rates) < 10:
                return {'risk_level': 'UNKNOWN', 'volatility': 0.0, 'var_95': 0.0}
            
            # Calculate daily returns
            rates = [r['rate'] for r in historical_rates]
            returns = []
            for i in range(1, len(rates)):
                daily_return = (rates[i] - rates[i-1]) / rates[i-1]
                returns.append(daily_return)
            
            # Calculate volatility (standard deviation of returns)
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5
            
            # Calculate Value at Risk (95% confidence)
            returns_sorted = sorted(returns)
            var_index = int(len(returns_sorted) * 0.05)
            var_95 = abs(returns_sorted[var_index]) if var_index < len(returns_sorted) else 0.0
            
            # Potential loss in base currency
            potential_loss = amount * var_95
            
            # Risk level classification
            if volatility < 0.02:
                risk_level = 'LOW'
            elif volatility < 0.05:
                risk_level = 'MEDIUM'
            else:
                risk_level = 'HIGH'
            
            return {
                'risk_level': risk_level,
                'volatility': volatility,
                'var_95': var_95,
                'potential_loss': potential_loss,
                'currency_pair': f"{from_currency}/{to_currency}"
            }
            
        except Exception as e:
            logger.error(f"Error calculating FX risk: {e}")
            return {'risk_level': 'UNKNOWN', 'volatility': 0.0, 'var_95': 0.0}
