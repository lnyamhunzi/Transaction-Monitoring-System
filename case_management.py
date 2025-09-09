"""
Case Management Service for AML investigations and workflow
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from models import Case, Alert, CaseActivity, CaseStatus
from fastapi import HTTPException
from notification_service import NotificationService

logger = logging.getLogger(__name__)

class CaseManagementService:
    """Service for managing AML investigation cases"""
    
    def __init__(self):
        self.notification_service = NotificationService()
        
        # SLA configurations (in hours)
        self.sla_config = {
            'CRITICAL': 4,
            'HIGH': 24,
            'MEDIUM': 72,
            'LOW': 168  # 1 week
        }
        
        # Case workflow states
        self.valid_transitions = {
            'OPEN': ['INVESTIGATING', 'CLOSED'],
            'INVESTIGATING': ['PENDING_REVIEW', 'CLOSED', 'ESCALATED'],
            'PENDING_REVIEW': ['INVESTIGATING', 'CLOSED', 'ESCALATED'],
            'ESCALATED': ['INVESTIGATING', 'CLOSED'],
            'CLOSED': []  # Final state
        }
    
    async def create_case(self, db: Session, alert_id: str = None, title: str = None, description: str = None, priority: str = 'MEDIUM', assigned_to: str = None, investigation_notes: str = None, target_completion_date: datetime = None) -> Case:
        """Create a new investigation case"""
        logger.info(f"Creating case with alert_id: {alert_id}, title: {title}")
        try:
            # Generate case number
            case_number = await self.generate_case_number(db)
            
            alert = None
            if alert_id:
                alert = db.query(Alert).filter(Alert.id == alert_id).first()

            if alert_id and not alert:
                raise HTTPException(status_code=404, detail=f"Alert with ID {alert_id} not found.")

            if alert:
                # Determine case priority based on alert
                priority = self.determine_case_priority(alert)
                title = title or f"{alert.alert_type} - Customer {alert.transaction.customer_id}"
                description = description or f"Investigation case created from alert: {alert.description}"

            # Ensure assigned_to is not None or empty string
            assigned_to = assigned_to if assigned_to else "Unassigned"
            assigned_to = assigned_to if assigned_to else "Unassigned"

            # Calculate target completion date based on SLA
            sla_hours = self.sla_config.get(priority, 72)
            target_completion = datetime.now() + timedelta(hours=sla_hours)
            
            # Create case
            # Convert empty string alert_id to None to satisfy foreign key constraint
            alert_id_for_db = alert_id if alert_id != "" else None
            case = Case(
                alert_id=alert_id_for_db,
                case_number=case_number,
                title=title,
                description=description,
                status=CaseStatus.OPEN,
                priority=priority,
                assigned_to=assigned_to,
                investigation_notes=investigation_notes,
                target_completion_date=target_completion
            )
            
            db.add(case)
            db.flush()  # Get the case ID
            
            # Create initial activity
            activity_desc = f"Case created."
            if alert:
                activity_desc = f"Case created from alert {alert.id}."
            if investigation_notes:
                activity_desc += f" Initial notes: {investigation_notes}"

            await self.log_case_activity(
                case.id,
                "CASE_CREATED",
                activity_desc,
                assigned_to,
                db
            )
            
            if alert:
                # Update alert status
                db.query(Alert).filter(Alert.id == alert.id).update({
                    'assigned_to': assigned_to,
                    'status': 'INVESTIGATING'
                })
            
            db.commit()
            
            # Send notification
            await self.notification_service.send_case_notification(
                case.id, "CREATED", assigned_to
            )
            
            logger.info(f"Created case {case.case_number}")
            return case
            
        except Exception as e:
            logger.error(f"Error creating case: {e}")
            db.rollback()
            raise
    
    async def update_case(self, case_id: str, updates: Dict[str, Any], updated_by: str, db: Session) -> Optional[Case]:
        """Update case with new information"""
        try:
            case = db.query(Case).filter(Case.id == case_id).first()
            if not case:
                return None
            
            old_status = case.status
            old_assigned_to = case.assigned_to
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(case, key) and value is not None:
                    setattr(case, key, value)
            
            # Log status change
            if 'status' in updates and updates['status'] != old_status:
                await self.validate_status_transition(old_status, updates['status'])
                await self.log_case_activity(
                    case_id,
                    "STATUS_CHANGED",
                    f"Status changed from {old_status} to {updates['status']}",
                    updated_by,
                    db
                )
                
                # Handle status-specific actions
                await self.handle_status_change(case, old_status, updates['status'], db)
            
            # Log assignment change
            if 'assigned_to' in updates and updates['assigned_to'] != old_assigned_to:
                await self.log_case_activity(
                    case_id,
                    "REASSIGNED",
                    f"Case reassigned from {old_assigned_to} to {updates['assigned_to']}",
                    updated_by,
                    db
                )
                
                # Send notification to new assignee
                await self.notification_service.send_case_notification(
                    case_id, "REASSIGNED", updates['assigned_to']
                )
            
            # Log notes update
            if 'investigation_notes' in updates:
                await self.log_case_activity(
                    case_id,
                    "NOTES_UPDATED",
                    "Investigation notes updated",
                    updated_by,
                    db
                )
            
            db.commit()
            
            logger.info(f"Updated case {case.case_number}")
            return case
            
        except Exception as e:
            logger.error(f"Error updating case: {e}")
            db.rollback()
            return None
    
    async def close_case(self, case_id: str, decision: str, rationale: str, decided_by: str, db: Session) -> bool:
        """Close a case with final decision"""
        try:
            case = db.query(Case).filter(Case.id == case_id).first()
            if not case:
                return False
            
            # Update case
            case.status = CaseStatus.CLOSED
            case.decision = decision
            case.decision_rationale = rationale
            case.decided_by = decided_by
            case.decided_at = datetime.now()
            case.actual_completion_date = datetime.now()
            
            # Calculate total investigation time
            investigation_time = (datetime.now() - case.created_at).total_seconds() / 3600
            case.total_hours_spent = investigation_time
            
            # Log closure
            await self.log_case_activity(
                case_id,
                "CASE_CLOSED",
                f"Case closed with decision: {decision}. Rationale: {rationale}",
                decided_by,
                db
            )
            
            # Update related alert
            if case.alert:
                case.alert.status = "CLOSED"
                case.alert.resolution_notes = f"Case closed: {decision}"
                case.alert.reviewed_by = decided_by
                case.alert.reviewed_at = datetime.now()
            
            # Handle SAR filing if required
            if decision == "SAR_FILED":
                await self.handle_sar_filing(case, db)
            
            db.commit()
            
            logger.info(f"Closed case {case.case_number} with decision: {decision}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing case: {e}")
            db.rollback()
            return False
    
    async def escalate_case(self, case_id: str, escalation_reason: str, escalated_by: str, escalated_to: str, db: Session) -> bool:
        """Escalate case to higher authority"""
        try:
            case = db.query(Case).filter(Case.id == case_id).first()
            if not case:
                return False
            
            # Update case
            case.status = CaseStatus.ESCALATED
            case.assigned_to = escalated_to
            case.supervisor = escalated_to
            
            # Log escalation
            await self.log_case_activity(
                case_id,
                "ESCALATED",
                f"Case escalated to {escalated_to}. Reason: {escalation_reason}",
                escalated_by,
                db
            )
            
            # Update related alert
            if case.alert:
                case.alert.escalated_to = escalated_to
                case.alert.escalated_at = datetime.now()
                case.alert.escalation_reason = escalation_reason
            
            db.commit()
            
            # Send escalation notification
            await self.notification_service.send_case_notification(
                case_id, "ESCALATED", escalated_to
            )
            
            logger.info(f"Escalated case {case.case_number} to {escalated_to}")
            return True
            
        except Exception as e:
            logger.error(f"Error escalating case: {e}")
            db.rollback()
            return False
    
    async def get_case_metrics(self, db: Session, days: int = 30) -> Dict[str, Any]:
        """Get case management metrics"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            # Total cases
            total_cases = db.query(Case).filter(Case.created_at >= start_date).count()
            
            # Cases by status
            status_counts = {}
            for status in CaseStatus:
                count = db.query(Case).filter(
                    and_(Case.created_at >= start_date, Case.status == status)
                ).count()
                status_counts[status.value] = count
            
            # Average resolution time
            closed_cases = db.query(Case).filter(
                and_(
                    Case.created_at >= start_date,
                    Case.status == CaseStatus.CLOSED,
                    Case.actual_completion_date.isnot(None)
                )
            ).all()
            
            avg_resolution_hours = 0
            if closed_cases:
                total_hours = sum(case.total_hours_spent or 0 for case in closed_cases)
                avg_resolution_hours = total_hours / len(closed_cases)
            
            # SLA compliance
            sla_breached = 0
            for case in closed_cases:
                if case.actual_completion_date > case.target_completion_date:
                    sla_breached += 1
            
            sla_compliance = 0
            if closed_cases:
                sla_compliance = ((len(closed_cases) - sla_breached) / len(closed_cases)) * 100
            
            # Cases by decision
            decisions = {}
            for case in closed_cases:
                if case.decision:
                    decisions[case.decision] = decisions.get(case.decision, 0) + 1
            
            return {
                'total_cases': total_cases,
                'status_distribution': status_counts,
                'avg_resolution_days': avg_resolution_hours / 24, # Convert hours to days
                'sla_compliance_percentage': sla_compliance,
                'sla_breached_count': sla_breached,
                'decision_distribution': decisions,
                'active_cases': total_cases - status_counts.get('CLOSED', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting case metrics: {e}")
            return {}
    
    async def get_overdue_cases(self, db: Session) -> List[Case]:
        """Get cases that are past their SLA deadline"""
        try:
            now = datetime.now()
            
            overdue_cases = db.query(Case).filter(
                and_(
                    Case.target_completion_date < now,
                    Case.status != CaseStatus.CLOSED
                )
            ).order_by(Case.target_completion_date).all()
            
            return overdue_cases
            
        except Exception as e:
            logger.error(f"Error getting overdue cases: {e}")
            return []
    
    async def generate_case_number(self, db: Session) -> str:
        """Generate unique case number"""
        try:
            # Format: AML-YYYY-NNNN
            year = datetime.now().year
            
            # Get last case number for this year
            last_case = db.query(Case).filter(
                Case.case_number.like(f'AML-{year}-%')
            ).order_by(desc(Case.case_number)).first()
            
            if last_case:
                # Extract sequence number
                last_seq = int(last_case.case_number.split('-')[-1])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            
            return f"AML-{year}-{new_seq:04d}"
            
        except Exception as e:
            logger.error(f"Error generating case number: {e}")
            return f"AML-{datetime.now().year}-{datetime.now().microsecond:04d}"
    
    def determine_case_priority(self, alert: Alert) -> str:
        """Determine case priority based on alert characteristics"""
        if alert.alert_type == "SANCTIONS_HIT":
            return "CRITICAL"
        elif alert.risk_score >= 0.9:
            return "CRITICAL"
        elif alert.risk_score >= 0.7:
            return "HIGH"
        elif alert.risk_score >= 0.5:
            return "MEDIUM"
        else:
            return "LOW"
    
    async def validate_status_transition(self, from_status: str, to_status: str):
        """Validate if status transition is allowed"""
        valid_transitions = self.valid_transitions.get(from_status, [])
        if to_status not in valid_transitions:
            raise ValueError(f"Invalid status transition from {from_status} to {to_status}")
    
    async def handle_status_change(self, case: Case, old_status: str, new_status: str, db: Session):
        """Handle status-specific actions"""
        if new_status == "INVESTIGATING":
            # Reset SLA deadline if case is reopened
            if old_status == "PENDING_REVIEW":
                sla_hours = self.sla_config.get(case.priority, 72)
                case.target_completion_date = datetime.now() + timedelta(hours=sla_hours)
        
        elif new_status == "ESCALATED":
            # Extend SLA for escalated cases
            case.target_completion_date = datetime.now() + timedelta(hours=48)
    
    async def log_case_activity(self, case_id: str, activity_type: str, description: str, performed_by: str, db: Session):
        """Log case activity for audit trail"""
        try:
            activity = CaseActivity(
                case_id=case_id,
                activity_type=activity_type,
                description=description,
                performed_by=performed_by
            )
            
            db.add(activity)
            
        except Exception as e:
            logger.error(f"Error logging case activity: {e}")
    
    async def handle_sar_filing(self, case: Case, db: Session):
        """Handle Suspicious Activity Report filing"""
        try:
            # Generate SAR reference
            sar_reference = f"SAR-{datetime.now().strftime('%Y%m%d')}-{case.case_number}"
            
            # Update case
            case.sar_filed = True
            case.sar_reference = sar_reference
            case.sar_filed_date = datetime.now()
            
            # Log SAR filing
            await self.log_case_activity(
                case.id,
                "SAR_FILED",
                f"SAR filed with reference: {sar_reference}",
                case.decided_by,
                db
            )
            
            logger.info(f"SAR filed for case {case.case_number} with reference {sar_reference}")
            
        except Exception as e:
            logger.error(f"Error handling SAR filing: {e}")
