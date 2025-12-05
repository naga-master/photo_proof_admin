"""Database connection and models for Admin Dashboard."""
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, BigInteger, JSON, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from config import DATABASE_URL, SQLITE_URL

# Try PostgreSQL first, fall back to SQLite
try:
    engine = create_engine(DATABASE_URL)
    engine.connect()
    print(f"Connected to PostgreSQL")
except Exception as e:
    print(f"PostgreSQL connection failed: {e}")
    print(f"Falling back to SQLite: {SQLITE_URL}")
    engine = create_engine(SQLITE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """Get database session (non-generator version)."""
    return SessionLocal()


# Models (matching main API models exactly)
class Studio(Base):
    """Studio/tenant model - matches main API schema."""
    __tablename__ = "studios"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    
    # Multi-tenant
    subdomain = Column(String(100), unique=True, nullable=True)
    
    # Branding
    logo_url = Column(String(500), nullable=True)
    brand_color = Column(String(7), default="#1e293b")
    typography = Column(String(255), default="System Default (Inter & Cormorant)")
    default_layout_id = Column(String(50), default="layout1")
    default_template_id = Column(String(50), default="modern")
    studio_photo = Column(String(500), nullable=True)
    studio_description = Column(Text, nullable=True)
    custom_css = Column(Text, nullable=True)
    
    # Subscription (legacy)
    subscription_tier = Column(String(50), default="free")
    subscription_status = Column(String(50), default="trial")
    max_projects = Column(Integer, default=5)
    max_storage_gb = Column(Integer, default=10)
    storage_used_bytes = Column(BigInteger, default=0)
    
    # Onboarding
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(String(50), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships (only define what exists in main API)
    domains = relationship("StudioDomain", back_populates="studio")
    users = relationship("User", back_populates="studio")
    features = relationship("StudioFeature", back_populates="studio")


class StudioDomain(Base):
    """Custom domains for studios."""
    __tablename__ = "studio_domains"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    studio_id = Column(String(36), ForeignKey("studios.id", ondelete="CASCADE"), nullable=False)
    domain = Column(String(255), unique=True, nullable=False)
    subdomain = Column(String(100), nullable=True)
    is_primary = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)
    verification_method = Column(String(50), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    studio = relationship("Studio", back_populates="domains")


class User(Base):
    """User model - matches main API schema."""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    studio_id = Column(String(36), ForeignKey("studios.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="client")
    avatar_url = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    studio = relationship("Studio", back_populates="users")


class StudioFeature(Base):
    """Feature overrides for studios."""
    __tablename__ = "studio_features"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    studio_id = Column(String(36), ForeignKey("studios.id", ondelete="CASCADE"), nullable=False)
    feature_key = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    studio = relationship("Studio", back_populates="features")


# Helper functions
def create_studio(db, name: str, subdomain: str, domain: str, owner_email: str, 
                  owner_name: str, password_hash: str, plan: str = "starter",
                  studio_id: str = None) -> Studio:
    """Create a new studio with owner and domain."""
    
    # Create studio
    studio = Studio(
        id=studio_id or str(uuid.uuid4()),
        name=name,
        email=owner_email,
        subdomain=subdomain,
        onboarding_step="pending",
        onboarding_completed=False,
        subscription_tier=plan,
        subscription_status="trial"
    )
    db.add(studio)
    db.flush()
    
    # Create domain
    studio_domain = StudioDomain(
        id=str(uuid.uuid4()),
        studio_id=studio.id,
        domain=domain,
        is_primary=True,
        is_verified=False
    )
    db.add(studio_domain)
    
    # Create owner user
    # Use email as username for simpler login experience
    user = User(
        id=str(uuid.uuid4()),
        studio_id=studio.id,
        name=owner_name,
        email=owner_email,
        username=owner_email,
        password_hash=password_hash,
        role="studio_owner"
    )
    db.add(user)
    
    db.flush()  # Don't commit yet, let caller handle it
    return studio


def get_all_studios(db):
    """Get all studios with related data."""
    return db.query(Studio).options(
        joinedload(Studio.domains),
        joinedload(Studio.users)
    ).all()


def get_studio_by_id(db, studio_id: str):
    """Get studio by ID."""
    return db.query(Studio).options(
        joinedload(Studio.domains),
        joinedload(Studio.users)
    ).filter(Studio.id == studio_id).first()


def get_pending_studios(db):
    """Get studios pending provisioning (not yet completed onboarding)."""
    return db.query(Studio).options(
        joinedload(Studio.domains),
        joinedload(Studio.users)
    ).filter(
        Studio.onboarding_completed == False,
        Studio.onboarding_step == "pending"
    ).all()


def provision_studio(db, studio_id: str):
    """Mark studio as provisioned."""
    studio = db.query(Studio).filter(Studio.id == studio_id).first()
    if studio:
        studio.onboarding_step = "completed"
        studio.onboarding_completed = True
        db.commit()
    return studio


def toggle_feature(db, studio_id: str, feature_key: str, enabled: bool):
    """Toggle a feature for a studio."""
    feature = db.query(StudioFeature).filter(
        StudioFeature.studio_id == studio_id,
        StudioFeature.feature_key == feature_key
    ).first()
    
    if feature:
        feature.enabled = enabled
    else:
        feature = StudioFeature(
            id=str(uuid.uuid4()),
            studio_id=studio_id,
            feature_key=feature_key,
            enabled=enabled
        )
        db.add(feature)
    
    db.commit()
    return feature


def get_studio_features(db, studio_id: str):
    """Get all feature overrides for a studio."""
    return db.query(StudioFeature).filter(StudioFeature.studio_id == studio_id).all()
