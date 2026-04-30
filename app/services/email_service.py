import smtplib
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
            raise ValueError("SMTP settings are not configured")

        message = EmailMessage()
        message["Subject"] = "Reset your password"
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

        # Use a timeout for the SMTP connection to prevent hanging
        try:
            print(f"Attempting to send email to {recipient_email} via {self.smtp_host}:{self.smtp_port}...")
            
            # Use smtplib.SMTP as a context manager
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                if self.smtp_use_tls:
                    server.starttls()
                
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(message)
                print(f"Successfully sent password reset email to {recipient_email}")
                
        except OSError as e:
            # Handle [Errno 101] Network is unreachable specifically
            error_msg = str(e)
            if "[Errno 101]" in error_msg or "Network is unreachable" in error_msg:
                print(f"CRITICAL: Network unreachable when sending email to {recipient_email}. "
                      f"This is often an IPv6 issue in Docker. "
                      f"Ensure the container is configured to prefer IPv4.")
            else:
                print(f"Failed to send email to {recipient_email} (Network/Socket Error): {error_msg}")
        except Exception as e:
            # Catch all other exceptions (authentication, SMTP errors, etc.)
            print(f"Failed to send email to {recipient_email} (SMTP/Other Error): {str(e)}")
            # We don't re-raise here because it's a background task


email_service = EmailService()
