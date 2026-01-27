import sys
import os
# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.input.email_client import EmailClient
from src.config import config

def test_fetch():
    print("="*60)
    print("TESTING EMAIL INGESTION")
    print(f"Target Sender: politicoplaybook@email.politico.com")
    print(f"IMAP Server: {config.EMAIL_IMAP_SERVER}")
    print(f"User: {config.EMAIL_USER}")
    print("="*60)
    
    client = EmailClient()
    if not client.password:
        print("[!] Error: No password found in env variables!")
        print("Please check your .env file.")
        return

    print("[*] Connecting to IMAP server...")
    # fetch_politico_emails connects, searches, cleans, and saves to DB
    emails = client.fetch_politico_emails()
    
    if emails:
        print(f"\n[*] SUCCESSFULLY FETCHED {len(emails)} EMAILS")
        for i, e in enumerate(emails):
            print(f"\n--- Email {i+1} ---")
            print(f"Subject:  {e['subject']}")
            print(f"Sender:   {e['sender']}")
            print(f"Received: {e['received_at']}")
            print(f"\n[Body Snippet (Cleaned - First 1000 chars)]:")
            print("-" * 40)
            clean_body = e['body_text'][:1000]
            # Replace multiple newlines with single for readability in console
            print(clean_body)
            print("-" * 40)
            if len(e['body_text']) > 1000:
                print(f"... (remaining {len(e['body_text'])-1000} chars withheld)")
    else:
        print("\n[!] No emails found matching criteria: FROM 'politicoplaybook@email.politico.com' since today.")

if __name__ == "__main__":
    test_fetch()
