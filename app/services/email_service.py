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
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                if self.smtp_use_tls:
                    server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
        except Exception as e:
            # Since this runs in the background, we should log the error
            print(f"Failed to send email: {str(e)}")
            # We don't re-raise here because it's a background task


email_service = EmailService()
