"""
User & Role Management Routes for Acxiom CRM.
Provides Admin-only functionality to:
- List all users with filtering by role and status
- Create new users with role assignment and password policy enforcement
- Edit user details, reassign roles, and optionally reset passwords
- Toggle active/inactive status with safeguard against deactivating the last active Admin
- View Roles and Permissions matrix
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models.user import User, Role
from app.forms.user_forms import CreateUserForm, EditUserForm
from app.utils.decorators import admin_required
from app.services.audit_service import AUDIT_TRAIL, AuditEventType

user_bp = Blueprint('user', __name__, url_prefix='/users')


@user_bp.route('/')
@admin_required
def index():
    """Admin-only User List with search, filtering, and role/status statistics."""
    search_query = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = User.query

    if search_query:
        query = query.filter(
            or_(
                User.username.ilike(f'%{search_query}%'),
                User.full_name.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%')
            )
        )

    if role_filter and role_filter in Role.ALL_ROLES:
        query = query.filter(User.role == role_filter)

    if status_filter == 'active':
        query = query.filter(User.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(User.is_active == False)

    users = query.order_by(User.id.asc()).all()

    # Aggregate statistics
    total_users = User.query.count()
    admin_count = User.query.filter_by(role=Role.ADMIN).count()
    manager_count = User.query.filter_by(role=Role.MANAGER).count()
    sales_count = User.query.filter_by(role=Role.SALES_EXECUTIVE).count()
    active_count = User.query.filter_by(is_active=True).count()
    inactive_count = User.query.filter_by(is_active=False).count()

    return render_template(
        'users/index.html',
        users=users,
        search_query=search_query,
        role_filter=role_filter,
        status_filter=status_filter,
        total_users=total_users,
        admin_count=admin_count,
        manager_count=manager_count,
        sales_count=sales_count,
        active_count=active_count,
        inactive_count=inactive_count,
        Role=Role
    )


@user_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create():
    """Admin-only creation of new users with role assignment and password policy."""
    form = CreateUserForm()

    if form.validate_on_submit():
        new_user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            full_name=form.full_name.data.strip(),
            role=form.role.data,
            is_active=form.is_active.data
        )
        new_user.set_password(form.password.data)

        db.session.add(new_user)
        db.session.commit()

        # Audit logging
        AUDIT_TRAIL.append({
            'Action': AuditEventType.USER_CREATE,
            'UserId': current_user.id,
            'EntityName': 'User',
            'RecordId': new_user.id,
            'OldValue': None,
            'NewValue': {
                'username': new_user.username,
                'email': new_user.email,
                'role': new_user.role,
                'is_active': new_user.is_active
            }
        })

        flash(f"User '{new_user.username}' ({new_user.role}) was created successfully.", "success")
        return redirect(url_for('user.index'))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('users/create.html', form=form), status_code


@user_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit(id):
    """Admin-only editing of user account details, role reassignment, and password reset."""
    user = User.query.get_or_404(id)
    form = EditUserForm(original_user=user, obj=user)

    if form.validate_on_submit():
        # Safeguard: prevent demoting the last active Administrator
        if user.role == Role.ADMIN and form.role.data != Role.ADMIN:
            active_admins = User.query.filter_by(role=Role.ADMIN, is_active=True).count()
            if active_admins <= 1:
                flash("Operation rejected: Cannot demote the last active Administrator account.", "danger")
                return render_template('users/edit.html', form=form, target_user=user), 400

        # Safeguard: prevent deactivating the last active Administrator
        if user.role == Role.ADMIN and not form.is_active.data:
            active_admins = User.query.filter_by(role=Role.ADMIN, is_active=True).count()
            if active_admins <= 1:
                flash("Operation rejected: Cannot deactivate the last active Administrator account.", "danger")
                return render_template('users/edit.html', form=form, target_user=user), 400

        old_state = {
            'username': user.username,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
            'is_active': user.is_active
        }

        user.username = form.username.data.strip()
        user.email = form.email.data.strip().lower()
        user.full_name = form.full_name.data.strip()
        user.role = form.role.data
        user.is_active = form.is_active.data

        # Reset password if new password provided
        if form.new_password.data:
            user.set_password(form.new_password.data)

        db.session.commit()

        # Audit logging
        AUDIT_TRAIL.append({
            'Action': AuditEventType.USER_UPDATE,
            'UserId': current_user.id,
            'EntityName': 'User',
            'RecordId': user.id,
            'OldValue': old_state,
            'NewValue': {
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'is_active': user.is_active
            }
        })

        flash(f"User account '{user.username}' successfully updated.", "success")
        return redirect(url_for('user.index'))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('users/edit.html', form=form, target_user=user), status_code


@user_bp.route('/toggle-status/<int:id>', methods=['POST'])
@admin_required
def toggle_status(id):
    """Toggle a user's active/inactive status with safeguard for the last active Admin."""
    user = User.query.get_or_404(id)

    # Safeguard: prevent deactivating the last active Admin
    if user.is_active and user.role == Role.ADMIN:
        active_admins = User.query.filter_by(role=Role.ADMIN, is_active=True).count()
        if active_admins <= 1:
            flash("Operation rejected: Cannot deactivate the last active Administrator account.", "danger")
            return redirect(url_for('user.index'))

    user.is_active = not user.is_active
    db.session.commit()

    # Audit logging
    AUDIT_TRAIL.append({
        'Action': AuditEventType.USER_STATUS_CHANGE,
        'UserId': current_user.id,
        'EntityName': 'User',
        'RecordId': user.id,
        'OldValue': {'is_active': not user.is_active},
        'NewValue': {'is_active': user.is_active}
    })

    status_label = "activated" if user.is_active else "deactivated"
    flash(f"User '{user.username}' has been {status_label}.", "info")
    return redirect(url_for('user.index'))


@user_bp.route('/roles')
@admin_required
def roles():
    """Display configured Roles and system Permissions matrix."""
    roles_info = [
        {
            'name': Role.ADMIN,
            'description': 'Full administrative control over all system modules, configurations, and user management.',
            'badge': 'bg-danger',
            'icon': 'fa-solid fa-user-shield',
            'user_count': User.query.filter_by(role=Role.ADMIN).count(),
            'permissions': [
                'Full User & Role Management (Create, Edit, Activate, Deactivate, Reassign)',
                'Full Customer Management (All records across organization)',
                'Full Lead Management & Lead Conversion (All records)',
                'Full Opportunity Management & Pipeline (All records)',
                'Full Follow-Up Management (Schedule, Complete, Reschedule, Delete)',
                'Full Activity Management (Calls, Meetings, Emails, Tasks)',
                'Global Executive Dashboard (Full organizational KPI visibility)',
                'Audit Trail & System Monitoring'
            ]
        },
        {
            'name': Role.MANAGER,
            'description': 'Supervisory control over CRM operations, sales pipelines, and team records.',
            'badge': 'bg-warning text-dark',
            'icon': 'fa-solid fa-briefcase',
            'user_count': User.query.filter_by(role=Role.MANAGER).count(),
            'permissions': [
                'View-only access to User Directory',
                'Full Customer Management across team/business scope',
                'Full Lead Management & Conversion across team/business scope',
                'Full Opportunity Management & Pipeline across team/business scope',
                'Team Follow-Up Management (View, Complete, Reschedule)',
                'Team Activity Management (Calls, Meetings, Emails, Tasks)',
                'Business Scope Dashboard (Team-level KPI visibility)'
            ]
        },
        {
            'name': Role.SALES_EXECUTIVE,
            'description': 'Sales representative responsible for managing assigned leads, customers, and opportunities.',
            'badge': 'bg-primary',
            'icon': 'fa-solid fa-user',
            'user_count': User.query.filter_by(role=Role.SALES_EXECUTIVE).count(),
            'permissions': [
                'View & Manage own created Customers',
                'View & Manage assigned / created Leads & Lead Conversion',
                'View & Manage assigned / created Opportunities & Pipeline',
                'View & Manage assigned Follow-Ups',
                'Log & Manage assigned Activities (Calls, Meetings, Emails, Tasks)',
                'Personal Dashboard (Assigned & owned records only)'
            ]
        }
    ]

    return render_template('users/roles.html', roles=roles_info)


@user_bp.route('/permissions')
@admin_required
def permissions():
    """Shortcut redirect to the Roles & Permissions matrix view."""
    return redirect(url_for('user.roles'))
