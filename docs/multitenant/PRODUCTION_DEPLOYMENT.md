# Production Deployment for Multi-Tenant PhotoProof

This guide covers deploying PhotoProof to production with full multi-tenant support.

## Architecture Overview

```
                        PRODUCTION ARCHITECTURE
                        
    ┌─────────────────────────────────────────────────────────────┐
    │                         INTERNET                             │
    │                                                              │
    │  demo.photoapp.com    alpha.photoapp.com   winowstudio.com  │
    │         │                    │                    │          │
    └─────────┼────────────────────┼────────────────────┼──────────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │      LOAD BALANCER       │
                    │   (Optional: AWS ALB,    │
                    │    Cloudflare, etc.)     │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │         NGINX            │
                    │    (Reverse Proxy)       │
                    │                          │
                    │  • SSL Termination       │
                    │  • Static file serving   │
                    │  • Proxy to apps         │
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │   Frontend      │ │   Backend API   │ │  Admin Panel    │
    │   (React)       │ │   (FastAPI)     │ │   (Flask)       │
    │   Port 3001     │ │   Port 8000     │ │   Port 8501     │
    └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │       PostgreSQL         │
                    │        Database          │
                    └──────────────────────────┘
```

---

## Part 1: Server Setup

### Recommended Server Specs

| Tier | Studios | RAM | CPU | Storage |
|------|---------|-----|-----|---------|
| Starter | 1-10 | 2GB | 1 vCPU | 50GB SSD |
| Growth | 10-50 | 4GB | 2 vCPU | 100GB SSD |
| Scale | 50-200 | 8GB | 4 vCPU | 250GB SSD |

### Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    nginx \
    postgresql \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    certbot \
    python3-certbot-nginx \
    git \
    supervisor

# Create app user
sudo useradd -m -s /bin/bash photoapp
sudo usermod -aG sudo photoapp
```

---

## Part 2: Nginx Configuration

### Main Nginx Config

```nginx
# /etc/nginx/nginx.conf

user www-data;
worker_processes auto;
pid /run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;  # For photo uploads

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Gzip
    gzip on;
    gzip_types text/plain application/json application/javascript text/css;

    # Include site configs
    include /etc/nginx/sites-enabled/*;
}
```

### Subdomain Configuration (Wildcard)

```nginx
# /etc/nginx/sites-available/photoapp-subdomains

# Catch-all for *.photoapp.com subdomains
server {
    listen 80;
    server_name *.photoapp.com photoapp.com;
    
    # Redirect to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name *.photoapp.com photoapp.com;

    # Wildcard SSL certificate
    ssl_certificate /etc/letsencrypt/live/photoapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/photoapp.com/privkey.pem;
    
    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Frontend (React app)
    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static uploads
    location /uploads {
        alias /var/www/photoapp/uploads;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### Custom Domain Configuration Template

```nginx
# /etc/nginx/sites-available/custom-domain-template
# Copy and modify for each custom domain

server {
    listen 80;
    server_name winowstudio.com www.winowstudio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name winowstudio.com www.winowstudio.com;

    # Domain-specific SSL (from Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/winowstudio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/winowstudio.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;

    # Same proxy config as subdomains
    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /uploads {
        alias /var/www/photoapp/uploads;
        expires 30d;
    }
}
```

### Enable Sites

```bash
# Enable subdomain config
sudo ln -s /etc/nginx/sites-available/photoapp-subdomains /etc/nginx/sites-enabled/

# For each custom domain
sudo ln -s /etc/nginx/sites-available/winowstudio.com /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

---

## Part 3: SSL Certificates

### Wildcard Certificate for Subdomains

```bash
# Install certbot with DNS plugin (example: Cloudflare)
sudo apt install python3-certbot-dns-cloudflare

# Create Cloudflare credentials file
sudo mkdir -p /etc/letsencrypt
sudo nano /etc/letsencrypt/cloudflare.ini
# Add:
# dns_cloudflare_api_token = YOUR_CLOUDFLARE_API_TOKEN

sudo chmod 600 /etc/letsencrypt/cloudflare.ini

# Get wildcard certificate
sudo certbot certonly \
    --dns-cloudflare \
    --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
    -d "photoapp.com" \
    -d "*.photoapp.com"
```

### Certificate for Custom Domain

```bash
# For each custom domain
sudo certbot --nginx -d winowstudio.com -d www.winowstudio.com

# Verify auto-renewal
sudo certbot renew --dry-run
```

### Auto-Renewal Cron

```bash
# Add to crontab
sudo crontab -e

# Add line:
0 3 * * * /usr/bin/certbot renew --quiet --post-hook "systemctl reload nginx"
```

---

## Part 4: Application Deployment

### Backend API Setup

```bash
# Clone repository
cd /var/www
sudo git clone https://github.com/your-repo/photo_proof_api.git
sudo chown -R photoapp:photoapp photo_proof_api

# Setup virtual environment
cd photo_proof_api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create production .env
sudo nano .env
```

**Production .env:**
```bash
# Database
DATABASE_URL=postgresql://photo_proof_user:STRONG_PASSWORD@localhost/photo_proof_production

# Security
SECRET_KEY=GENERATE_A_LONG_RANDOM_STRING_HERE
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS - Dynamic handling recommended (see below)
CORS_ORIGINS=https://photoapp.com,https://*.photoapp.com

# Environment
ENVIRONMENT=production
DEBUG=false

# Uploads
UPLOAD_DIR=/var/www/photoapp/uploads
MAX_UPLOAD_SIZE=52428800

# Cookies
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
COOKIE_DOMAIN=.photoapp.com
```

### Dynamic CORS for Custom Domains

Modify `photo_proof_api/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import SessionLocal
from app.db.models import StudioDomain

def get_allowed_origins():
    """Fetch allowed origins from database + config."""
    # Base origins from config
    origins = set(settings.cors_origins)
    
    # Add verified custom domains
    db = SessionLocal()
    try:
        domains = db.query(StudioDomain).filter(
            StudioDomain.is_verified == True
        ).all()
        for d in domains:
            origins.add(f"https://{d.domain}")
            origins.add(f"http://{d.domain}")  # For development
    finally:
        db.close()
    
    return list(origins)

# In app setup:
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Frontend Build

```bash
cd /var/www/Photo_Proof_v1

# Install dependencies
npm ci

# Build for production
npm run build

# The built files go to ./dist
```

### Supervisor Configuration

```ini
# /etc/supervisor/conf.d/photoapp.conf

[program:photoapp-api]
command=/var/www/photo_proof_api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
directory=/var/www/photo_proof_api
user=photoapp
autostart=true
autorestart=true
stderr_logfile=/var/log/photoapp/api-error.log
stdout_logfile=/var/log/photoapp/api-access.log
environment=PYTHONPATH="/var/www/photo_proof_api"

[program:photoapp-frontend]
command=/usr/bin/npx serve -s dist -l 3001
directory=/var/www/Photo_Proof_v1
user=photoapp
autostart=true
autorestart=true
stderr_logfile=/var/log/photoapp/frontend-error.log
stdout_logfile=/var/log/photoapp/frontend-access.log

[program:photoapp-admin]
command=/var/www/photo_proof_admin/.venv/bin/python app.py
directory=/var/www/photo_proof_admin
user=photoapp
autostart=true
autorestart=true
stderr_logfile=/var/log/photoapp/admin-error.log
stdout_logfile=/var/log/photoapp/admin-access.log
```

```bash
# Create log directory
sudo mkdir -p /var/log/photoapp
sudo chown photoapp:photoapp /var/log/photoapp

# Start services
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

---

## Part 5: DNS Configuration

### For Your Main Domain (photoapp.com)

At your domain registrar:

```
Type    Name    Value                   TTL
────────────────────────────────────────────────
A       @       YOUR_SERVER_IP          3600
A       *       YOUR_SERVER_IP          3600    ← Wildcard for all subdomains
CNAME   www     photoapp.com            3600
```

### For Studio's Custom Domain (winowstudio.com)

Studio owner adds at their registrar:

```
Type    Name    Value                   TTL
────────────────────────────────────────────────
A       @       YOUR_SERVER_IP          3600
CNAME   www     winowstudio.com         3600
```

---

## Part 6: Adding New Custom Domain (Automation Script)

```bash
#!/bin/bash
# /usr/local/bin/add-custom-domain.sh

DOMAIN=$1

if [ -z "$DOMAIN" ]; then
    echo "Usage: add-custom-domain.sh <domain>"
    exit 1
fi

echo "Adding custom domain: $DOMAIN"

# 1. Get SSL certificate
sudo certbot certonly --nginx -d "$DOMAIN" -d "www.$DOMAIN"

# 2. Create nginx config
sudo cat > /etc/nginx/sites-available/$DOMAIN << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
    }

    location /uploads {
        alias /var/www/photoapp/uploads;
        expires 30d;
    }
}
EOF

# 3. Enable site
sudo ln -s /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/

# 4. Test and reload
sudo nginx -t && sudo systemctl reload nginx

echo "✅ Domain $DOMAIN configured!"
echo "Remember to add to studio_domains table in database"
```

---

## Part 7: Monitoring & Health Checks

### Health Check Endpoint

```python
# In photo_proof_api/app/routers/health.py

@router.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
```

### Uptime Monitoring

Use services like:
- UptimeRobot (free tier available)
- Pingdom
- StatusCake

Monitor:
- `https://photoapp.com/api/health`
- `https://demo.photoapp.com/api/health`
- Each custom domain

### Log Rotation

```bash
# /etc/logrotate.d/photoapp

/var/log/photoapp/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 photoapp photoapp
    sharedscripts
    postrotate
        supervisorctl restart all > /dev/null
    endscript
}
```

---

## Part 8: Backup Strategy

### Database Backup

```bash
#!/bin/bash
# /usr/local/bin/backup-db.sh

BACKUP_DIR="/var/backups/photoapp"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="photoapp_db_$DATE.sql.gz"

mkdir -p $BACKUP_DIR

pg_dump -U photo_proof_user photo_proof_production | gzip > "$BACKUP_DIR/$FILENAME"

# Keep only last 7 days
find $BACKUP_DIR -name "photoapp_db_*.sql.gz" -mtime +7 -delete

echo "Backup created: $FILENAME"
```

### Add to Cron

```bash
# Daily at 2 AM
0 2 * * * /usr/local/bin/backup-db.sh
```

---

## Quick Reference: Production Checklist

```
SERVER SETUP:
□ Provision server with adequate resources
□ Install nginx, PostgreSQL, Python, Node.js
□ Configure firewall (ports 80, 443)
□ Set up SSL certificates

APPLICATION:
□ Deploy backend API
□ Build and deploy frontend
□ Configure production .env
□ Set up supervisor for process management

DOMAINS:
□ Configure DNS for main domain
□ Set up wildcard subdomain (*.photoapp.com)
□ Script for adding custom domains

SECURITY:
□ Strong database passwords
□ Secure SECRET_KEY
□ HTTPS everywhere
□ Regular security updates

MONITORING:
□ Health check endpoints
□ Uptime monitoring
□ Log rotation
□ Automated backups
```

---

## Next Steps

- **[TENANT_MIDDLEWARE_REFERENCE.md](./TENANT_MIDDLEWARE_REFERENCE.md)** - Technical deep-dive into tenant detection
