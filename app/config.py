import os
import secrets


class Config:
    SECRET_KEY          = os.getenv("SECRET_KEY", secrets.token_hex(32))
    GROQ_API_KEY        = os.getenv("GROQ_API_KEY")
    GOOGLE_CLIENT_ID    = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    PORT                = int(os.getenv("PORT", 5000))
    DEBUG               = os.getenv("FLASK_DEBUG", "0") == "1"
