"""Configuration for Admin Dashboard."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory (shared with main API)
env_path = Path(__file__).parent.parent / "photo_proof_api" / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/photo_proof"
)

# For SQLite fallback (development)
SQLITE_URL = os.getenv(
    "SQLITE_URL", 
    f"sqlite:///{Path(__file__).parent.parent / 'photo_proof_api' / 'photo_proof.db'}"
)

# Admin credentials
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Change in production!

# App settings
APP_NAME = "PhotoProof Admin"
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# Email settings (for sending invites)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Paths
BASE_DIR = Path(__file__).parent.parent
UPLOADS_DIR = BASE_DIR / "photo_proof_api" / "uploads"

# Feature definitions
FEATURES = {
    "analytics": {
        "name": "Analytics Dashboard",
        "description": "View detailed analytics and reports",
        "default_plans": ["professional", "enterprise"]
    },
    "ai_tools": {
        "name": "AI Tools",
        "description": "AI-powered editing and enhancements",
        "default_plans": ["enterprise"]
    },
    "contracts": {
        "name": "Contracts",
        "description": "Digital contract management",
        "default_plans": ["professional", "enterprise"]
    },
    "custom_domain": {
        "name": "Custom Domain",
        "description": "Use your own domain",
        "default_plans": ["professional", "enterprise"]
    },
    "white_label": {
        "name": "White Label",
        "description": "Remove PhotoProof branding",
        "default_plans": ["enterprise"]
    },
    "api_access": {
        "name": "API Access",
        "description": "Programmatic access via API",
        "default_plans": ["enterprise"]
    }
}

# Subscription plans
PLANS = {
    "starter": {
        "name": "Starter",
        "price_monthly": 499,
        "price_yearly": 4990,
        "max_projects": 5,
        "max_storage_gb": 5,
        "max_users": 1,
        "max_clients": 50
    },
    "professional": {
        "name": "Professional", 
        "price_monthly": 1499,
        "price_yearly": 14990,
        "max_projects": 50,
        "max_storage_gb": 100,
        "max_users": 5,
        "max_clients": 500
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 4999,
        "price_yearly": 49990,
        "max_projects": -1,  # unlimited
        "max_storage_gb": 500,
        "max_users": -1,  # unlimited
        "max_clients": -1  # unlimited
    }
}
