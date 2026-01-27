import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
import json
from bs4 import BeautifulSoup
from src.config import config
from supabase import create_client, Client

class EmailClient:
    def __init__(self):
        self.imap_server = config.EMAIL_IMAP_SERVER
        self.username = config.EMAIL_USER
        self.password = config.EMAIL_PASSWORD
        self.folder = config.EMAIL_FOLDER
        
        self.supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

    def connect(self):
        """Connect to IMAP server."""
        if not self.username or not self.password:
            print("[!] Email credentials not set. Skipping email connection.")
            return None
        
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.username, self.password)
            return mail
        except Exception as e:
            print(f"[!] IMAP Connection failed: {e}")
            return None

    def fetch_politico_emails(self, days_back=2) -> list[dict]:
        """Fetch emails from Politico in the last N days."""
        mail = self.connect()
        if not mail:
            return []

        try:
            mail.select(self.folder)
            
            # Search for emails from specific sender
            # SINCE date format: 01-Jan-2026
            since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            target_sender = "politicoplaybook@email.politico.com"
            
            print(f"[*] Searching emails since: {since_date}")
            
            # Using specific sender in search
            status, messages = mail.search(None, f'(FROM "{target_sender}" SINCE "{since_date}")')
            
            email_ids = messages[0].split()
            print(f"[*] Found {len(email_ids)} emails from Politico today.")
            
            processed_emails = []

            for e_id in email_ids[-5:]: # Limit to last 5
                status, msg_data = mail.fetch(e_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        
                        sender = msg.get("From")
                        
                        # Extract Message-ID for deduplication
                        message_id = msg.get("Message-ID", "").strip()
                        
                        # Parse accurate date
                        date_str = msg.get("Date")
                        try:
                            if date_str:
                                received_dt = parsedate_to_datetime(date_str)
                            else:
                                received_dt = datetime.now()
                        except:
                            received_dt = datetime.now()
                        
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                if content_type == "text/plain":
                                    body += part.get_payload(decode=True).decode()
                                elif content_type == "text/html":
                                    html_content = part.get_payload(decode=True).decode()
                                    soup = BeautifulSoup(html_content, "html.parser")
                                    body += soup.get_text()
                        else:
                            body = msg.get_payload(decode=True).decode()
                            
                        email_data = {
                            "sender": sender,
                            "subject": subject,
                            "received_at": received_dt.isoformat(),
                            "body_text": body[:10000], # Trucate huge emails
                            "summary": None,
                            "metadata": {
                                "message_id": message_id
                            }
                        }
                        
                        # Save to Supabase
                        self._save_email(email_data)
                        processed_emails.append(email_data)
            
            mail.close()
            mail.logout()
            return processed_emails

        except Exception as e:
            print(f"[!] Email fetch failed: {e}")
            return []

    def _save_email(self, data: dict):
        """Save parsed email to Supabase (Idempotent)."""
        try:
            # Check for duplicates using Message-ID in metadata
            msg_id = data.get("metadata", {}).get("message_id")
            
            if msg_id:
                # Query JSONB column using arrow operator ->> for text comparison
                try:
                    existing = self.supabase.table("email_sources") \
                        .select("id") \
                        .eq("metadata->>message_id", msg_id) \
                        .execute()
                    
                    if existing.data:
                        print(f"[*] Skipping duplicate email: {data['subject']}")
                        return
                except Exception as check_err:
                    print(f"[!] Warning: Deduplication check failed, proceeding to insert: {check_err}")

            self.supabase.table("email_sources").insert(data).execute()
            print(f"[*] Saved email: {data['subject']}")
        except Exception as e:
            print(f"[!] Failed to save email to DB: {e}")
