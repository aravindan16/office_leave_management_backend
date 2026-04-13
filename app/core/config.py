from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    mongodb_url: str = "mongodb+srv://wizzmod:wizzmod@wizzmod-cluster.gu90dde.mongodb.net/leave_management?retryWrites=true&w=majority"
    jwt_secret: str = "your-super-secret-jwt-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    reset_token_expire_minutes: int = 60
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Office Leave Management"
    smtp_use_tls: bool = True

    @property
    def allowed_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    class Config:
        env_file = ".env"

settings = Settings()
