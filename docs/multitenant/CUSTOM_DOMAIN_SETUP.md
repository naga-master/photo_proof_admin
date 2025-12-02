# Custom Domain Multi-Tenancy Setup

This guide explains how to configure custom domain support where studios use their own domains like `winowstudio.com` or `photos.smithwedding.com`.

## How It Works

```
URL: https://winowstudio.com
              ^^^^^^^^^^^^^^^
              └── Entire domain is mapped to a specific studio

The system:
1. Receives request with Host: winowstudio.com
2. Looks up "winowstudio.com" in studio_domains table
3. Finds the associated studio_id
4. Returns that studio's data and branding
```

## Difference from Subdomains

| Aspect | Subdomain | Custom Domain |
|--------|-----------|---------------|
| URL | demo.photoapp.com | winowstudio.com |
| Who owns domain | You (platform) | Studio owner |
| DNS setup | One-time (wildcard) | Per-studio |
| SSL certificate | One wildcard cert | Per-domain or wildcard |
| Database table | `studios.subdomain` | `studio_domains.domain` |

---

## Part 1: What the Studio Owner Provides

When a studio wants to use their custom domain, they need to provide:

### Required Information

```
┌─────────────────────────────────────────────────────────────────┐
│              CUSTOM DOMAIN ONBOARDING FORM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Studio Name:     [ Winow Studio                    ]           │
│  Owner Email:     [ contact@winowstudio.com         ]           │
│  Custom Domain:   [ winowstudio.com                 ]           │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  Domain Type:     ○ Root domain (winowstudio.com)               │
│                   ○ Subdomain (photos.winowstudio.com)          │
│                   ○ Subdomain (gallery.winowstudio.com)         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### What Studio Owner Needs to Do (DNS)

They must configure their domain's DNS to point to your server:

**Option A: A Record (for root domains)**
```
Type: A
Name: @ (or winowstudio.com)
Value: YOUR_SERVER_IP (e.g., 203.0.113.50)
TTL: 3600
```

**Option B: CNAME Record (for subdomains)**
```
Type: CNAME
Name: photos (becomes photos.winowstudio.com)
Value: app.photoapp.com (your platform domain)
TTL: 3600
```

---

## Part 2: Database Configuration

Custom domains are stored in the `studio_domains` table.

### studio_domains Table Schema

```sql
CREATE TABLE studio_domains (
    id VARCHAR(36) PRIMARY KEY,
    studio_id VARCHAR(36) REFERENCES studios(id) ON DELETE CASCADE,
    domain VARCHAR(255) UNIQUE NOT NULL,      -- "winowstudio.com"
    subdomain VARCHAR(100),                   -- Optional, for internal reference
    is_primary BOOLEAN DEFAULT true,          -- Primary domain for this studio
    is_verified BOOLEAN DEFAULT false,        -- DNS verification passed
    verification_token VARCHAR(255),          -- Token for DNS TXT verification
    verification_method VARCHAR(50),          -- 'dns_txt', 'dns_cname', 'file'
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Adding a Custom Domain

**Step 1: Create Studio (if new)**

```sql
INSERT INTO studios (id, name, email, is_active, onboarding_completed)
VALUES (
    'winow-studio-uuid-1234',
    'Winow Studio',
    'contact@winowstudio.com',
    true,
    true
);
```

**Step 2: Add Domain Record**

```sql
INSERT INTO studio_domains (id, studio_id, domain, is_primary, is_verified)
VALUES (
    'domain-uuid-5678',
    'winow-studio-uuid-1234',
    'winowstudio.com',
    true,
    true  -- Set to true after DNS verification
);
```

**Step 3: Create Owner User**

```sql
INSERT INTO users (id, studio_id, name, email, username, password_hash, role, is_active)
VALUES (
    'user-winow-001',
    'winow-studio-uuid-1234',
    'Winow Owner',
    'owner@winowstudio.com',
    'owner@winowstudio.com',
    '$2b$12$...',  -- bcrypt hash
    'studio_owner',
    true
);
```

---

## Part 3: Local Development Testing

To test custom domains locally, use `/etc/hosts`:

### Step 1: Add to /etc/hosts

```bash
sudo nano /etc/hosts

# Add:
127.0.0.1 winowstudio.com
127.0.0.1 photos.smithwedding.com
```

### Step 2: Add to CORS

```bash
# File: photo_proof_api/.env
CORS_ORIGINS=...,http://winowstudio.com:3001,http://photos.smithwedding.com:3001
```

### Step 3: Add Domain to Database

```sql
-- Assuming studio already exists
INSERT INTO studio_domains (id, studio_id, domain, is_primary, is_verified)
VALUES (
    gen_random_uuid()::text,
    'existing-studio-uuid',
    'winowstudio.com',
    true,
    true
);
```

### Step 4: Test

```bash
# Restart backend
# Visit: http://winowstudio.com:3001
```

---

## Part 4: Domain Verification Process

Before enabling a custom domain, verify the studio owner controls it.

### Method 1: DNS TXT Record Verification

**Step 1: Generate verification token**
```python
import secrets
token = secrets.token_urlsafe(32)
# Example: "Xk9mP2nQ4rS6tV8wY0zA3bC5dE7fG9hI"
```

**Step 2: Store in database**
```sql
UPDATE studio_domains 
SET verification_token = 'photoapp-verify=Xk9mP2nQ4rS6tV8wY0zA3bC5dE7fG9hI',
    verification_method = 'dns_txt'
WHERE domain = 'winowstudio.com';
```

**Step 3: Instruct studio owner**
```
Please add this TXT record to your domain's DNS:

Type:  TXT
Name:  _photoapp (or @)
Value: photoapp-verify=Xk9mP2nQ4rS6tV8wY0zA3bC5dE7fG9hI
TTL:   3600

After adding, click "Verify Domain" button.
```

**Step 4: Verify (Python)**
```python
import dns.resolver

def verify_domain(domain: str, expected_token: str) -> bool:
    try:
        # Check TXT records
        answers = dns.resolver.resolve(f'_photoapp.{domain}', 'TXT')
        for rdata in answers:
            if expected_token in str(rdata):
                return True
        return False
    except Exception:
        return False

# Usage
if verify_domain('winowstudio.com', 'photoapp-verify=Xk9m...'):
    # UPDATE studio_domains SET is_verified = true WHERE domain = 'winowstudio.com'
    pass
```

### Method 2: CNAME Verification

```
Please add this CNAME record:

Type:  CNAME  
Name:  _photoapp-verify
Value: verify.photoapp.com
TTL:   3600
```

### Method 3: File Verification

```
Please upload this file to your website:

URL: https://winowstudio.com/.well-known/photoapp-verify.txt
Contents: photoapp-verify=Xk9mP2nQ4rS6tV8wY0zA3bC5dE7fG9hI
```

---

## Part 5: Complete Walkthrough

Let's onboard "Mountain View Photography" with domain `mvphotos.com`.

### Step 1: Studio Owner Provides Info

```
Studio Name:    Mountain View Photography
Owner Name:     Alex Mountain
Owner Email:    alex@mvphotos.com
Custom Domain:  mvphotos.com
```

### Step 2: Create Studio Record

```sql
INSERT INTO studios (id, name, email, brand_color, is_active, onboarding_completed)
VALUES (
    'mv-studio-2024-001',
    'Mountain View Photography',
    'alex@mvphotos.com',
    '#2D5A27',  -- Forest green
    true,
    true
);
```

### Step 3: Create Owner User

```python
# Generate password hash
import bcrypt
password = "mountainview2024"
hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
print(hash)
```

```sql
INSERT INTO users (id, studio_id, name, email, username, password_hash, role, is_active)
VALUES (
    'user-mv-001',
    'mv-studio-2024-001',
    'Alex Mountain',
    'alex@mvphotos.com',
    'alex@mvphotos.com',
    '$2b$12$generatedHashHere',
    'studio_owner',
    true
);
```

### Step 4: Add Domain (Pending Verification)

```sql
INSERT INTO studio_domains (id, studio_id, domain, is_primary, is_verified, verification_token, verification_method)
VALUES (
    'domain-mv-001',
    'mv-studio-2024-001',
    'mvphotos.com',
    true,
    false,  -- Not yet verified
    'photoapp-verify=Xk9mP2nQ4rS6tV8wY0zA3bC5dE7fG9hI',
    'dns_txt'
);
```

### Step 5: Send Instructions to Studio Owner

```
Hi Alex,

To connect mvphotos.com to PhotoProof, please:

1. LOG IN TO YOUR DOMAIN REGISTRAR (GoDaddy, Namecheap, etc.)

2. ADD DNS RECORDS:

   A Record (required):
   ─────────────────────
   Type:  A
   Name:  @ (or mvphotos.com)
   Value: 203.0.113.50    ← Our server IP
   TTL:   3600

   TXT Record (for verification):
   ───────────────────────────────
   Type:  TXT
   Name:  _photoapp
   Value: photoapp-verify=Xk9mP2nQ4rS6tV8wY0zA3bC5dE7fG9hI
   TTL:   3600

3. WAIT 5-30 MINUTES for DNS propagation

4. CLICK "VERIFY DOMAIN" in your PhotoProof dashboard

Your login credentials:
- URL: https://mvphotos.com (after setup)
- Email: alex@mvphotos.com
- Password: mountainview2024

Questions? Reply to this email.
```

### Step 6: Verify and Activate

After studio owner adds DNS records:

```sql
-- After verification passes
UPDATE studio_domains 
SET is_verified = true, 
    verified_at = NOW() 
WHERE domain = 'mvphotos.com';
```

### Step 7: Configure Server (Production)

In nginx:
```nginx
server {
    listen 443 ssl;
    server_name mvphotos.com;
    
    ssl_certificate /etc/letsencrypt/live/mvphotos.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mvphotos.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }
}
```

---

## Tenant Middleware Logic

The middleware checks domains in this order:

```python
# From photo_proof_api/app/middleware/tenant.py

async def detect_studio_from_host(host: str, db: Session):
    clean_host = host.split(':')[0].lower()  # Remove port
    
    # 1. Check custom domain table first
    domain_record = db.query(StudioDomain).filter(
        StudioDomain.domain == clean_host,
        StudioDomain.is_verified == True
    ).first()
    
    if domain_record:
        return domain_record.studio  # Found via custom domain!
    
    # 2. Fall back to subdomain check
    if '.' in clean_host:
        subdomain = clean_host.split('.')[0]
        studio = db.query(Studio).filter(
            Studio.subdomain == subdomain,
            Studio.is_active == True
        ).first()
        
        if studio:
            return studio  # Found via subdomain
    
    return None  # No studio found
```

---

## Troubleshooting

### Problem: "Studio not found for this domain"

**Check 1: Domain in database?**
```sql
SELECT * FROM studio_domains WHERE domain = 'mvphotos.com';
```

**Check 2: Is it verified?**
```sql
SELECT domain, is_verified FROM studio_domains WHERE domain = 'mvphotos.com';
-- If is_verified = false, verification hasn't passed
```

**Check 3: DNS propagated?**
```bash
# Check A record
dig mvphotos.com A

# Check TXT record
dig _photoapp.mvphotos.com TXT
```

### Problem: DNS Not Propagating

**Solution:**
1. Wait longer (can take up to 48 hours)
2. Check with multiple DNS checkers: https://dnschecker.org
3. Flush local DNS: `sudo dscacheutil -flushcache` (macOS)

### Problem: SSL Certificate Errors

**For production, use Let's Encrypt:**
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate for custom domain
sudo certbot --nginx -d mvphotos.com

# Auto-renewal
sudo certbot renew --dry-run
```

### Problem: CORS Errors

**Dynamic CORS (recommended for production):**

```python
# Instead of hardcoding domains, check against database
async def get_allowed_origins():
    db = SessionLocal()
    domains = db.query(StudioDomain).filter(StudioDomain.is_verified == True).all()
    return [f"https://{d.domain}" for d in domains]
```

---

## Quick Reference: Custom Domain Checklist

```
PLATFORM ADMIN:
□ 1. Create studio record in database
□ 2. Create owner user with studio_id
□ 3. Add domain to studio_domains (is_verified=false)
□ 4. Generate verification token
□ 5. Send DNS instructions to studio owner

STUDIO OWNER:
□ 6. Add A record pointing to server IP
□ 7. Add TXT record for verification
□ 8. Wait for DNS propagation

PLATFORM ADMIN:
□ 9. Verify domain ownership
□ 10. Set is_verified=true
□ 11. Configure SSL certificate (production)
□ 12. Add to nginx/server config (production)
□ 13. Test: https://customdomain.com
```

---

## Next Steps

- **[PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)** - Server configuration for production
- **[TENANT_MIDDLEWARE_REFERENCE.md](./TENANT_MIDDLEWARE_REFERENCE.md)** - Technical details
