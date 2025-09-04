"""
Machine Learning Engine for Anomaly Detection and Pattern Recognition
"""

import logging
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
import joblib
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

from models import Transaction, Customer, MLModel
from utils import extract_transaction_features

def engineer_anomaly_features(df):
    """
    Create features specifically for anomaly detection
    """
    print("Engineering features for anomaly detection...")
    
    # Make a copy to avoid modifying original
    df_features = df.copy()
    
    # Basic transaction features
    df_features['amount_log'] = np.log1p(df_features['base_amount'])
    df_features['amount_zscore'] = (df_features['base_amount'] - df_features['base_amount'].mean()) / df_features['base_amount'].std()
    
    # Time-based features
    df_features['hour'] = pd.to_datetime(df_features['created_at']).dt.hour
    df_features['day_of_week'] = pd.to_datetime(df_features['created_at']).dt.dayofweek
    df_features['is_weekend'] = (df_features['day_of_week'] >= 5).astype(int)
    df_features['is_night'] = ((df_features['hour'] < 6) | (df_features['hour'] > 22)).astype(int)
    df_features['is_business_hours'] = ((df_features['hour'] >= 9) & (df_features['hour'] <= 17) & (df_features['day_of_week'] < 5)).astype(int)
    
    # Customer behavioral features
    print("Computing customer behavioral features...")
    
    # Customer transaction frequency and amounts
    customer_stats = df_features.groupby('customer_id').agg({
        'base_amount': ['count', 'mean', 'std', 'min', 'max'],
        'created_at': ['min', 'max']
    }).reset_index()
    
    # Flatten column names
    customer_stats.columns = ['customer_id', 'txn_count', 'txn_mean', 'txn_std', 'txn_min', 'txn_max', 'first_txn', 'last_txn']
    customer_stats['txn_std'] = customer_stats['txn_std'].fillna(0)
    customer_stats['customer_tenure_days'] = (customer_stats['last_txn'] - customer_stats['first_txn']).dt.days + 1
    customer_stats['txn_frequency'] = customer_stats['txn_count'] / customer_stats['customer_tenure_days']
    
    # Merge customer stats back
    df_features = df_features.merge(customer_stats[['customer_id', 'txn_count', 'txn_mean', 'txn_std', 'txn_frequency']], on='customer_id', how='left')
    
    # Transaction deviation from customer's normal behavior
    df_features['amount_deviation'] = np.abs(df_features['base_amount'] - df_features['txn_mean']) / (df_features['txn_std'] + 1e-6)
    df_features['amount_percentile'] = df_features.groupby('customer_id')['base_amount'].rank(pct=True)
    
    # Channel and transaction type encoding
    channel_risk = df_features.groupby('channel')['has_alert'].mean().to_dict()
    df_features['channel_risk'] = df_features['channel'].map(channel_risk)
    
    type_risk = df_features.groupby('transaction_type')['has_alert'].mean().to_dict()
    df_features['type_risk'] = df_features['transaction_type'].map(type_risk)
    
    # Cross-border and high-value indicators
    df_features['is_cross_border'] = df_features['is_cross_border'].astype(int)
    df_features['is_high_value'] = df_features['is_high_value'].astype(int)
    
    # PEP and customer risk
    df_features['is_pep'] = df_features['is_pep'].fillna(False).astype(int)
    risk_mapping = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}
    df_features['customer_risk_numeric'] = df_features['risk_rating'].map(risk_mapping).fillna(1)
    
    # Counterparty features
    df_features['has_counterparty'] = (~df_features['counterparty_name'].isna()).astype(int)
    df_features['narrative_length'] = df_features['narrative'].fillna('').str.len()
    
    print(f"Feature engineering completed. Shape: {df_features.shape}")
    return df_features

logger = logging.getLogger(__name__)

class MLAnomlyEngine:
    """Machine Learning Engine for transaction anomaly detection"""
    
    def __init__(self):
        self.anomaly_model = None
        self.risk_model = None
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.feature_columns = []
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize ML models"""
        try:
            await self.load_models()
            if not self.anomaly_model:
                logger.info("No trained models found, initializing with default models")
                await self.create_default_models()
            self.is_initialized = True
            logger.info("ML Engine initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ML Engine: {e}")
            self.is_initialized = False
    
    async def load_models(self):
        """Load trained models from disk"""
        try:
            self.anomaly_model = joblib.load('models/anomaly_detection_model.pkl')
            self.risk_model = joblib.load('models/risk_classification_model.pkl')
            self.scaler = joblib.load('models/anomaly_scaler.pkl')
            self.pca = joblib.load('models/anomaly_pca.pkl')
            with open('models/feature_columns.pkl', 'rb') as f:
                self.feature_columns = pickle.load(f)
            logger.info("ML models loaded successfully")
        except FileNotFoundError:
            logger.info("No existing models found")
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    async def create_default_models(self):
        """Create default models with basic configuration"""
        # Isolation Forest for anomaly detection
        self.anomaly_model = IsolationForest(
            contamination='auto',  # Auto detect contamination level
            random_state=42,
            n_estimators=100
        )
        
        # Random Forest for risk classification
        self.risk_model = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            max_depth=10
        )
        
        # Define basic feature columns
        self.feature_columns = [
            'amount', 'hour_of_day', 'day_of_week', 'is_weekend',
            'customer_age_days', 'transaction_velocity_1h', 'transaction_velocity_24h',
            'amount_percentile_30d', 'frequency_score', 'channel_encoded',
            'transaction_type_encoded', 'currency_encoded'
        ]
    
    async def detect_anomaly(self, transaction_data: Dict[str, Any], db: Session) -> float:
        """Detect anomalies in transaction using ML models"""
        if not self.is_initialized:
            await self.initialize()
        
        if not self.anomaly_model:
            logger.warning("Anomaly model not available, returning 0.0")
            return 0.0
        
        try:
            # Extract features
            features_dict = await self.extract_features(transaction_data, db)
            if not features_dict:
                return 0.0
            
            # Convert to DataFrame for feature engineering
            df = pd.DataFrame([features_dict])
            
            # Select and order features
            X = df[self.feature_columns].values
            
            # Scale and transform features
            X_scaled = self.scaler.transform(X)
            X_pca = self.pca.transform(X_scaled)

            # Get anomaly score
            anomaly_score = self.anomaly_model.decision_function(X_pca)[0]
            
            # Convert to probability (0-1 scale)
            normalized_score = max(0, min(1, (0.5 - anomaly_score)))
            
            return normalized_score
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}")
            return 0.0
    
    async def predict_risk_class(self, transaction_data: Dict[str, Any], db: Session) -> Dict[str, float]:
        """Predict risk class probabilities"""
        if not self.is_initialized:
            await self.initialize()

        if not self.risk_model:
            logger.warning("Risk model not available, returning default probabilities")
            return {'LOW': 0.7, 'MEDIUM': 0.2, 'HIGH': 0.1}
        
        try:
            # Extract features
            features_dict = await self.extract_features(transaction_data, db)
            if not features_dict:
                return {'LOW': 0.7, 'MEDIUM': 0.2, 'HIGH': 0.1}
            
            # Convert to DataFrame for feature engineering
            df = pd.DataFrame([features_dict])
            
            # Select and order features
            X = df[self.feature_columns].values
            
            # Scale and transform features
            X_scaled = self.scaler.transform(X)
            X_pca = self.pca.transform(X_scaled)
            
            # Get risk probabilities
            probabilities = self.risk_model.predict_proba(X_pca)[0]
            
            # Map to risk classes (assuming model was trained with LOW, MEDIUM, HIGH)
            risk_classes = ['LOW', 'MEDIUM', 'HIGH']
            return dict(zip(risk_classes, probabilities))
            
        except Exception as e:
            logger.error(f"Error in risk prediction: {e}")
            return {'LOW': 0.7, 'MEDIUM': 0.2, 'HIGH': 0.1}
    
    async def extract_features(self, transaction_data: Dict[str, Any], db: Session) -> Dict[str, float]:
        """Extract comprehensive features for ML models"""
        try:
            # Create a DataFrame from the transaction data
            df = pd.DataFrame([transaction_data])
            
            # Get customer information
            customer_id = transaction_data.get('customer_id')
            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if customer:
                df['is_pep'] = customer.is_pep
                df['risk_rating'] = customer.risk_rating
            else:
                df['is_pep'] = False
                df['risk_rating'] = 'LOW'

            df['created_at'] = datetime.now()
            df['base_amount'] = transaction_data.get('amount')
            df['has_alert'] = False # This is for prediction, so no alert yet
            df['is_cross_border'] = False # Placeholder
            df['is_high_value'] = False # Placeholder
            df['counterparty_name'] = transaction_data.get('counterparty_name')
            df['narrative'] = transaction_data.get('narrative')

            # Engineer features
            df_features = engineer_anomaly_features(df)
            
            return df_features.iloc[0].to_dict()
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return {}
    
    async def predict_risk_class(self, transaction_data: Dict[str, Any], db: Session) -> Dict[str, float]:
        """Predict risk class probabilities"""
        if not self.is_initialized:
            await self.initialize()

        if not self.risk_model:
            logger.warning("Risk model not available, returning default probabilities")
            return {'LOW': 0.7, 'MEDIUM': 0.2, 'HIGH': 0.1}
        
        try:
            # Extract features
            features_dict = await self.extract_features(transaction_data, db)
            if not features_dict:
                return {'LOW': 0.7, 'MEDIUM': 0.2, 'HIGH': 0.1}
            
            # Convert to DataFrame for feature engineering
            df = pd.DataFrame([features_dict])
            
            # Select and order features
            X = df[self.feature_columns].values
            
            # Scale and transform features
            X_scaled = self.scaler.transform(X)
            X_pca = self.pca.transform(X_scaled)
            
            # Get risk probabilities
            probabilities = self.risk_model.predict_proba(X_pca)[0]
            
            # Map to risk classes (assuming model was trained with LOW, MEDIUM, HIGH)
            risk_classes = ['LOW', 'MEDIUM', 'HIGH']
            return dict(zip(risk_classes, probabilities))
            
        except Exception as e:
            logger.error(f"Error in risk prediction: {e}")
            return {'LOW': 0.7, 'MEDIUM': 0.2, 'HIGH': 0.1}
    
    async def extract_features(self, transaction_data: Dict[str, Any], db: Session) -> Dict[str, float]:
        """Extract comprehensive features for ML models"""
        try:
            # Create a DataFrame from the transaction data
            df = pd.DataFrame([transaction_data])
            
            # Get customer information
            customer_id = transaction_data.get('customer_id')
            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if customer:
                df['is_pep'] = customer.is_pep
                df['risk_rating'] = customer.risk_rating
            else:
                df['is_pep'] = False
                df['risk_rating'] = 'LOW'

            df['created_at'] = datetime.now()
            df['base_amount'] = transaction_data.get('amount')
            df['has_alert'] = False # This is for prediction, so no alert yet
            df['is_cross_border'] = False # Placeholder
            df['is_high_value'] = False # Placeholder
            df['counterparty_name'] = transaction_data.get('counterparty_name')
            df['narrative'] = transaction_data.get('narrative')

            # Engineer features
            df_features = engineer_anomaly_features(df)
            
            return df_features.iloc[0].to_dict()
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return {}
    
    async def calculate_transaction_velocity(self, customer_id: str, hours: int, db: Session) -> float:
        """Calculate transaction velocity (count per hour)"""
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
    
    async def calculate_amount_percentile(self, customer_id: str, amount: float, days: int, db: Session) -> float:
        """Calculate percentile rank of amount in customer's historical transactions"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            historical_amounts = db.query(Transaction.base_amount).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= start_date
                )
            ).all()
            
            if not historical_amounts:
                return 0.5  # Default to median if no history
            
            amounts = [a[0] for a in historical_amounts]
            amounts.sort()
            
            # Calculate percentile rank
            lower_count = sum(1 for a in amounts if a < amount)
            equal_count = sum(1 for a in amounts if a == amount)
            
            percentile = (lower_count + 0.5 * equal_count) / len(amounts)
            return percentile
            
        except Exception as e:
            logger.error(f"Error calculating amount percentile: {e}")
            return 0.5
    
    async def calculate_frequency_score(self, customer_id: str, db: Session) -> float:
        """Calculate frequency score based on recent transaction patterns"""
        try:
            # Count transactions in different time windows
            now = datetime.now()
            
            count_1h = db.query(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= now - timedelta(hours=1)
                )
            ).count()
            
            count_24h = db.query(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= now - timedelta(hours=24)
                )
            ).count()
            
            count_7d = db.query(Transaction).filter(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.created_at >= now - timedelta(days=7)
                )
            ).count()
            
            # Weight recent activity more heavily
            frequency_score = (count_1h * 10) + (count_24h * 2) + (count_7d * 0.5)
            
            return min(frequency_score, 100)  # Cap at 100
            
        except Exception as e:
            logger.error(f"Error calculating frequency score: {e}")
            return 0.0
    
    def prepare_feature_vector(self, features: Dict[str, float]) -> List[float]:
        """Prepare feature vector for model input"""
        try:
            # Ensure all required features are present
            feature_vector = []
            for col in self.feature_columns:
                feature_vector.append(features.get(col, 0.0))
            
            return feature_vector
            
        except Exception as e:
            logger.error(f"Error preparing feature vector: {e}")
            return [0.0] * len(self.feature_columns)
    
    async def train_models(self, db: Session, days_back: int = 90):
        """Train ML models using historical data"""
        try:
            logger.info(f"Starting model training with {days_back} days of data")
            
            # Get training data
            start_date = datetime.now() - timedelta(days=days_back)
            transactions = db.query(Transaction).filter(
                Transaction.created_at >= start_date
            ).all()
            
            if len(transactions) < 1000:
                logger.warning("Insufficient data for training")
                return False
            
            # Prepare training data
            X, y_risk, y_anomaly = await self.prepare_training_data(transactions, db)
            
            if X.empty:
                logger.error("No training data prepared")
                return False
            
            # Split data
            X_train, X_test, y_risk_train, y_risk_test = train_test_split(
                X, y_risk, test_size=0.2, random_state=42
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train anomaly detection model
            self.anomaly_model.fit(X_train_scaled)
            
            # Train risk classification model
            self.risk_model.fit(X_train_scaled, y_risk_train)
            
            # Evaluate models
            risk_predictions = self.risk_model.predict(X_test_scaled)
            logger.info(f"Risk Classification Report:\n{classification_report(y_risk_test, risk_predictions)}")
            
            # Save models
            await self.save_models()
            
            logger.info("Model training completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error training models: {e}")
            return False
    
    async def prepare_training_data(self, transactions: List[Transaction], db: Session):
        """Prepare training data from historical transactions"""
        try:
            training_data = []
            
            for transaction in transactions:
                # Extract features for each transaction
                transaction_data = {
                    'customer_id': transaction.customer_id,
                    'base_amount': transaction.base_amount,
                    'channel': transaction.channel,
                    'transaction_type': transaction.transaction_type,
                    'currency': transaction.currency
                }
                
                features = await self.extract_features(transaction_data, db)
                
                # Create risk label based on alerts
                risk_label = 'LOW'
                if transaction.alerts:
                    max_risk_score = max(alert.risk_score for alert in transaction.alerts)
                    if max_risk_score > 0.8:
                        risk_label = 'HIGH'
                    elif max_risk_score > 0.5:
                        risk_label = 'MEDIUM'
                
                # Create anomaly label (simplified)
                anomaly_label = 1 if risk_label == 'HIGH' else 0
                
                features['risk_label'] = risk_label
                features['anomaly_label'] = anomaly_label
                training_data.append(features)
            
            df = pd.DataFrame(training_data)
            
            # Separate features and labels
            feature_cols = [col for col in df.columns if col not in ['risk_label', 'anomaly_label']]
            X = df[feature_cols]
            y_risk = df['risk_label']
            y_anomaly = df['anomaly_label']
            
            return X, y_risk, y_anomaly
            
        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return pd.DataFrame(), [], []
    
    async def save_models(self):
        """Save trained models to disk"""
        try:
            import os
            os.makedirs('models', exist_ok=True)
            
            joblib.dump(self.anomaly_model, 'models/anomaly_detection_model.pkl')
            joblib.dump(self.risk_model, 'models/risk_classification_model.pkl')
            joblib.dump(self.scaler, 'models/feature_scaler.pkl')
            
            with open('models/feature_columns.pkl', 'wb') as f:
                pickle.dump(self.feature_columns, f)
            
            logger.info("Models saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving models: {e}")
