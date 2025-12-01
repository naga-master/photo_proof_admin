# PhotoProof Admin Dashboard

## Overview

Internal admin dashboard for managing PhotoProof multi-tenant SaaS platform.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MARKETING WEBSITE                            │
│                   (features, pricing, etc.)                      │
│                                                                  │
│                    [Start Free Trial]                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ADMIN DASHBOARD (This App)                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PUBLIC: /signup                                          │  │
│  │  - Studio registration                                    │  │
│  │  - Plan selection                                         │  │
│  │  - Domain configuration                                   │  │
│  │  - Account creation                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PROTECTED: Admin Pages                                   │  │
│  │  - Dashboard (overview stats)                             │  │
│  │  - Studios (list, edit, disable)                          │  │
│  │  - Features (toggle per studio)                           │  │
│  │  - Plans (subscription management)                        │  │
│  │  - Provisioning (domain setup queue)                      │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CUSTOMER APP (React)                          │
│  - Login only (no onboarding)                                   │
│  - Full studio management features                               │
└─────────────────────────────────────────────────────────────────┘
```

## Customer Journey

1. **Discovery**: Customer visits marketing website
2. **Signup**: Clicks "Start Free Trial" → redirected to Admin Dashboard /signup
3. **Registration**: Fills studio details, picks plan, enters domain
4. **Provisioning**: System sets up domain (auto in prod, manual in local dev)
5. **Notification**: Customer receives "Your studio is ready!" email
6. **Access**: Customer logs into their custom domain

## Tech Stack

- **Framework**: Flask (Python)
- **Package Manager**: uv (fast Python package installer)
- **Database**: Shares PostgreSQL/SQLite with main API
- **Authentication**: Session-based for admin pages
- **Hosting**: Same server, port 8501

## Pages

| Page | Access | Purpose |
|------|--------|---------|
| Signup | Public | Customer onboarding |
| Dashboard | Admin | Overview stats |
| Studios | Admin | Manage all studios |
| Features | Admin | Toggle features per studio |
| Plans | Admin | Subscription plan management |
| Provisioning | Admin | Domain setup queue |

## Environment Variables

```bash
# Database (same as main API)
DATABASE_URL=postgresql://user:pass@localhost:5432/photoproof

# Admin credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password

# Email (for sending invites)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

## Running the App

```bash
cd photo_proof_admin

# Using start script (recommended)
./start.sh

# Or manually with uv
uv venv
uv pip install -r requirements.txt
uv run python app.py
```

## Local Development

For local dev, domain provisioning requires manual intervention:
1. Customer completes signup
2. Studio status: "Provisioning"
3. Admin goes to Provisioning page
4. Clicks "Provision" button
5. Script adds domain to /etc/hosts
6. Email sent to customer

## Production

Domain provisioning is automated:
1. Customer completes signup
2. System verifies DNS CNAME
3. Let's Encrypt provisions SSL
4. Email sent automatically
