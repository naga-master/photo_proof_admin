# PhotoProof Admin Dashboard

Internal admin dashboard for managing the PhotoProof multi-tenant platform.
Built with Flask for full control over the UI.

## Features

- **Public Signup Page** - Customer onboarding (link from marketing site)
- **Studios Management** - View, edit, disable studios
- **Feature Toggles** - Enable/disable features per studio
- **Domain Provisioning** - Setup domains for local development

## Quick Start

### Using uv (Recommended)

```bash
cd photo_proof_admin

# Run with start script (auto-installs uv if needed)
./start.sh
```

### Manual Setup

```bash
cd photo_proof_admin

# Install uv if not installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt

# Run the app
uv run python app.py
```

### Access the Dashboard

- **Signup Page:** http://localhost:8501/signup
- **Admin Dashboard:** http://localhost:8501/admin

### Default Credentials

- Username: `admin`
- Password: `admin123`

> **Change these in production!** Edit `config.py` or set environment variables.

## Troubleshooting

### Database Connection Issues

The app tries PostgreSQL first, then falls back to SQLite. To use PostgreSQL:

1. Make sure the main API database is running
2. Check connection settings in `config.py`
3. Or set `DATABASE_URL` environment variable

### uv Not Found

If uv is not installed, the start script will auto-install it. Or install manually:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Project Structure

```
photo_proof_admin/
├── app.py                    # Flask application
├── auth.py                   # Authentication helpers
├── config.py                 # Configuration settings
├── database.py               # Database models & connection
├── requirements.txt          # Python dependencies
├── start.sh                  # Startup script (uses uv)
├── docs/
│   └── ARCHITECTURE.md       # Technical documentation
├── static/
│   └── css/
│       └── style.css         # Stylesheet
└── templates/
    ├── base.html             # Base template
    ├── signup/
    │   ├── base.html         # Signup layout with progress steps
    │   ├── start.html        # Step 1: Studio details
    │   ├── plan.html         # Step 2: Plan selection
    │   └── complete.html     # Completion page
    └── admin/
        ├── base.html         # Admin layout with sidebar
        ├── login.html        # Admin login
        ├── dashboard.html    # Overview stats
        ├── studios.html      # Studios management
        ├── features.html     # Feature toggles
        └── provisioning.html # Domain setup queue
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://postgres:postgres@localhost:5432/photo_proof` |
| `ADMIN_USERNAME` | Admin login username | `admin` |
| `ADMIN_PASSWORD` | Admin login password | `admin123` |
| `SECRET_KEY` | Flask session secret | `dev-secret-key-change-in-production` |

### Changing Admin Credentials

Edit `config.py` or set environment variables:

```bash
export ADMIN_USERNAME=myadmin
export ADMIN_PASSWORD=mysecurepassword
```

## Customer Flow

1. Customer visits marketing website
2. Clicks "Start Free Trial" → redirected to `/signup`
3. Fills out studio details, domain, and account info
4. Selects subscription plan
5. Studio created with "pending" status
6. Admin provisions domain (adds to `/etc/hosts` for local dev)
7. Customer receives email and logs into their studio

## Local Development: Domain Provisioning

For local development, custom domains need to be added to `/etc/hosts`:

1. Customer signs up with domain (e.g., `gallery.smithphoto.com`)
2. Go to **Provisioning** page in admin dashboard
3. Copy the hosts entry shown
4. Add to `/etc/hosts`:
   ```bash
   sudo nano /etc/hosts
   # Add: 127.0.0.1    gallery.smithphoto.com
   ```
5. Click "Mark as Provisioned"
6. Customer can now access their studio

## Production Deployment

In production:

1. Set `SECRET_KEY` to a secure random value
2. Use proper admin credentials
3. Configure real SMTP for emails
4. Domain provisioning is automated (DNS verification + Let's Encrypt)
