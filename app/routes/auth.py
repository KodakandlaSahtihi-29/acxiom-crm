from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models.user import User, Role
from app.forms.auth_forms import LoginForm, RegisterForm
from app.utils.security import is_safe_redirect_url
from app.services.audit_service import log_auth_event, AuditEventType

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Authenticate user via username or email.
    Enforces active status, lockout policy, and logs audit events.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        ident = form.username_or_email.data.strip()
        password = form.password.data

        # Case-insensitive query by username OR email
        user = User.query.filter(
            or_(
                User.username.ilike(ident),
                User.email.ilike(ident)
            )
        ).first()

        if not user:
            # Constant-time delay/generic message for non-existent user
            log_auth_event(AuditEventType.LOGIN_FAILED, username=ident, details="User not found")
            flash("Invalid credentials. Please verify your username/email and password.", "danger")
            return render_template('auth/login.html', form=form), 401

        # Check account lockout status
        if user.is_locked():
            mins = user.get_remaining_lockout_minutes()
            log_auth_event(
                AuditEventType.ACCOUNT_LOCKED,
                username=user.username,
                user_id=user.id,
                details=f"Locked out attempt. {mins}m remaining."
            )
            flash(
                f"This account is temporarily locked due to 5 consecutive failed login attempts. "
                f"Please try again in approximately {mins} minute(s).",
                "danger"
            )
            return render_template('auth/login.html', form=form), 403

        # Check active status
        if not user.is_active:
            log_auth_event(
                AuditEventType.LOGIN_FAILED,
                username=user.username,
                user_id=user.id,
                details="Inactive user login attempt"
            )
            flash("Your account has been deactivated. Please contact an administrator for assistance.", "warning")
            return render_template('auth/login.html', form=form), 403

        # Verify password hash
        if not user.check_password(password):
            user.record_failed_login(max_attempts=5, lockout_minutes=15)
            if user.is_locked():
                log_auth_event(
                    AuditEventType.ACCOUNT_LOCKED,
                    username=user.username,
                    user_id=user.id,
                    details="Account locked after 5 failed attempts"
                )
                flash(
                    "Account locked due to 5 consecutive failed attempts. "
                    "Access is restricted for the next 15 minutes.",
                    "danger"
                )
                return render_template('auth/login.html', form=form), 403
            else:
                remaining = 5 - user.failed_login_attempts
                log_auth_event(
                    AuditEventType.LOGIN_FAILED,
                    username=user.username,
                    user_id=user.id,
                    details=f"Invalid password. {remaining} attempts remaining."
                )
                flash(
                    f"Invalid credentials. You have {remaining} attempt(s) remaining before your account is locked.",
                    "danger"
                )
                return render_template('auth/login.html', form=form), 401

        # Authentication successful: reset failed attempts & establish session
        user.reset_failed_logins()
        login_user(user, remember=form.remember_me.data)
        log_auth_event(AuditEventType.LOGIN_SUCCESS, username=user.username, user_id=user.id, details="Successful authentication")

        flash(f"Welcome back, {user.full_name}!", "success")

        # Safe redirection check
        next_page = request.args.get('next')
        if next_page and is_safe_redirect_url(next_page):
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))

    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Register a new user account.
    Assigns safe default role (SalesExecutive) and prevents elevation to Admin.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User(
            full_name=form.full_name.data.strip(),
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role=Role.SALES_EXECUTIVE,  # Guaranteed safe default role
            is_active=True
        )
        new_user.set_password(form.password.data)

        db.session.add(new_user)
        db.session.commit()

        log_auth_event(
            AuditEventType.REGISTER_SUCCESS,
            username=new_user.username,
            user_id=new_user.id,
            details=f"Self-registration completed with default role: {Role.SALES_EXECUTIVE}"
        )

        flash("Account created successfully! You may now sign in.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout', methods=['POST', 'GET'])
@login_required
def logout():
    """
    Log out the current authenticated user session.
    Protected with CSRF verification when submitted via POST.
    """
    user_id = current_user.id
    username = current_user.username
    logout_user()
    log_auth_event(AuditEventType.LOGOUT, username=username, user_id=user_id, details="Session ended")
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('auth.login'))


@auth_bp.route('/access-denied')
def access_denied():
    """Access Denied error page (HTTP 403 Forbidden)."""
    log_auth_event(
        AuditEventType.ACCESS_DENIED,
        username=current_user.username if current_user.is_authenticated else 'Anonymous',
        user_id=current_user.id if current_user.is_authenticated else None,
        details=f"Unauthorized access attempt to {request.referrer or 'unknown'}"
    )
    return render_template('auth/access_denied.html'), 403
