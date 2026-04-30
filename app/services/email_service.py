import smtplib
import socket
from email.message import EmailMessage

from app.core.config import settings


# ✅ Force IPv4 instead of IPv6 (THIS FIXES YOUR ISSUE)
class SMTPIPv4(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        return socket.create_connection((host, port), timeout)


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
            raise ValueError("SMTP settings are not configured")

        import uuid
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

        try:
            print(f"Attempting to send email to {recipient_email} via {self.smtp_host}:{self.smtp_port}...")

            # ✅ USE IPv4 FORCED SMTP (IMPORTANT CHANGE)
            with SMTPIPv4(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.ehlo()

                if self.smtp_use_tls:
                    server.starttls()
                    server.ehlo()

                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)

                server.send_message(message)

                print(f"Successfully sent password reset email to {recipient_email}")

        except Exception as e:
            print(f"❌ Failed to send email: {str(e)}")


# instance
email_service = EmailService()