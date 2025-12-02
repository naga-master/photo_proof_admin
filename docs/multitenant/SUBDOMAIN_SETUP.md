# Subdomain-Based Multi-Tenancy Setup

This guide explains how to configure subdomain-based multi-tenancy where each studio gets a subdomain like `demo.photoapp.local`.

## How It Works

```
URL: https://demo.photoapp.local:3001
              ^^^^
              └── This "demo" subdomain identifies the studio

The system:
1. Extracts "demo" from the Host header
2. Looks up studio with subdomain="demo" in database
3. Returns that studio's data and branding
```

## Prerequisites

- PostgreSQL database running
- Backend API running (port 8000)
- Frontend running (port 3001)
- Admin access to modify `/etc/hosts` (local development)

---

## Part 1: Local Development Setup

### Step 1: Configure /etc/hosts

The `/etc/hosts` file maps domain names to IP addresses locally (bypassing DNS).

```bash
# Open hosts file (requires sudo)
sudo nano /etc/hosts

# Add these lines at the end:
127.0.0.1 demo.photoapp.local
127.0.0.1 alpha.photoapp.local
127.0.0.1 beta.photoapp.local
127.0.0.1 mystudio.photoapp.local

# Save and exit (Ctrl+X, Y, Enter)
```

**What this does:**
- When you visit `demo.photoapp.local` in your browser
- Your computer resolves it to `127.0.0.1` (localhost)
- The request goes to your local server with `Host: demo.photoapp.local`

**Verify it works:**
```bash
ping demo.photoapp.local
# Should show: PING demo.photoapp.local (127.0.0.1)
```

### Step 2: Configure CORS

The backend must allow requests from each subdomain. Edit `.env`:

```bash
# File: photo_proof_api/.env

# Add each subdomain to CORS_ORIGINS (comma-separated, no spaces)
CORS_ORIGINS=http://localhost:3001,http://localhost:5173,http://demo.photoapp.local:3001,http://alpha.photoapp.local:3001,http://beta.photoapp.local:3001,http://mystudio.photoapp.local:3001
```

**Important:** Restart the backend after changing `.env`:
```bash
# Stop the backend (Ctrl+C) and restart
cd photo_proof_api
source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Create Studio in Database

Each subdomain needs a corresponding studio record.

**Option A: Using Admin Dashboard**

1. Go to `http://localhost:8501/signup`
2. Fill in studio details
3. The subdomain is auto-generated from studio name

**Option B: Using SQL**

```sql
-- Connect to database
psql -U photo_proof_user -d photo_proof_production

-- Create a new studio
INSERT INTO studios (id, name, email, subdomain, is_active, onboarding_completed)
VALUES (
    'your-uuid-here',           -- Generate with: SELECT gen_random_uuid();
    'My Studio Name',
    'owner@mystudio.com',
    'mystudio',                 -- This becomes mystudio.photoapp.local
    true,
    true
);
```

**Option C: Using Python Script**

```python
# File: create_studio.py
from app.db.session import SessionLocal
from app.db.models import Studio
import uuid

db = SessionLocal()

studio = Studio(
    id=str(uuid.uuid4()),
    name="My Studio Name",
    email="owner@mystudio.com",
    subdomain="mystudio",
    is_active=True,
    onboarding_completed=True
)
db.add(studio)
db.commit()
print(f"Created studio: {studio.name} ({studio.subdomain})")

db.close()
```

### Step 4: Create Studio Owner User

The studio needs an owner user who can log in:

```sql
-- Create owner user for the studio
INSERT INTO users (id, studio_id, name, email, username, password_hash, role, is_active)
VALUES (
    'user-uuid-here',
    'studio-uuid-from-step-3',
    'Studio Owner',
    'owner@mystudio.com',
    'owner@mystudio.com',
    '$2b$12$...',              -- bcrypt hash of password
    'studio_owner',
    true
);
```

**Generate password hash in Python:**
```python
import bcrypt
password = "your_password"
hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
print(hash)  # Use this in SQL
```

### Step 5: Test the Setup

1. **Start Backend:**
   ```bash
   cd photo_proof_api
   source .venv/bin/activate
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Start Frontend:**
   ```bash
   cd Photo_Proof_v1
   npm run dev
   ```

3. **Access the studio:**
   - Open browser: `http://mystudio.photoapp.local:3001`
   - You should see the login page with studio branding
   - Login with the owner credentials

4. **Check backend logs:**
   ```
   ✅ Found studio via Studio.subdomain: mystudio
   📍 Request for studio: My Studio Name (uuid-here)
   ```

---

## Part 2: Complete Walkthrough - Adding a New Studio

Let's add "Sunrise Photography" with subdomain `sunrise`.

### Step 1: Add to /etc/hosts

```bash
sudo nano /etc/hosts
# Add:
127.0.0.1 sunrise.photoapp.local
```

### Step 2: Add to CORS

Edit `photo_proof_api/.env`:
```
CORS_ORIGINS=...,http://sunrise.photoapp.local:3001
```

### Step 3: Create Studio Record

```sql
INSERT INTO studios (id, name, email, subdomain, brand_color, is_active, onboarding_completed, created_at, updated_at)
VALUES (
    'e5f6a7b8-c9d0-1234-5678-9abcdef01234',
    'Sunrise Photography',
    'hello@sunrisephoto.com',
    'sunrise',
    '#FF6B35',  -- Orange brand color
    true,
    true,
    NOW(),
    NOW()
);
```

### Step 4: Create Owner User

```sql
-- First, generate password hash for "sunrise123"
-- Hash: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4qKzTyRhCYwjKePm

INSERT INTO users (id, studio_id, name, email, username, password_hash, role, is_active, created_at, updated_at)
VALUES (
    'user-sunrise-001',
    'e5f6a7b8-c9d0-1234-5678-9abcdef01234',
    'Sarah Sunrise',
    'sarah@sunrisephoto.com',
    'sarah@sunrisephoto.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4qKzTyRhCYwjKePm',
    'studio_owner',
    true,
    NOW(),
    NOW()
);
```

### Step 5: Restart Backend & Test

```bash
# Restart backend to pick up CORS changes
# Then visit: http://sunrise.photoapp.local:3001
```

---

## Database Schema Reference

### studios table

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(36) | Primary key (UUID) |
| name | VARCHAR(255) | Studio display name |
| email | VARCHAR(255) | Studio email (unique) |
| **subdomain** | VARCHAR(100) | **Subdomain identifier (unique)** |
| brand_color | VARCHAR(7) | Hex color (#RRGGBB) |
| logo_url | VARCHAR(500) | Path to logo image |
| is_active | BOOLEAN | Studio enabled/disabled |
| onboarding_completed | BOOLEAN | Setup finished |

### users table

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(36) | Primary key |
| **studio_id** | VARCHAR(36) | **Links user to studio** |
| email | VARCHAR(255) | User email |
| username | VARCHAR(255) | Login username |
| password_hash | VARCHAR(255) | Bcrypt password |
| role | VARCHAR(50) | 'studio_owner', 'studio_admin', etc. |

---

## Troubleshooting

### Problem: "Studio not found for this domain"

**Causes:**
1. Subdomain not in database
2. Studio `is_active = false`
3. Typo in subdomain

**Fix:**
```sql
-- Check if studio exists
SELECT id, name, subdomain, is_active FROM studios WHERE subdomain = 'mystudio';

-- Activate if needed
UPDATE studios SET is_active = true WHERE subdomain = 'mystudio';
```

### Problem: CORS Error in Browser

**Error:**
```
Access to fetch at 'http://localhost:8000/api/...' from origin 
'http://mystudio.photoapp.local:3001' has been blocked by CORS policy
```

**Fix:**
1. Add domain to `CORS_ORIGINS` in `.env`
2. Restart backend
3. Clear browser cache / hard refresh

### Problem: /etc/hosts Not Working

**Symptoms:**
- `ping mystudio.photoapp.local` fails
- Browser shows "site can't be reached"

**Fixes:**
```bash
# 1. Check file contents
cat /etc/hosts

# 2. Flush DNS cache (macOS)
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder

# 3. Verify no typos (spaces, not tabs)
127.0.0.1 mystudio.photoapp.local
```

### Problem: Login Shows Wrong Studio Data

**Cause:** User's `studio_id` doesn't match the subdomain's studio

**Fix:**
```sql
-- Check user's studio assignment
SELECT u.email, u.studio_id, s.name, s.subdomain 
FROM users u 
JOIN studios s ON u.studio_id = s.id 
WHERE u.email = 'owner@mystudio.com';

-- Update if wrong
UPDATE users SET studio_id = 'correct-studio-uuid' WHERE email = 'owner@mystudio.com';
```

---

## Quick Reference: Add New Studio Checklist

```
□ 1. Add to /etc/hosts:     127.0.0.1 newstudio.photoapp.local
□ 2. Add to CORS_ORIGINS:   http://newstudio.photoapp.local:3001
□ 3. Restart backend
□ 4. Insert studio record (subdomain = 'newstudio')
□ 5. Insert owner user (studio_id = studio's UUID)
□ 6. Test: http://newstudio.photoapp.local:3001
```

---

## Next Steps

- **[CUSTOM_DOMAIN_SETUP.md](./CUSTOM_DOMAIN_SETUP.md)** - For studios with their own domains
- **[PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)** - Deploy to production server
