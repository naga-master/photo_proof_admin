"""
PhotoProof Admin Dashboard - Flask Application
"""
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import os
import uuid

from config import ADMIN_USERNAME, ADMIN_PASSWORD, PLANS, FEATURES
from database import (
    get_db_session, Studio, StudioDomain, User, StudioFeature,
    create_studio, get_all_studios, get_studio_by_id, 
    get_pending_studios, provision_studio, get_studio_features, toggle_feature,
    joinedload
)
from auth import hash_password, verify_password

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")


# Auth decorator for admin pages
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please login to access this page", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


# ==================== PUBLIC ROUTES ====================

@app.route("/")
def index():
    """Redirect to signup or admin based on context."""
    return redirect(url_for("signup"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Public signup page - Step 1: Studio details and account."""
    if request.method == "POST":
        studio_name = request.form.get("studio_name")
        domain = request.form.get("domain")
        email = request.form.get("email")
        owner_name = request.form.get("owner_name")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        # Validation
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("signup/start.html")
        
        if len(password) < 8:
            flash("Password must be at least 8 characters", "error")
            return render_template("signup/start.html")
        
        # Store in session for plan selection
        session["signup_studio_name"] = studio_name
        session["signup_domain"] = domain
        session["signup_email"] = email
        session["signup_owner_name"] = owner_name
        session["signup_password"] = password
        session["signup_subdomain"] = studio_name.lower().replace(" ", "-").replace("'", "")
        
        return redirect(url_for("signup_plan"))
    
    return render_template("signup/start.html")


@app.route("/signup/plan", methods=["GET", "POST"])
def signup_plan():
    """Step 2: Plan selection."""
    if "signup_studio_name" not in session:
        return redirect(url_for("signup"))
    
    if request.method == "POST":
        plan = request.form.get("plan", "starter")
        session["signup_plan"] = plan
        return redirect(url_for("signup_branding"))
    
    return render_template("signup/plan.html", plans=PLANS, features=FEATURES)


@app.route("/signup/branding", methods=["GET", "POST"])
def signup_branding():
    """Signup step 3: Branding customization."""
    if "signup_plan" not in session:
        return redirect(url_for("signup_plan"))
    
    if request.method == "POST":
        brand_color = request.form.get("brand_color", "#0EA5E9")
        typography = request.form.get("typography", "Modern (Inter)")
        skip_logo = request.form.get("skip_logo") == "on"
        skip_photo = request.form.get("skip_photo") == "on"
        
        # Prepare upload directory
        import os
        from werkzeug.utils import secure_filename
        upload_dir = os.path.join(os.path.dirname(__file__), '..', 'photo_proof_api', 'uploads', 'studios')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate studio ID early for file naming
        studio_id = str(uuid.uuid4())
        
        # Handle logo upload - save to file
        logo_url = None
        if not skip_logo and "logo" in request.files:
            logo_file = request.files["logo"]
            if logo_file and logo_file.filename:
                ext = os.path.splitext(logo_file.filename)[1] or '.png'
                logo_filename = f"{studio_id}_logo{ext}"
                logo_path = os.path.join(upload_dir, logo_filename)
                logo_file.save(logo_path)
                logo_url = f"/uploads/studios/{logo_filename}"
        
        # Handle studio photo upload - save to file
        photo_url = None
        if not skip_photo and "studio_photo" in request.files:
            photo_file = request.files["studio_photo"]
            if photo_file and photo_file.filename:
                ext = os.path.splitext(photo_file.filename)[1] or '.jpg'
                photo_filename = f"{studio_id}_photo{ext}"
                photo_path = os.path.join(upload_dir, photo_filename)
                photo_file.save(photo_path)
                photo_url = f"/uploads/studios/{photo_filename}"
        
        # Create the studio with all data
        try:
            db = get_db_session()
            studio = create_studio(
                db=db,
                name=session["signup_studio_name"],
                subdomain=session["signup_subdomain"],
                domain=session["signup_domain"],
                owner_email=session["signup_email"],
                owner_name=session["signup_owner_name"],
                password_hash=hash_password(session["signup_password"]),
                plan=session["signup_plan"],
                studio_id=studio_id
            )
            
            # Update branding fields
            studio.brand_color = brand_color
            studio.typography = typography
            if logo_url:
                studio.logo_url = logo_url
            if photo_url:
                studio.studio_photo = photo_url
            
            db.commit()
            # studio_id already set before create_studio call
            db.close()
            
            # Clear signup session data
            for key in ["signup_studio_name", "signup_domain", "signup_email", 
                       "signup_owner_name", "signup_password", "signup_subdomain", "signup_plan"]:
                session.pop(key, None)
            
            return redirect(url_for("signup_complete", studio_id=studio_id))
            
        except Exception as e:
            error_msg = str(e)
            if "ix_studios_subdomain" in error_msg or "subdomain" in error_msg.lower():
                error_msg = f"The subdomain '{session.get('signup_subdomain')}' is already taken. Please go back and choose a different one."
            elif "ix_studios_email" in error_msg or "studios_email" in error_msg.lower():
                error_msg = f"The email '{session.get('signup_email')}' is already registered."
            flash(f"Failed to create studio: {error_msg}", "error")
            return render_template("signup/branding.html", error=error_msg)
    
    return render_template("signup/branding.html")


@app.route("/signup/complete/<studio_id>")
def signup_complete(studio_id):
    """Signup completion page."""
    db = get_db_session()
    studio = get_studio_by_id(db, studio_id)
    domain = studio.domains[0].domain if studio and studio.domains else "your-domain.com"
    db.close()
    return render_template("signup/complete.html", studio=studio, domain=domain)


# ==================== ADMIN ROUTES ====================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page."""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            flash("Login successful", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials", "error")
    
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    """Admin logout."""
    session.pop("admin_logged_in", None)
    flash("Logged out successfully", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    """Admin dashboard overview."""
    db = get_db_session()
    
    total_studios = db.query(Studio).count()
    active_studios = db.query(Studio).filter(
        Studio.is_active == True,
        Studio.onboarding_completed == True
    ).count()
    pending_studios = db.query(Studio).filter(Studio.onboarding_completed == False).count()
    total_users = db.query(User).count()
    
    recent_studios = db.query(Studio).options(
        joinedload(Studio.domains)
    ).order_by(Studio.created_at.desc()).limit(5).all()
    pending_list = get_pending_studios(db)
    
    db.close()
    
    return render_template("admin/dashboard.html",
        total_studios=total_studios,
        active_studios=active_studios,
        pending_studios=pending_studios,
        total_users=total_users,
        recent_studios=recent_studios,
        pending_list=pending_list
    )


@app.route("/admin/studios")
@admin_required
def admin_studios():
    """Studios management page."""
    db = get_db_session()
    
    status_filter = request.args.get("status", "all")
    search = request.args.get("search", "")
    
    query = db.query(Studio).options(joinedload(Studio.domains))
    
    if status_filter == "active":
        query = query.filter(Studio.onboarding_completed == True, Studio.is_active == True)
    elif status_filter == "pending":
        query = query.filter(Studio.onboarding_completed == False)
    elif status_filter == "inactive":
        query = query.filter(Studio.is_active == False)
    
    if search:
        query = query.filter(Studio.name.ilike(f"%{search}%"))
    
    studios = query.order_by(Studio.created_at.desc()).all()
    db.close()
    
    return render_template("admin/studios.html", studios=studios, status_filter=status_filter, search=search)


@app.route("/admin/studios/<studio_id>/toggle", methods=["POST"])
@admin_required
def toggle_studio(studio_id):
    """Toggle studio active status."""
    db = get_db_session()
    studio = get_studio_by_id(db, studio_id)
    if studio:
        studio.is_active = not studio.is_active
        db.commit()
        flash(f"Studio {'enabled' if studio.is_active else 'disabled'}", "success")
    db.close()
    return redirect(url_for("admin_studios"))


@app.route("/admin/features")
@admin_required
def admin_features():
    """Feature toggles page."""
    db = get_db_session()
    studios = get_all_studios(db)
    
    studio_id = request.args.get("studio_id")
    selected_studio = None
    studio_features = {}
    
    if studio_id:
        selected_studio = get_studio_by_id(db, studio_id)
        if selected_studio:
            features_list = get_studio_features(db, studio_id)
            studio_features = {f.feature_key: f.enabled for f in features_list}
    
    db.close()
    
    return render_template("admin/features.html",
        studios=studios,
        selected_studio=selected_studio,
        studio_features=studio_features,
        features=FEATURES
    )


@app.route("/admin/features/<studio_id>/toggle", methods=["POST"])
@admin_required
def toggle_studio_feature(studio_id):
    """Toggle a feature for a studio."""
    db = get_db_session()
    feature_key = request.form.get("feature_key")
    enabled = request.form.get("enabled") == "true"
    
    toggle_feature(db, studio_id, feature_key, enabled)
    db.close()
    
    flash(f"Feature {feature_key} {'enabled' if enabled else 'disabled'}", "success")
    return redirect(url_for("admin_features", studio_id=studio_id))


@app.route("/admin/provisioning")
@admin_required
def admin_provisioning():
    """Domain provisioning page."""
    db = get_db_session()
    pending = get_pending_studios(db)
    active = db.query(Studio).options(
        joinedload(Studio.domains)
    ).filter(Studio.onboarding_completed == True).all()
    db.close()
    
    return render_template("admin/provisioning.html", pending=pending, active=active)


@app.route("/admin/provisioning/<studio_id>/provision", methods=["POST"])
@admin_required
def provision(studio_id):
    """Provision a studio domain."""
    db = get_db_session()
    studio = provision_studio(db, studio_id)
    
    if studio and studio.domains:
        studio.domains[0].is_verified = True
        db.commit()
    
    db.close()
    flash("Studio provisioned successfully!", "success")
    return redirect(url_for("admin_provisioning"))


@app.route("/admin/provisioning/<studio_id>/deprovision", methods=["POST"])
@admin_required
def deprovision(studio_id):
    """Deprovision a studio."""
    db = get_db_session()
    studio = get_studio_by_id(db, studio_id)
    if studio:
        studio.onboarding_step = "pending"
        studio.onboarding_completed = False
        if studio.domains:
            studio.domains[0].is_verified = False
        db.commit()
    db.close()
    flash("Studio deprovisioned", "warning")
    return redirect(url_for("admin_provisioning"))


# ==================== API ROUTES ====================

@app.route("/api/check-domain")
def check_domain():
    """Check if domain is available."""
    domain = request.args.get("domain")
    if not domain:
        return jsonify({"available": False, "error": "Domain required"})
    
    db = get_db_session()
    existing = db.query(StudioDomain).filter(StudioDomain.domain == domain).first()
    db.close()
    
    return jsonify({"available": existing is None, "domain": domain})


if __name__ == "__main__":
    app.run(debug=True, port=8501, host="0.0.0.0")
