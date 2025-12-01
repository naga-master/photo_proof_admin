"""Authentication for Admin Dashboard."""
import bcrypt
from config import ADMIN_USERNAME, ADMIN_PASSWORD


def hash_password(password: str) -> str:
    """Hash a password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def check_admin_password(username: str, password: str) -> bool:
    """Check admin credentials."""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD
