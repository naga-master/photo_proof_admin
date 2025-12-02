# Multi-Tenant Architecture Overview

## What is Multi-Tenancy?

Multi-tenancy is a software architecture where a single instance of an application serves multiple customers (tenants). Each tenant's data is isolated and invisible to other tenants, but they all share the same application infrastructure.

In PhotoProof:
- **Tenant** = Photography Studio
- **Each studio** has its own clients, projects, photos, invoices, contracts
- **All studios** share the same backend API and frontend application
- **Data isolation** is enforced at the database query level using `studio_id`

## How PhotoProof Identifies Tenants

PhotoProof uses **domain-based tenant detection**. When a request comes in, the system looks at the URL/domain to determine which studio the request is for.

### Two Approaches Supported

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DOMAIN-BASED TENANT DETECTION                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  APPROACH 1: SUBDOMAIN                                               │
│  ─────────────────────                                               │
│  URL: https://demo.photoapp.com                                      │
│                 ^^^^                                                 │
│                 └── Subdomain identifies the studio                  │
│                                                                      │
│  • You own the main domain (photoapp.com)                           │
│  • Each studio gets: {studio}.photoapp.com                          │
│  • Examples:                                                         │
│    - demo.photoapp.com    → Demo Photography Studio                 │
│    - smith.photoapp.com   → Smith Photography                       │
│    - wedding.photoapp.com → Wedding Moments Studio                  │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  APPROACH 2: CUSTOM DOMAIN                                          │
│  ─────────────────────────                                          │
│  URL: https://winowstudio.com                                       │
│                ^^^^^^^^^^^^^^^                                       │
│                └── Entire domain mapped to a studio                  │
│                                                                      │
│  • Studio owns their own domain                                      │
│  • They configure DNS to point to your server                       │
│  • Examples:                                                         │
│    - winowstudio.com      → Winow Studio                            │
│    - photos.smithwedding.com → Smith Photography                    │
│    - gallery.janedoe.photography → Jane Doe Photography             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Architecture Diagram

```
                                    MULTI-TENANT REQUEST FLOW
                                    
    ┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
    │   User Browser   │         │   User Browser   │         │   User Browser   │
    │                  │         │                  │         │                  │
    │ demo.photoapp.   │         │ alpha.photoapp.  │         │ winowstudio.com  │
    │     local:3001   │         │     local:3001   │         │                  │
    └────────┬─────────┘         └────────┬─────────┘         └────────┬─────────┘
             │                            │                            │
             │ Host: demo.photoapp.local  │ Host: alpha.photoapp.local │ Host: winowstudio.com
             │                            │                            │
             └────────────────────────────┼────────────────────────────┘
                                          │
                                          ▼
                            ┌─────────────────────────┐
                            │     Frontend (React)     │
                            │     localhost:3001       │
                            │                          │
                            │  • Reads Host header     │
                            │  • Fetches studio theme  │
                            │  • Applies branding      │
                            └────────────┬────────────┘
                                         │
                                         │ API Requests with Host header
                                         ▼
                            ┌─────────────────────────┐
                            │   Backend API (FastAPI)  │
                            │     localhost:8000       │
                            │                          │
                            │  ┌───────────────────┐  │
                            │  │ Tenant Middleware │  │
                            │  │                   │  │
                            │  │ 1. Extract Host   │  │
                            │  │ 2. Lookup Studio  │  │
                            │  │ 3. Set Context    │  │
                            │  └─────────┬─────────┘  │
                            │            │            │
                            │            ▼            │
                            │  ┌───────────────────┐  │
                            │  │  Route Handlers   │  │
                            │  │                   │  │
                            │  │ Filter by         │  │
                            │  │ studio_id         │  │
                            │  └─────────┬─────────┘  │
                            └────────────┼────────────┘
                                         │
                                         ▼
                            ┌─────────────────────────┐
                            │      PostgreSQL DB       │
                            │                          │
                            │  ┌───────────────────┐  │
                            │  │     studios       │  │
                            │  │  - id             │  │
                            │  │  - name           │  │
                            │  │  - subdomain      │◄─┼── Subdomain lookup
                            │  └───────────────────┘  │
                            │                          │
                            │  ┌───────────────────┐  │
                            │  │  studio_domains   │  │
                            │  │  - studio_id      │  │
                            │  │  - domain         │◄─┼── Custom domain lookup
                            │  │  - is_verified    │  │
                            │  └───────────────────┘  │
                            │                          │
                            │  ┌───────────────────┐  │
                            │  │  clients          │  │
                            │  │  - studio_id ────►│──┼── Data filtered by studio_id
                            │  └───────────────────┘  │
                            │                          │
                            │  ┌───────────────────┐  │
                            │  │  projects         │  │
                            │  │  - studio_id ────►│──┼── Data filtered by studio_id
                            │  └───────────────────┘  │
                            └─────────────────────────┘
```

## Data Isolation

Every data table that contains tenant-specific data has a `studio_id` column:

```sql
-- Example: Clients table
SELECT * FROM clients WHERE studio_id = 'demo-studio-uuid';

-- Example: Projects table  
SELECT * FROM projects WHERE studio_id = 'demo-studio-uuid';

-- This ensures Studio A never sees Studio B's data
```

The `studio_id` filter is applied automatically in API endpoints based on the authenticated user's studio.

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Tenant Middleware | `photo_proof_api/app/middleware/tenant.py` | Detects studio from domain |
| Studio Model | `photo_proof_api/app/db/models/multi_tenant.py` | Studio table with subdomain |
| StudioDomain Model | `photo_proof_api/app/db/models/multi_tenant.py` | Custom domains table |
| Auth Service | `photo_proof_api/app/services/auth_service.py` | JWT tokens with studio_id |
| CORS Config | `photo_proof_api/.env` | Allowed origins for each domain |

## Next Steps

- **[SUBDOMAIN_SETUP.md](./SUBDOMAIN_SETUP.md)** - Set up subdomain-based tenancy (demo.photoapp.local)
- **[CUSTOM_DOMAIN_SETUP.md](./CUSTOM_DOMAIN_SETUP.md)** - Set up custom domain tenancy (winowstudio.com)
- **[PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)** - Deploy to production
- **[TENANT_MIDDLEWARE_REFERENCE.md](./TENANT_MIDDLEWARE_REFERENCE.md)** - Technical deep-dive
