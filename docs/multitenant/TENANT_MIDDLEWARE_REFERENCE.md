# Tenant Middleware Technical Reference

This document provides a deep-dive into how PhotoProof's multi-tenant middleware works.

## Overview

The tenant middleware intercepts every HTTP request, determines which studio (tenant) the request is for, and sets context that downstream handlers use to filter data.

```
Request Flow:
─────────────

Browser Request                Tenant Middleware               Route Handler
     │                              │                              │
     │  Host: demo.photoapp.com     │                              │
     ├─────────────────────────────►│                              │
     │                              │                              │
     │                              │  1. Extract host             │
     │                              │  2. Query database           │
     │                              │  3. Set request.state        │
     │                              │─────────────────────────────►│
     │                              │                              │
     │                              │                              │  4. Filter by studio_id
     │                              │                              │  5. Return data
     │◄─────────────────────────────┼──────────────────────────────│
     │                              │                              │
```

---

## Source Code Location

```
photo_proof_api/
├── app/
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── tenant.py          ← Main tenant detection logic
│   ├── api/
│   │   └── deps.py            ← Dependency injection for tenant
│   └── db/
│       └── models/
│           └── multi_tenant.py ← Studio, StudioDomain models
```

---

## Core Logic: tenant.py

```python
# photo_proof_api/app/middleware/tenant.py

"""Multi-tenant middleware for domain-based studio detection."""

import logging
from typing import Optional
from fastapi import Request
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Studio, StudioDomain

logger = logging.getLogger(__name__)


class TenantContext:
    """Thread-safe tenant context using request state."""
    
    @staticmethod
    def get_studio_id_from_request(request: Request) -> Optional[str]:
        """Get studio_id from request state."""
        return getattr(request.state, 'studio_id', None)
    
    @staticmethod
    def get_studio_from_request(request: Request) -> Optional[Studio]:
        """Get full studio object from request state."""
        return getattr(request.state, 'studio', None)


async def detect_studio_from_host(host: str, db: Session) -> Optional[Studio]:
    """
    Detect studio from HTTP Host header.
    
    Detection Order:
    1. Check studio_domains table (custom domains)
    2. Check studios.subdomain field (subdomains)
    3. Development fallback (localhost → demo studio)
    
    Args:
        host: HTTP Host header value (e.g., "demo.photoapp.com" or "winowstudio.com")
        db: Database session
    
    Returns:
        Studio object if found, None otherwise
    """
    
    # Remove port if present (e.g., "demo.photoapp.local:3001" → "demo.photoapp.local")
    clean_host = host.split(':')[0].lower()
    
    logger.debug(f"Detecting studio from host: {clean_host}")
    
    # ─────────────────────────────────────────────────────────────
    # DEVELOPMENT FALLBACK
    # When accessing via localhost/127.0.0.1, use demo studio
    # ─────────────────────────────────────────────────────────────
    if clean_host in ['localhost', '127.0.0.1']:
        logger.info(f"🔧 Development mode: Using 'demo' studio for localhost")
        studio = db.query(Studio).filter(
            Studio.subdomain == 'demo',
            Studio.is_active == True
        ).first()
        
        if studio:
            logger.info(f"✅ Found demo studio for localhost: {studio.name}")
            return studio
        else:
            logger.warning(f"⚠️  No 'demo' studio found for localhost fallback")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 1: Check custom domain (full domain match)
    # Examples: winowstudio.com, photos.smithwedding.com
    # ─────────────────────────────────────────────────────────────
    domain_record = db.query(StudioDomain).filter(
        StudioDomain.domain == clean_host,
        StudioDomain.is_verified == True
    ).first()
    
    if domain_record:
        logger.info(f"✅ Found studio via custom domain: {domain_record.studio_id}")
        return domain_record.studio
    
    # ─────────────────────────────────────────────────────────────
    # STEP 2: Check subdomain (extract first part before dot)
    # Examples: demo.photoapp.com → subdomain = "demo"
    # ─────────────────────────────────────────────────────────────
    if '.' in clean_host:
        subdomain = clean_host.split('.')[0]
        
        # Check StudioDomain table with subdomain field
        domain_by_subdomain = db.query(StudioDomain).filter(
            StudioDomain.subdomain == subdomain,
            StudioDomain.is_verified == True
        ).first()
        
        if domain_by_subdomain:
            logger.info(f"✅ Found studio via StudioDomain subdomain: {subdomain}")
            return domain_by_subdomain.studio
        
        # Fallback: check studio.subdomain field directly
        studio = db.query(Studio).filter(
            Studio.subdomain == subdomain,
            Studio.is_active == True
        ).first()
        
        if studio:
            logger.info(f"✅ Found studio via Studio.subdomain: {subdomain}")
            return studio
    
    logger.warning(f"⚠️  No studio found for host: {clean_host}")
    return None


async def tenant_middleware(request: Request, call_next):
    """
    Middleware to detect and set current tenant (studio).
    
    This middleware:
    1. Extracts the Host header from the request
    2. Determines which studio the request is for
    3. Sets studio information in request.state
    4. Passes request to the next handler
    """
    
    # ─────────────────────────────────────────────────────────────
    # SKIP PATHS
    # Some routes don't need tenant detection
    # ─────────────────────────────────────────────────────────────
    skip_paths = [
        '/docs',              # Swagger UI
        '/redoc',             # ReDoc
        '/openapi.json',      # OpenAPI schema
        '/api/health',        # Health checks
        '/api/v1/health',
        '/api/onboarding',    # Studio onboarding
        '/api/auth',          # Authentication (login/register)
        '/_',                 # Internal routes
    ]
    
    # Skip OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        logger.debug("Skipping tenant detection for OPTIONS request")
        return await call_next(request)
    
    # Skip certain paths
    path = request.url.path
    if any(path.startswith(skip_path) for skip_path in skip_paths):
        logger.debug(f"Skipping tenant detection for path: {path}")
        return await call_next(request)
    
    # ─────────────────────────────────────────────────────────────
    # DETECT STUDIO FROM HOST
    # ─────────────────────────────────────────────────────────────
    host = request.headers.get('host', '')
    
    if not host:
        logger.debug("No host header present, continuing without tenant")
        request.state.studio_id = None
        request.state.studio = None
        return await call_next(request)
    
    db = SessionLocal()
    try:
        studio = await detect_studio_from_host(host, db)
        
        if studio:
            # Set studio in request state for downstream use
            request.state.studio_id = studio.id
            request.state.studio = studio
            logger.debug(f"📍 Request for studio: {studio.name} ({studio.id})")
            
            # Process request
            response = await call_next(request)
            
            # Add debug headers to response
            response.headers["X-Studio-ID"] = studio.id
            response.headers["X-Studio-Name"] = studio.name
            return response
        else:
            # No studio found
            request.state.studio_id = None
            request.state.studio = None
            logger.debug(f"No studio found for host: {host}")
            return await call_next(request)
            
    except Exception as e:
        logger.error(f"Error in tenant middleware: {e}", exc_info=True)
        request.state.studio_id = None
        request.state.studio = None
        return await call_next(request)
    finally:
        db.close()
```

---

## Dependency Injection: deps.py

Route handlers use these dependencies to access tenant context:

```python
# photo_proof_api/app/api/deps.py

from fastapi import Depends, HTTPException, Request, status
from app.middleware.tenant import TenantContext
from app.db import models

def get_current_studio(request: Request) -> models.Studio:
    """
    Get current studio from request state (set by tenant middleware).
    
    Use this for endpoints that REQUIRE a studio context.
    Raises HTTPException if no studio found.
    """
    studio = TenantContext.get_studio_from_request(request)
    
    if not studio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Studio not found for this domain. Please ensure you're accessing via a valid studio domain."
        )
    
    return studio


def get_optional_studio(request: Request) -> Optional[models.Studio]:
    """
    Get current studio if available (doesn't raise exception).
    
    Use this for endpoints that can work with or without studio context.
    """
    return TenantContext.get_studio_from_request(request)


def require_studio_user(
    user: UserRead = Depends(get_current_user),
    studio: models.Studio = Depends(get_current_studio)
) -> UserRead:
    """
    Ensure user belongs to current studio (from domain).
    
    This enforces:
    1. User is authenticated
    2. User belongs to the studio determined by the domain
    
    Use for studio-specific operations to prevent cross-tenant access.
    """
    if user.studio_id != studio.id:
        logger.warning(
            f"User {user.id} attempted to access studio {studio.id} but belongs to {user.studio_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this studio's resources"
        )
    
    return user
```

---

## Database Schema

### studios Table

```sql
CREATE TABLE studios (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50),
    address TEXT,
    
    -- Multi-tenant identifier
    subdomain VARCHAR(100) UNIQUE,          -- "demo", "alpha", etc.
    
    -- Branding
    logo_url VARCHAR(500),
    brand_color VARCHAR(7) DEFAULT '#1e293b',
    typography VARCHAR(255),
    studio_photo VARCHAR(500),
    studio_description TEXT,
    
    -- Subscription
    subscription_tier VARCHAR(50) DEFAULT 'free',
    subscription_status VARCHAR(50) DEFAULT 'trial',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    onboarding_completed BOOLEAN DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for subdomain lookups
CREATE INDEX ix_studios_subdomain ON studios(subdomain);
CREATE INDEX ix_studios_is_active ON studios(is_active);
```

### studio_domains Table

```sql
CREATE TABLE studio_domains (
    id VARCHAR(36) PRIMARY KEY,
    studio_id VARCHAR(36) REFERENCES studios(id) ON DELETE CASCADE,
    
    -- Domain identification
    domain VARCHAR(255) UNIQUE NOT NULL,    -- "winowstudio.com"
    subdomain VARCHAR(100),                  -- Optional reference
    
    -- Configuration
    is_primary BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    
    -- Verification
    verification_token VARCHAR(255),
    verification_method VARCHAR(50),         -- 'dns_txt', 'dns_cname', 'file'
    verified_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for domain lookups
CREATE INDEX ix_studio_domains_domain ON studio_domains(domain);
CREATE INDEX ix_studio_domains_studio_id ON studio_domains(studio_id);
CREATE INDEX ix_studio_domains_verified ON studio_domains(is_verified);
```

---

## Request Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REQUEST LIFECYCLE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Browser sends request                                                    │
│     ────────────────────                                                     │
│     GET /api/projects HTTP/1.1                                              │
│     Host: demo.photoapp.com                                                 │
│     Authorization: Bearer eyJhbG...                                         │
│                                                                              │
│                          │                                                   │
│                          ▼                                                   │
│                                                                              │
│  2. FastAPI receives request                                                │
│     ────────────────────────                                                │
│     app.main:app                                                            │
│                                                                              │
│                          │                                                   │
│                          ▼                                                   │
│                                                                              │
│  3. Tenant Middleware runs FIRST                                            │
│     ─────────────────────────────                                           │
│     middleware/tenant.py:tenant_middleware()                                │
│                                                                              │
│     a. Extract Host header: "demo.photoapp.com"                             │
│     b. Remove port: "demo.photoapp.com"                                     │
│     c. Query studio_domains WHERE domain = "demo.photoapp.com"              │
│        → Not found                                                          │
│     d. Extract subdomain: "demo"                                            │
│     e. Query studios WHERE subdomain = "demo"                               │
│        → Found! Studio ID: "24cf1e21-..."                                   │
│     f. Set request.state.studio_id = "24cf1e21-..."                        │
│     g. Set request.state.studio = <Studio object>                          │
│                                                                              │
│                          │                                                   │
│                          ▼                                                   │
│                                                                              │
│  4. Auth Middleware runs                                                    │
│     ──────────────────────                                                  │
│     Validates JWT token                                                     │
│     Sets request.state.user                                                 │
│                                                                              │
│                          │                                                   │
│                          ▼                                                   │
│                                                                              │
│  5. Route Handler runs                                                      │
│     ──────────────────────                                                  │
│     routers/projects.py:list_projects()                                     │
│                                                                              │
│     a. Get current_user from dependency                                     │
│     b. Get studio_id from current_user.studio_id (from JWT)                │
│     c. Query: SELECT * FROM projects WHERE studio_id = "24cf1e21-..."      │
│     d. Return filtered results                                              │
│                                                                              │
│                          │                                                   │
│                          ▼                                                   │
│                                                                              │
│  6. Response returned                                                       │
│     ─────────────────────                                                   │
│     HTTP/1.1 200 OK                                                         │
│     X-Studio-ID: 24cf1e21-...                                              │
│     X-Studio-Name: Demo Photography Studio                                  │
│     Content-Type: application/json                                          │
│                                                                              │
│     {"projects": [...], "total": 26}                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Security Considerations

### 1. Data Isolation

Every query MUST filter by `studio_id`:

```python
# CORRECT ✅
query = db.query(Client).filter(Client.studio_id == current_user.studio_id)

# WRONG ❌ - Exposes all clients!
query = db.query(Client)
```

### 2. Cross-Tenant Access Prevention

The `require_studio_user` dependency validates that the logged-in user belongs to the studio determined by the domain:

```python
@router.get("/clients")
def list_clients(
    user: UserRead = Depends(require_studio_user),  # Validates studio match
    db: Session = Depends(get_db)
):
    # user.studio_id is guaranteed to match domain's studio
    return db.query(Client).filter(Client.studio_id == user.studio_id).all()
```

### 3. Domain Verification

Never trust an unverified domain:

```python
# Only use verified domains
domain_record = db.query(StudioDomain).filter(
    StudioDomain.domain == clean_host,
    StudioDomain.is_verified == True  # IMPORTANT!
).first()
```

### 4. SQL Injection Prevention

Always use parameterized queries (SQLAlchemy does this automatically):

```python
# Safe - SQLAlchemy parameterizes
db.query(Studio).filter(Studio.subdomain == user_input).first()

# NEVER do this:
db.execute(f"SELECT * FROM studios WHERE subdomain = '{user_input}'")
```

---

## Testing Tenant Detection

### Unit Test Example

```python
# tests/test_tenant_middleware.py

import pytest
from unittest.mock import MagicMock, patch
from app.middleware.tenant import detect_studio_from_host

@pytest.mark.asyncio
async def test_detect_studio_from_subdomain():
    """Test studio detection via subdomain."""
    mock_db = MagicMock()
    mock_studio = MagicMock()
    mock_studio.id = "test-studio-id"
    mock_studio.name = "Test Studio"
    
    mock_db.query.return_value.filter.return_value.first.return_value = mock_studio
    
    result = await detect_studio_from_host("demo.photoapp.com", mock_db)
    
    assert result == mock_studio
    assert result.name == "Test Studio"


@pytest.mark.asyncio
async def test_detect_studio_from_custom_domain():
    """Test studio detection via custom domain."""
    mock_db = MagicMock()
    mock_domain = MagicMock()
    mock_domain.studio = MagicMock()
    mock_domain.studio.name = "Custom Studio"
    
    # First query (custom domain) returns result
    mock_db.query.return_value.filter.return_value.first.return_value = mock_domain
    
    result = await detect_studio_from_host("winowstudio.com", mock_db)
    
    assert result.name == "Custom Studio"


@pytest.mark.asyncio
async def test_detect_studio_not_found():
    """Test when no studio matches the host."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    result = await detect_studio_from_host("unknown.domain.com", mock_db)
    
    assert result is None
```

### Manual Testing

```bash
# Test with curl
curl -H "Host: demo.photoapp.local" http://localhost:8000/api/studio/current

# Check response headers
curl -I -H "Host: demo.photoapp.local" http://localhost:8000/api/projects/
# Look for: X-Studio-ID and X-Studio-Name headers
```

---

## Debugging

### Enable Debug Logging

```python
# In .env
LOG_LEVEL=DEBUG

# Or in code
import logging
logging.getLogger("app.middleware.tenant").setLevel(logging.DEBUG)
```

### Check Logs

```
# Successful detection:
DEBUG | Detecting studio from host: demo.photoapp.local
INFO  | ✅ Found studio via Studio.subdomain: demo
DEBUG | 📍 Request for studio: Demo Photography Studio (24cf1e21-...)

# Failed detection:
DEBUG | Detecting studio from host: unknown.example.com
WARNING | ⚠️  No studio found for host: unknown.example.com
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Studio not found" | Subdomain not in DB | Add studio with correct subdomain |
| "Studio not found" | is_active = false | `UPDATE studios SET is_active = true` |
| Wrong studio data | User's studio_id mismatch | Check user's studio_id in database |
| CORS error | Domain not in allowed origins | Add to CORS_ORIGINS |

---

## Summary

The tenant middleware provides transparent multi-tenancy by:

1. **Intercepting** every request before it reaches route handlers
2. **Detecting** the studio from the Host header (custom domain or subdomain)
3. **Setting context** in `request.state` for downstream use
4. **Enabling data isolation** through `studio_id` filtering in queries

This architecture allows a single deployment to serve unlimited studios, each with isolated data and custom branding.
