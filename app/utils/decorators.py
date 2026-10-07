from functools import wraps
from flask import redirect, url_for, flash, request
from flask_login import current_user
from app.models.user import Role


def role_required(*allowed_roles):
    """
    Decorator to restrict access to users having at least one of the specified roles.
    If the user is not logged in, redirects to the login page.
    If the user lacks permission, redirects to the access-denied page.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('auth.login', next=request.path))

            if current_user.role not in allowed_roles:
                flash(f"Access Denied: Your role ({current_user.role}) does not have permission to view this resource.", "danger")
                return redirect(url_for('auth.access_denied'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Convenience decorator restricting access to Administrator accounts only."""
    return role_required(Role.ADMIN)(f)


def manager_required(f):
    """Convenience decorator restricting access to Managers and Administrators."""
    return role_required(Role.ADMIN, Role.MANAGER)(f)


def sales_executive_required(f):
    """Access for all CRM team members (Admin, Manager, SalesExecutive)."""
    return role_required(Role.ADMIN, Role.MANAGER, Role.SALES_EXECUTIVE)(f)
