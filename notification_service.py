"""
Notification Service for AML alerts and system notifications
"""

import logging
import smtplib
import os
from email.mime.text import MIMEText as MimeText
from email.mime.multipart import MIMEMultipart as MimeMultipart
from typing import List, Dict, Any
from datetime import datetime
from jinja2 import Template

from models import Alert, Transaction, Customer

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for handling email notifications and alerts"""
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "aml-system@bank.com")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "password")
        self.from_email = os.getenv("FROM_EMAIL", "aml-system@bank.com")
        
        # Recipient lists by alert type
        self.compliance_team = os.getenv("COMPLIANCE_EMAILS", "compliance@bank.com").split(",")
        self.management_team = os.getenv("MANAGEMENT_EMAILS", "management@bank.com").split(",")
        self.aml_officers = os.getenv("AML_OFFICERS", "aml-officer@bank.com").split(",")
    
    async def send_alert_email(self, alert: Alert) -> bool:
        """Send email notification for high-risk alerts"""
        try:
            # Determine recipients based on alert type and risk score
            recipients = self._get_alert_recipients(alert)
            
            # Generate email content
            subject = f"AML Alert: {alert.alert_type} - Risk Score {alert.risk_score:.2f}"
            body = await self._generate_alert_email_body(alert)
            
            # Send email
            success = await self._send_email(recipients, subject, body)
            
            if success:
                logger.info(f"Alert email sent successfully for alert {alert.id}")
            else:
                logger.error(f"Failed to send alert email for alert {alert.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending alert email: {e}")
            return False
    
    async def send_case_notification(self, case_id: str, action: str, assigned_to: str) -> bool:
        """Send notification for case management activities"""
        try:
            recipients = [assigned_to] + self.compliance_team
            subject = f"AML Case {action}: {case_id}"
            
            body = f"""
            <h2>AML Case Management Notification</h2>
            <p><strong>Case ID:</strong> {case_id}</p>
            <p><strong>Action:</strong> {action}</p>
            <p><strong>Assigned To:</strong> {assigned_to}</p>
            <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Please log into the AML system to review the case details.</p>
            """
            
            return await self._send_email(recipients, subject, body)
            
        except Exception as e:
            logger.error(f"Error sending case notification: {e}")
            return False
    
    async def send_daily_summary(self, stats: Dict[str, Any]) -> bool:
        """Send daily summary report to management"""
        try:
            recipients = self.management_team + self.compliance_team
            subject = f"AML Daily Summary - {datetime.now().strftime('%Y-%m-%d')}"
            
            body = await self._generate_daily_summary_body(stats)
            
            return await self._send_email(recipients, subject, body)
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
            return False
    
    async def send_system_alert(self, message: str, severity: str = "INFO") -> bool:
        """Send system-level alerts to technical team"""
        try:
            tech_team = os.getenv("TECH_EMAILS", "tech@bank.com").split(",")
            subject = f"AML System Alert - {severity}"
            
            body = f"""
            <h2>AML System Alert</h2>
            <p><strong>Severity:</strong> {severity}</p>
            <p><strong>Message:</strong> {message}</p>
            <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            """
            
            return await self._send_email(tech_team, subject, body)
            
        except Exception as e:
            logger.error(f"Error sending system alert: {e}")
            return False
    
    def _get_alert_recipients(self, alert: Alert) -> List[str]:
        """Determine email recipients based on alert characteristics"""
        recipients = []
        
        # Always include AML officers
        recipients.extend(self.aml_officers)
        
        # High-risk alerts go to compliance team
        if alert.risk_score >= 0.8:
            recipients.extend(self.compliance_team)
        
        # Critical alerts (sanctions hits) go to management
        if alert.alert_type == "SANCTIONS_HIT" or alert.risk_score >= 0.9:
            recipients.extend(self.management_team)
        
        # Remove duplicates
        return list(set(recipients))
    
    async def _generate_alert_email_body(self, alert: Alert) -> str:
        """Generate HTML email body for alerts"""
        template_str = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background-color: #dc3545; color: white; padding: 15px; border-radius: 5px; }
                .content { padding: 20px; border: 1px solid #ddd; border-radius: 5px; margin-top: 10px; }
                .risk-high { color: #dc3545; font-weight: bold; }
                .risk-medium { color: #ffc107; font-weight: bold; }
                .risk-low { color: #28a745; font-weight: bold; }
                table { width: 100%; border-collapse: collapse; margin: 15px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f8f9fa; }
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🚨 AML Alert Notification</h2>
            </div>
            
            <div class="content">
                <h3>Alert Details</h3>
                <table>
                    <tr><th>Alert ID</th><td>{{ alert.id }}</td></tr>
                    <tr><th>Alert Type</th><td>{{ alert.alert_type }}</td></tr>
                    <tr><th>Risk Score</th><td class="risk-{{ risk_class }}">{{ alert.risk_score }}</td></tr>
                    <tr><th>Priority</th><td>{{ alert.priority }}</td></tr>
                    <tr><th>Status</th><td>{{ alert.status }}</td></tr>
                    <tr><th>Created</th><td>{{ alert.created_at }}</td></tr>
                </table>
                
                <h3>Transaction Details</h3>
                <table>
                    <tr><th>Transaction ID</th><td>{{ transaction.id }}</td></tr>
                    <tr><th>Customer ID</th><td>{{ transaction.customer_id }}</td></tr>
                    <tr><th>Amount</th><td>{{ transaction.currency }} {{ transaction.amount }}</td></tr>
                    <tr><th>Channel</th><td>{{ transaction.channel }}</td></tr>
                    <tr><th>Type</th><td>{{ transaction.transaction_type }}</td></tr>
                </table>
                
                <h3>Description</h3>
                <p>{{ alert.description }}</p>
                
                <h3>Action Required</h3>
                <p>Please investigate this alert immediately and take appropriate action through the AML system.</p>
                
                <p><strong>Time Sensitive:</strong> This alert requires review within {{ sla_hours }} hours.</p>
            </div>
        </body>
        </html>
        """
        
        template = Template(template_str)
        
        # Determine risk class for styling
        risk_class = "high" if alert.risk_score >= 0.8 else "medium" if alert.risk_score >= 0.5 else "low"
        
        # Calculate SLA hours based on risk score
        sla_hours = 4 if alert.risk_score >= 0.8 else 24 if alert.risk_score >= 0.5 else 72
        
        return template.render(
            alert=alert,
            transaction=alert.transaction,
            risk_class=risk_class,
            sla_hours=sla_hours
        )
    
    async def _generate_daily_summary_body(self, stats: Dict[str, Any]) -> str:
        """Generate daily summary email body"""
        template_str = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background-color: #007bff; color: white; padding: 15px; border-radius: 5px; }
                .content { padding: 20px; border: 1px solid #ddd; border-radius: 5px; margin-top: 10px; }
                .metric { display: inline-block; margin: 10px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }
                .metric h4 { margin: 0; color: #007bff; }
                .metric p { margin: 5px 0; font-size: 24px; font-weight: bold; }
                table { width: 100%; border-collapse: collapse; margin: 15px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f8f9fa; }
            </style>
        </head>
        <body>
            <div class="header">
                <h2>📊 AML Daily Summary Report</h2>
                <p>{{ date }}</p>
            </div>
            
            <div class="content">
                <h3>Key Metrics</h3>
                <div class="metric">
                    <h4>Total Transactions</h4>
                    <p>{{ stats.total_transactions }}</p>
                </div>
                
                <div class="metric">
                    <h4>New Alerts</h4>
                    <p>{{ stats.new_alerts }}</p>
                </div>
                
                <div class="metric">
                    <h4>High Risk Alerts</h4>
                    <p>{{ stats.high_risk_alerts }}</p>
                </div>
                
                <div class="metric">
                    <h4>Cases Opened</h4>
                    <p>{{ stats.cases_opened }}</p>
                </div>
                
                <h3>Alert Breakdown by Type</h3>
                <table>
                    <tr><th>Alert Type</th><th>Count</th><th>Avg Risk Score</th></tr>
                    {% for alert_type in stats.alert_breakdown %}
                    <tr>
                        <td>{{ alert_type.type }}</td>
                        <td>{{ alert_type.count }}</td>
                        <td>{{ alert_type.avg_risk }}</td>
                    </tr>
                    {% endfor %}
                </table>
                
                <h3>Top Risk Customers</h3>
                <table>
                    <tr><th>Customer ID</th><th>Alert Count</th><th>Max Risk Score</th></tr>
                    {% for customer in stats.top_risk_customers %}
                    <tr>
                        <td>{{ customer.customer_id }}</td>
                        <td>{{ customer.alert_count }}</td>
                        <td>{{ customer.max_risk_score }}</td>
                    </tr>
                    {% endfor %}
                </table>
                
                <p><em>This is an automated report generated by the AML Transaction Monitoring System.</em></p>
            </div>
        </body>
        </html>
        """
        
        template = Template(template_str)
        return template.render(
            stats=stats,
            date=datetime.now().strftime('%Y-%m-%d')
        )
    
    async def _send_email(self, recipients: List[str], subject: str, body: str) -> bool:
        """Send email using SMTP"""
        try:
            # Create message
            msg = MimeMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = ', '.join(recipients)
            
            # Add HTML body
            html_part = MimeText(body, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
