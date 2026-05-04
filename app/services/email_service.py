import smtplib
import socket
import uuid
from email.message import EmailMessage
from app.core.config import settings

class EmailService:
    def __init__(self) -> None:
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_from_email = settings.smtp_from_email or settings.smtp_username
        self.smtp_from_name = settings.smtp_from_name
        self.smtp_use_tls = settings.smtp_use_tls

    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_port and self.smtp_from_email)

    def send_password_reset_email(self, recipient_email: str, reset_link: str) -> None:
        if not self.is_configured():
            print("❌ SMTP settings are not configured")
            return

        test_id = str(uuid.uuid4())[:8]
        message = EmailMessage()
        message["Subject"] = f"Reset your password - {test_id}"
        message["From"] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
        message["To"] = recipient_email

        message.set_content(
            "We received a request to reset your password.\n\n"
            f"Open this link to choose a new password:\n{reset_link}\n\n"
            f"This link expires in {settings.reset_token_expire_minutes} minutes.\n"
            "If you did not request this change, you can ignore this email."
        )
        message.add_alternative(
            f"""
            <html>
              <body>
                <p>We received a request to reset your password.</p>
                <p>
                  <a href="{reset_link}">Click here to reset your password</a>
                </p>
                <p>This link expires in {settings.reset_token_expire_minutes} minutes.</p>
                <p>If you did not request this change, you can ignore this email.</p>
              </body>
            </html>
            """,
            subtype="html",
        )

        # Force IPv4 resolution to bypass Docker/Network IPv6 issues
        try:
            print(f"Attempting to send email to {recipient_email} (ID: {test_id})...")
            
            # Resolve hostname to IPv4 specifically
            addr_info = socket.getaddrinfo(self.smtp_host, self.smtp_port, family=socket.AF_INET, type=socket.SOCK_STREAM)
            target_ip = addr_info[0][4][0]
            print(f"Connecting to {self.smtp_host} via IPv4 address {target_ip} on port {self.smtp_port}...")

            # Use SMTP_SSL for port 465, otherwise standard SMTP
            if self.smtp_port == 465:
                smtp_class = smtplib.SMTP_SSL
            else:
                smtp_class = smtplib.SMTP

            with smtp_class(target_ip, self.smtp_port, timeout=15) as server:
                # If using standard SMTP on 587, we need STARTTLS
                if self.smtp_port != 465 and self.smtp_use_tls:
                    try:
                        server.starttls()
                    except Exception as tls_err:
                        print(f"STARTTLS failed: {tls_err}. Retrying with direct hostname...")
                        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server2:
                            server2.starttls()
                            if self.smtp_username and self.smtp_password:
                                server2.login(self.smtp_username, self.smtp_password)
                            server2.send_message(message)
                            print(f"✅ Successfully sent email via hostname fallback")
                            return

                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(message)
                print(f"✅ Successfully sent email to {recipient_email} (ID: {test_id})")
                
        except Exception as e:
            print(f"❌ Failed to send email to {recipient_email}: {str(e)}")
            import traceback
            traceback.print_exc()

email_service = EmailService()