"""Email Sender - Utility to send analysis reports via email with HTML formatting."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import date
import re


def markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to HTML for better email rendering.
    
    Handles:
    - Headers (# ## ###)
    - Bold (**text**)
    - Tables
    - Lists
    - Horizontal rules
    - Emoji preservation
    """
    html = markdown_text
    
    # Escape HTML special chars (but preserve emojis)
    html = html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Headers
    html = re.sub(r'^### (.+)$', r'<h3 style="color:#2563eb;margin:16px 0 8px 0;">\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2 style="color:#1d4ed8;margin:20px 0 10px 0;border-bottom:1px solid #e5e7eb;padding-bottom:5px;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1 style="color:#1e40af;margin:24px 0 12px 0;">\1</h1>', html, flags=re.MULTILINE)
    
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#111827;">\1</strong>', html)
    
    # Horizontal rules
    html = re.sub(r'^---+$', '<hr style="border:none;border-top:1px solid #d1d5db;margin:20px 0;">', html, flags=re.MULTILINE)
    
    # Bullet points with emoji markers (📌 🎯 💰 etc)
    html = re.sub(r'^- \*\*(.+?)\*\*: (.+)$', r'<p style="margin:8px 0 8px 16px;">• <strong>\1</strong>: \2</p>', html, flags=re.MULTILINE)
    html = re.sub(r'^- (.+)$', r'<p style="margin:6px 0 6px 16px;">• \1</p>', html, flags=re.MULTILINE)
    
    # Numbered lists
    html = re.sub(r'^(\d+)\. (.+)$', r'<p style="margin:6px 0 6px 16px;">\1. \2</p>', html, flags=re.MULTILINE)
    
    # Tables (simple conversion)
    def convert_table(match):
        lines = match.group(0).strip().split('\n')
        if len(lines) < 2:
            return match.group(0)
        
        table_html = '<table style="border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;">'
        
        for i, line in enumerate(lines):
            if '---' in line and '|' in line:
                continue  # Skip separator row
            
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if not cells:
                continue
                
            tag = 'th' if i == 0 else 'td'
            style = 'background:#f3f4f6;font-weight:bold;' if i == 0 else ''
            
            row = '<tr>'
            for cell in cells:
                row += f'<{tag} style="border:1px solid #d1d5db;padding:8px 12px;{style}">{cell}</{tag}>'
            row += '</tr>'
            table_html += row
        
        table_html += '</table>'
        return table_html
    
    # Match table blocks
    html = re.sub(r'(\|.+\|[\s\S]*?\|.+\|)', convert_table, html)
    
    # Paragraphs (lines not already tagged)
    lines = html.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('<') and not stripped.startswith('|'):
            result.append(f'<p style="margin:8px 0;line-height:1.6;">{line}</p>')
        else:
            result.append(line)
    html = '\n'.join(result)
    
    return html


def create_html_email(report_content: str, summary: str = "") -> str:
    """Create a beautifully formatted HTML email."""
    subject_date = date.today().strftime("%Y-%m-%d")
    
    summary_html = ""
    if summary:
        summary_html = f"""
        <div style="background:linear-gradient(135deg,#1e3a5f,#2d5a87);color:white;padding:20px;border-radius:8px;margin-bottom:20px;">
            <h2 style="margin:0 0 12px 0;color:white;">📊 30秒速读</h2>
            <div style="font-size:14px;line-height:1.7;">
                {markdown_to_html(summary)}
            </div>
        </div>
        """
    
    report_html = markdown_to_html(report_content)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:800px;margin:0 auto;padding:20px;background:#f9fafb;color:#374151;">
        
        <div style="background:white;padding:30px;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            
            <!-- Header -->
            <div style="text-align:center;margin-bottom:24px;border-bottom:2px solid #1e40af;padding-bottom:16px;">
                <h1 style="margin:0;color:#1e40af;font-size:24px;">🦈 首席策略师深夜备忘录</h1>
                <p style="margin:8px 0 0 0;color:#6b7280;font-size:14px;">{subject_date}</p>
            </div>
            
            <!-- Summary Box -->
            {summary_html}
            
            <!-- Main Report -->
            <div style="font-size:15px;line-height:1.7;">
                {report_html}
            </div>
            
            <!-- Footer -->
            <div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;text-align:center;color:#9ca3af;font-size:12px;">
                <p>Generated by Trump Policy Analysis Agent</p>
            </div>
            
        </div>
        
    </body>
    </html>
    """
    
    return html


class EmailSender:
    """Sends reports via SMTP (Gmail) with HTML formatting."""
    
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.user = os.getenv("EMAIL_USER")
        self.password = os.getenv("EMAIL_PASSWORD")
        self.recipients = os.getenv("EMAIL_TO", "").split(",")
        
    def send_report(self, report_content: str, summary: str = "") -> bool:
        """Send a strategic memo via email with HTML formatting.
        
        Args:
            report_content: The full markdown report
            summary: Brief summary for the email body top
            
        Returns:
            True if sent successfully
        """
        if not self.user or not self.password:
            print("[!] Email credentials missing. Skipping email send.")
            return False
            
        recipients = [r.strip() for r in self.recipients if r.strip()]
        if not recipients:
            recipients = [self.user]  # Fallback to sender
            
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.user
            msg['To'] = ", ".join(recipients)
            subject_date = date.today().strftime("%Y-%m-%d")
            msg['Subject'] = f"🦈 Trump Intelligence Briefing - {subject_date}"
            
            # Plain text fallback
            plain_body = f"DAILY STRATEGIC MEMO - {subject_date}\n\n"
            if summary:
                plain_body += f"--- SUMMARY ---\n{summary}\n\n"
            plain_body += f"--- FULL REPORT ---\n{report_content}"
            
            # HTML version
            html_body = create_html_email(report_content, summary)
            
            # Attach both (HTML preferred)
            msg.attach(MIMEText(plain_body, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            # Connect and send
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.user, self.password)
            
            # Send to all recipients
            for recipient in recipients:
                server.sendmail(self.user, recipient.strip(), msg.as_string())
            
            server.quit()
            
            print(f"[*] Email briefing sent to {', '.join(recipients)}")
            return True
            
        except Exception as e:
            print(f"[!] Failed to send email: {e}")
            return False


def send_daily_report(report_content: str, summary: str = ""):
    """Convenience function to send the report."""
    sender = EmailSender()
    return sender.send_report(report_content, summary)
