"""
Quick test to verify email sending works
"""
import sys
sys.path.append('src')

from infrastructure.reporting.smtp_client import send_report_via_email

# Test email sending
print("Testing email send to insaatproje8@gmail.com...")

result = send_report_via_email(
    report_text="TEST: Bu bir test mesajıdır. Email sistemi çalışıyor mu kontrol ediyoruz.",
    recipient_email=None,  # Will use default (insaatproje8@gmail.com)
    subject="TEST: Email Sistemi Kontrolü",
    attachment_path=None
)

if result:
    print("✅ Email başarıyla gönderildi!")
else:
    print("❌ Email gönderilemedi. Loglara bakın.")
