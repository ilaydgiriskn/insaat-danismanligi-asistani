"""SMTP Client for sending emails via standard library."""

import os
import logging
import smtplib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Optional

from infrastructure.config import get_settings

logger = logging.getLogger(__name__)


def send_report_via_email(report_text: str, recipient_email: str = None, subject: str = "AI Destekli Kullanıcı Analiz Raporu", attachment_path: Optional[str] = None) -> bool:
    """
    Send the analysis report via email using SMTP.
    
    Args:
        report_text: The content of the report (plain text).
        recipient_email: The email address to send the report to. If None, sends to self.
        subject: The subject of the email.
        attachment_path: Optional path to a file to attach (e.g. PDF).
        
    Returns:
        bool: True if sent successfully, False otherwise.
    """
    settings = get_settings()
    
    # Validation
    if not settings.smtp_server or not settings.smtp_email or not settings.smtp_password:
        logger.warning("SMTP configuration missing. Skipping email report.")
        return False
    
    # Determine recipients
    recipients = []
    if recipient_email:
        # If specific recipient provided, use it
        recipients = [recipient_email]
    elif settings.smtp_recipient_emails:
        # Use configured recipients (comma-separated)
        recipients = [email.strip() for email in settings.smtp_recipient_emails.split(',') if email.strip()]
    else:
        # Fallback: send to self
        recipients = [settings.smtp_email]
    
    if not recipients:
        logger.warning("No recipient emails configured. Skipping email report.")
        return False
        
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = settings.smtp_email
        msg['To'] = ', '.join(recipients)  # Multiple recipients in To field
        msg['Subject'] = subject

        
        msg.attach(MIMEText(report_text, 'plain', 'utf-8'))
        
        # Attach file if provided
        if attachment_path and os.path.exists(attachment_path):
            try:
                with open(attachment_path, "rb") as f:
                    attach = MIMEApplication(f.read(), _subtype="pdf")
                    # Extract filename from path
                    filename = Path(attachment_path).name
                    attach.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(attach)
                logger.info(f"Attached file: {attachment_path}")
            except Exception as e:
                logger.error(f"Failed to attach file {attachment_path}: {e}")
        
        # Connect to server
        logger.info(f"Connecting to SMTP server: {settings.smtp_server}:{settings.smtp_port}...")
        
        # Determine strictness based on port
        server = smtplib.SMTP(settings.smtp_server, settings.smtp_port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        
        # Login
        server.login(settings.smtp_email, settings.smtp_password)
        
        # Send to all recipients
        server.send_message(msg, to_addrs=recipients)
        server.quit()
        
        logger.info(f"Email report sent successfully to {', '.join(recipients)}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email report: {str(e)}", exc_info=False) # Log error but don't crash
        return False
