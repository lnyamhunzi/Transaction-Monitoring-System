import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
import asyncio


from models import Transaction, TransactionStatus, Alert, Case # Import Case model as well
from aml_controls import AMLControlEngine
from notification_service import NotificationService
from currency_service import CurrencyService # Assuming this is needed
from ml_engine import MLAnomlyEngine
from risk_scoring import RiskScoringEngine
from sanctions_screening import SanctionsScreeningEngine

logger = logging.getLogger(__name__)

# Initialize services (these should ideally be passed or initialized once globally)
aml_engine = AMLControlEngine()
notification_service = NotificationService()
currency_service = CurrencyService()
ml_engine = MLAnomlyEngine()
risk_engine = RiskScoringEngine()
sanctions_engine = SanctionsScreeningEngine()

async def process_transaction_controls(transaction_id: str, transaction_data: dict, db: Session, manager):
    """Background task to process AML controls"""
    logger.info(f"[process_transaction_controls] Starting for transaction_id: {transaction_id}")
    
    try:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            logger.error(f"[process_transaction_controls] Transaction {transaction_id} not found for processing.")
            return

        logger.info(f"[process_transaction_controls] Setting status to PROCESSING for {transaction_id}")
        transaction.status = TransactionStatus.PROCESSING
        db.commit()
        db.refresh(transaction)
        logger.info(f"[process_transaction_controls] Status updated to PROCESSING for {transaction_id}")

        # Run all AML controls
        logger.info(f"[process_transaction_controls] Running AML controls for {transaction_id}")
        control_results = await aml_engine.run_all_controls(transaction_data, db)
        logger.info(f"[process_transaction_controls] AML controls completed for {transaction_id}")
        
        # Run ML anomaly detection
        logger.info(f"[process_transaction_controls] Running ML anomaly detection for {transaction_id}")
        anomaly_score = await ml_engine.detect_anomaly(transaction_data, db)
        transaction.ml_prediction = anomaly_score # Assign ML prediction to transaction
        logger.info(f"[process_transaction_controls] ML anomaly detection completed for {transaction_id}, score: {anomaly_score}")
        
        # Calculate risk score
        logger.info(f"[process_transaction_controls] Calculating risk score for {transaction_id}")
        risk_score = await risk_engine.calculate_risk_score(transaction_data, db)
        transaction.risk_score = risk_score
        logger.info(f"[process_transaction_controls] Risk score calculated for {transaction_id}: {risk_score}")

        # Update customer's overall risk rating after transaction processing
        customer_id = transaction_data.get('customer_id')
        if customer_id:
            await risk_engine.update_customer_overall_risk_rating(customer_id, db)

        # Sanctions screening
        logger.info(f"[process_transaction_controls] Running sanctions screening for {transaction_id}")
        sanctions_result = await sanctions_engine.screen_transaction(transaction_data, db)
        logger.info(f"[process_transaction_controls] Sanctions screening completed for {transaction_id}")
        
        # Create alerts if necessary
        alerts_created = []
        
        for control_name, result in control_results.items():
            if result['triggered']:
                alert_type = f"AML_{control_name}"
                existing_alert = db.query(Alert).filter(
                    and_(Alert.transaction_id == transaction_id, Alert.alert_type == alert_type)
                ).first()

                if existing_alert:
                    # Update existing alert
                    existing_alert.risk_score = result['risk_score']
                    existing_alert.description = result['description']
                    existing_alert.metadata = result['metadata']
                    existing_alert.status = "OPEN" # Or keep current status if not "CLOSED"
                    db.add(existing_alert) # Add to session for update
                    alerts_created.append(existing_alert)
                else:
                    # Create new alert
                    alert = Alert(
                        transaction_id=transaction_id,
                        alert_type=alert_type,
                        risk_score=result['risk_score'],
                        description=result['description'],
                        metadata=result['metadata'],
                        status="OPEN",
                        sla_deadline=datetime.utcnow() + timedelta(hours=24) # Set SLA deadline
                    )
                    db.add(alert)
                    alerts_created.append(alert)
        
        if anomaly_score > 0.7:
            alert_type = "ML_ANOMALY"
            existing_alert = db.query(Alert).filter(
                and_(Alert.transaction_id == transaction_id, Alert.alert_type == alert_type)
            ).first()

            if existing_alert:
                # Update existing alert
                existing_alert.risk_score = anomaly_score
                existing_alert.description = f"ML anomaly detected with score {anomaly_score:.2f}"
                existing_alert.status = "OPEN"
                db.add(existing_alert)
                alerts_created.append(existing_alert)
            else:
                # Create new alert
                alert = Alert(
                    transaction_id=transaction_id,
                    alert_type=alert_type,
                    risk_score=anomaly_score,
                    description=f"ML anomaly detected with score {anomaly_score:.2f}",
                    status="OPEN",
                    sla_deadline=datetime.utcnow() + timedelta(hours=24) # Set SLA deadline
                )
                db.add(alert)
                alerts_created.append(alert)
        
        if sanctions_result['matched']:
            alert_type = "SANCTIONS_HIT"
            existing_alert = db.query(Alert).filter(
                and_(Alert.transaction_id == transaction_id, Alert.alert_type == alert_type)
            ).first()

            if existing_alert:
                # Update existing alert
                existing_alert.risk_score = 1.0
                existing_alert.description = f"Sanctions match: {sanctions_result['details']}"
                existing_alert.status = "OPEN"
                existing_alert.priority = "HIGH"
                db.add(existing_alert)
                alerts_created.append(existing_alert)
            else:
                # Create new alert
                alert = Alert(
                    transaction_id=transaction_id,
                    alert_type="SANCTIONS_HIT",
                    risk_score=1.0,
                    description=f"Sanctions match: {sanctions_result['details']}",
                    status="OPEN",
                    priority="HIGH",
                    sla_deadline=datetime.utcnow() + timedelta(hours=24) # Set SLA deadline
                )
                db.add(alert)
                alerts_created.append(alert)
        
        if alerts_created:
            logger.info(f"[process_transaction_controls] Alerts created for {transaction_id}. Setting status to FLAGGED.")
            transaction.status = TransactionStatus.FLAGGED
        else:
            logger.info(f"[process_transaction_controls] No alerts created for {transaction_id}. Setting status to COMPLETED.")
            transaction.status = TransactionStatus.COMPLETED
        
        db.commit()
        db.refresh(transaction)
        logger.info(f"[process_transaction_controls] Final status updated to {transaction.status} for {transaction_id}")

        # Send real-time update for transaction status (assuming manager is available)
        await manager.broadcast({
            "type": "transaction_status_update",
            "data": {
                "id": str(transaction.id),
                "status": transaction.status.value if hasattr(transaction.status, 'value') else str(transaction.status)
            }
        })
        
        # Send real-time notifications
        for alert in alerts_created:
            await manager.broadcast({
                "type": "alert_generated",
                "data": {
                    "id": alert.id,
                    "alert_type": alert.alert_type,
                    "risk_score": alert.risk_score,
                    "description": alert.description,
                    "customer_id": alert.transaction.customer_id if alert.transaction else None,
                    "timestamp": alert.created_at.isoformat()
                }
            })
            
            # Send email notification for high-risk alerts
            if alert.risk_score > 0.8:
                await notification_service.send_alert_email(alert)
    
    except Exception as e:
        db.rollback()
        logger.error(f"[process_transaction_controls] Critical error processing transaction {transaction_id}: {e}", exc_info=True)
        transaction.status = TransactionStatus.FAILED
        transaction.processing_status = str(e)
        db.commit()
        db.refresh(transaction)
        logger.error(f"[process_transaction_controls] Status updated to FAILED for {transaction_id} due to error.")
        
        # Send real-time update for failed transaction status
        await manager.broadcast({
            "type": "transaction_status_update",
            "data": {
                "id": str(transaction.id),
                "status": transaction.status.value if hasattr(transaction.status, 'value') else str(transaction.status)
            }
        })