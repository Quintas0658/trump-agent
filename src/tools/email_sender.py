"""Email Sender - Utility to send analysis reports via email."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import date

from src.config import config

class EmailSender:
    """Sends reports via SMTP (Gmail)."""
    
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.user = os.getenv("EMAIL_USER")
        self.password = os.getenv("EMAIL_PASSWORD")
        
    def send_report(self, report_content: str, summary: str = "") -> bool:
        """Send a strategic memo via email.
        
        Args:
            report_content: The full markdown report
            summary: Brief summary for the email body top
            
        Returns:
            True if sent successfully
        """
        if not self.user or not self.password:
            print("[!] Email credentials missing. Skipping email send.")
            return False
            
        try:
            msg = MIMEMultipart()
            msg['From'] = self.user
            msg['To'] = self.user  # Send to self by default
            subject_date = date.today().strftime("%Y-%m-%d")
            msg['Subject'] = f"🦈 Trump Intelligence Briefing - {subject_date}"
            
            # Create email body
            body = f"DAILY STRATEGIC MEMO - {subject_date}\n\n"
            if summary:
                body += f"--- 30-SECOND SUMMARY ---\n{summary}\n\n"
            
            body += f"--- FULL REPORT ---\n{report_content}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect and send
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.user, self.password)
            server.send_message(msg)
            server.quit()
            
            print(f"[*] Email briefing sent to {self.user}")
            return True
            
        except Exception as e:
            print(f"[!] Failed to send email: {e}")
            return False

def send_daily_report(report_content: str, summary: str = ""):
    """Convenience function to send the report."""
    sender = EmailSender()
    return sender.send_report(report_content, summary)
