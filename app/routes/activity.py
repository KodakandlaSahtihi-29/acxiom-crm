"""
Activity Management Routes for Acxiom CRM.
Implements:
- /activities (Master activity list with search and filters)
- /activities/calls (Call activities view)
- /activities/meetings (Meeting activities view)
- /activities/emails (Email activities view)
- /activities/tasks (Task activities view)
- /activities/create (Create new activity)
- /activities/details/<id> (Activity details)
- /activities/edit/<id> (Edit activity)
- /activities/complete/<id> (Complete activity)
- /activities/cancel/<id> (Cancel activity)
- /activities/delete/<id> (Delete with confirmation)
"""
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models.activity import Activity, ActivityType, ActivityStatus
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.user import User, Role
from app.forms.activity_forms import ActivityForm, CompleteActivityForm, CancelActivityForm
from app.services.audit_service import log_activity_event, AuditEventType

activity_bp = Blueprint('activity', __name__, url_prefix='/activities')


def populate_activity_form_choices(form):
    """Populate dynamic choices for Customers, Leads, and Users."""
    customers = Customer.query.order_by(Customer.customer_name.asc()).all()
    form.customer_id.choices = [(0, '— None (General / Lead only) —')] + [
        (c.id, f"{c.customer_name} ({c.customer_code})") for c in customers
    ]

    leads = Lead.query.order_by(Lead.lead_name.asc()).all()
    form.lead_id.choices = [(0, '— None (General / Customer only) —')] + [
        (l.id, f"{l.lead_name} ({l.lead_code})") for l in leads
    ]

    users = User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    form.assigned_to.choices = [(u.id, f"{u.full_name} ({u.role})") for u in users]


@activity_bp.route('', strict_slashes=False)
@activity_bp.route('/', strict_slashes=False)
@login_required
def index():
    """
    Master Activity List view with multi-criteria filtering, search, and pagination.
    """
    search_query = request.args.get('q', '').strip()
    type_filter = request.args.get('type', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_filter = request.args.get('date_filter', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 15

    query = Activity.get_scoped_query(current_user)

    if search_query:
        query = query.outerjoin(Customer, Activity.customer_id == Customer.id)\
                     .outerjoin(Lead, Activity.lead_id == Lead.id)\
                     .filter(
                         or_(
                             Activity.subject.ilike(f'%{search_query}%'),
                             Activity.description.ilike(f'%{search_query}%'),
                             Customer.customer_name.ilike(f'%{search_query}%'),
                             Lead.lead_name.ilike(f'%{search_query}%')
                         )
                     )

    if type_filter and type_filter in ActivityType.ALL_TYPES:
        query = query.filter(Activity.activity_type == type_filter)

    if status_filter and status_filter in ActivityStatus.ALL_STATUSES:
        query = query.filter(Activity.status == status_filter)

    today = date.today()
    if date_filter == 'today':
        query = query.filter(Activity.activity_date == today)
    elif date_filter == 'upcoming':
        query = query.filter(Activity.activity_date > today)
    elif date_filter == 'past':
        query = query.filter(Activity.activity_date < today)

    # Order by date descending, then id descending
    query = query.order_by(Activity.activity_date.desc(), Activity.id.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    activities = pagination.items

    # Metrics scoped to current user
    base_scoped = Activity.get_scoped_query(current_user)
    total_count = base_scoped.count()
    calls_count = base_scoped.filter_by(activity_type=ActivityType.CALL).count()
    meetings_count = base_scoped.filter_by(activity_type=ActivityType.MEETING).count()
    emails_count = base_scoped.filter_by(activity_type=ActivityType.EMAIL).count()
    tasks_count = base_scoped.filter_by(activity_type=ActivityType.TASK).count()
    completed_count = base_scoped.filter_by(status=ActivityStatus.COMPLETED).count()

    return render_template(
        'activities/index.html',
        activities=activities,
        pagination=pagination,
        search_query=search_query,
        type_filter=type_filter,
        status_filter=status_filter,
        date_filter=date_filter,
        ActivityType=ActivityType,
        ActivityStatus=ActivityStatus,
        total_count=total_count,
        calls_count=calls_count,
        meetings_count=meetings_count,
        emails_count=emails_count,
        tasks_count=tasks_count,
        completed_count=completed_count,
        active_view='all'
    )


@activity_bp.route('/calls')
@login_required
def calls():
    """Shortcut view filtered specifically for Call activities."""
    return _filtered_type_view(ActivityType.CALL, 'calls')


@activity_bp.route('/meetings')
@login_required
def meetings():
    """Shortcut view filtered specifically for Meeting activities."""
    return _filtered_type_view(ActivityType.MEETING, 'meetings')


@activity_bp.route('/emails')
@login_required
def emails():
    """Shortcut view filtered specifically for Email activities."""
    return _filtered_type_view(ActivityType.EMAIL, 'emails')


@activity_bp.route('/tasks')
@login_required
def tasks():
    """Shortcut view filtered specifically for Task activities."""
    return _filtered_type_view(ActivityType.TASK, 'tasks')


def _filtered_type_view(target_type, view_slug):
    """Helper for the 4 mandatory module tree branches."""
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_filter = request.args.get('date_filter', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 15

    query = Activity.get_scoped_query(current_user).filter(Activity.activity_type == target_type)

    if search_query:
        query = query.outerjoin(Customer, Activity.customer_id == Customer.id)\
                     .outerjoin(Lead, Activity.lead_id == Lead.id)\
                     .filter(
                         or_(
                             Activity.subject.ilike(f'%{search_query}%'),
                             Activity.description.ilike(f'%{search_query}%'),
                             Customer.customer_name.ilike(f'%{search_query}%'),
                             Lead.lead_name.ilike(f'%{search_query}%')
                         )
                     )

    if status_filter and status_filter in ActivityStatus.ALL_STATUSES:
        query = query.filter(Activity.status == status_filter)

    today = date.today()
    if date_filter == 'today':
        query = query.filter(Activity.activity_date == today)
    elif date_filter == 'upcoming':
        query = query.filter(Activity.activity_date > today)
    elif date_filter == 'past':
        query = query.filter(Activity.activity_date < today)

    query = query.order_by(Activity.activity_date.desc(), Activity.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    activities = pagination.items

    base_scoped = Activity.get_scoped_query(current_user)
    total_count = base_scoped.count()
    calls_count = base_scoped.filter_by(activity_type=ActivityType.CALL).count()
    meetings_count = base_scoped.filter_by(activity_type=ActivityType.MEETING).count()
    emails_count = base_scoped.filter_by(activity_type=ActivityType.EMAIL).count()
    tasks_count = base_scoped.filter_by(activity_type=ActivityType.TASK).count()
    completed_count = base_scoped.filter_by(status=ActivityStatus.COMPLETED).count()

    return render_template(
        'activities/index.html',
        activities=activities,
        pagination=pagination,
        search_query=search_query,
        type_filter=target_type,
        status_filter=status_filter,
        date_filter=date_filter,
        ActivityType=ActivityType,
        ActivityStatus=ActivityStatus,
        total_count=total_count,
        calls_count=calls_count,
        meetings_count=meetings_count,
        emails_count=emails_count,
        tasks_count=tasks_count,
        completed_count=completed_count,
        active_view=view_slug,
        type_title=target_type
    )


@activity_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    Create a new activity (Call, Meeting, Email, Task).
    Supports pre-populating type, customer_id, or lead_id from URL query parameters.
    Generates ACTIVITY_CREATE audit event.
    """
    form = ActivityForm()
    populate_activity_form_choices(form)

    if request.method == 'GET':
        pre_type = request.args.get('type', '').strip()
        if pre_type in ActivityType.ALL_TYPES:
            form.activity_type.data = pre_type
        pre_cust = request.args.get('customer_id', type=int)
        if pre_cust:
            form.customer_id.data = pre_cust
        pre_lead = request.args.get('lead_id', type=int)
        if pre_lead:
            form.lead_id.data = pre_lead

        form.assigned_to.data = current_user.id
        form.activity_date.data = date.today()
        form.status.data = ActivityStatus.PENDING

    if form.validate_on_submit():
        new_activity = Activity(
            activity_type=form.activity_type.data,
            subject=form.subject.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            activity_date=form.activity_date.data,
            status=form.status.data or ActivityStatus.PENDING,
            customer_id=form.customer_id.data if form.customer_id.data > 0 else None,
            lead_id=form.lead_id.data if form.lead_id.data > 0 else None,
            assigned_to=form.assigned_to.data,
            created_by=current_user.id
        )

        db.session.add(new_activity)
        db.session.commit()

        # Audit event
        log_activity_event(
            action=AuditEventType.ACTIVITY_CREATE,
            activity_id=new_activity.id,
            user_id=current_user.id,
            old_value=None,
            new_value=new_activity.to_dict(),
            details=f"Created {new_activity.activity_type} activity: '{new_activity.subject}'"
        )

        flash(f"Activity '{new_activity.subject}' ({new_activity.activity_type}) created successfully.", "success")
        return redirect(url_for('activity.details', id=new_activity.id))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('activities/create.html', form=form), status_code


@activity_bp.route('/details/<int:id>')
@login_required
def details(id):
    """View complete activity details and relationships."""
    activity = Activity.query.get_or_404(id)

    if not activity.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to access this activity.", "danger")
        return redirect(url_for('auth.access_denied'))

    complete_form = CompleteActivityForm()
    cancel_form = CancelActivityForm()

    return render_template(
        'activities/details.html',
        activity=activity,
        complete_form=complete_form,
        cancel_form=cancel_form,
        can_manage=activity.can_be_managed_by(current_user)
    )


@activity_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """
    Edit activity details.
    Generates ACTIVITY_UPDATE audit event.
    """
    activity = Activity.query.get_or_404(id)

    if not activity.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to edit this activity.", "danger")
        return redirect(url_for('auth.access_denied'))

    form = ActivityForm(obj=activity)
    populate_activity_form_choices(form)

    if request.method == 'GET':
        form.customer_id.data = activity.customer_id or 0
        form.lead_id.data = activity.lead_id or 0
        form.assigned_to.data = activity.assigned_to

    if form.validate_on_submit():
        old_state = activity.to_dict()

        activity.activity_type = form.activity_type.data
        activity.subject = form.subject.data.strip()
        activity.description = form.description.data.strip() if form.description.data else None
        activity.activity_date = form.activity_date.data
        activity.status = form.status.data
        activity.customer_id = form.customer_id.data if form.customer_id.data > 0 else None
        activity.lead_id = form.lead_id.data if form.lead_id.data > 0 else None
        activity.assigned_to = form.assigned_to.data

        db.session.commit()
        new_state = activity.to_dict()

        # Audit event
        log_activity_event(
            action=AuditEventType.ACTIVITY_UPDATE,
            activity_id=activity.id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=new_state,
            details=f"Updated activity #{activity.id} ('{activity.subject}')"
        )

        flash(f"Activity '{activity.subject}' successfully updated.", "success")
        return redirect(url_for('activity.details', id=activity.id))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('activities/edit.html', form=form, activity=activity), status_code


@activity_bp.route('/complete/<int:id>', methods=['GET', 'POST'])
@login_required
def complete(id):
    """
    Mark an activity as Completed.
    Records completion timestamp and optional outcome notes.
    Generates ACTIVITY_COMPLETE audit event.
    """
    activity = Activity.query.get_or_404(id)

    if not activity.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to complete this activity.", "danger")
        return redirect(url_for('auth.access_denied'))

    form = CompleteActivityForm()

    if form.validate_on_submit() or request.method == 'POST':
        old_state = activity.to_dict()

        activity.status = ActivityStatus.COMPLETED
        activity.completed_date = datetime.utcnow()
        if form.completion_remarks.data:
            activity.completion_remarks = form.completion_remarks.data.strip()

        db.session.commit()
        new_state = activity.to_dict()

        # Audit event
        log_activity_event(
            action=AuditEventType.ACTIVITY_COMPLETE,
            activity_id=activity.id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=new_state,
            details=f"Marked activity #{activity.id} as Completed"
        )

        flash(f"Activity '{activity.subject}' marked as Completed.", "success")
        return redirect(url_for('activity.details', id=activity.id))

    return render_template('activities/complete.html', form=form, activity=activity)


@activity_bp.route('/cancel/<int:id>', methods=['GET', 'POST'])
@login_required
def cancel(id):
    """
    Mark an activity as Cancelled with mandatory reason.
    Generates ACTIVITY_CANCEL audit event.
    """
    activity = Activity.query.get_or_404(id)

    if not activity.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to cancel this activity.", "danger")
        return redirect(url_for('auth.access_denied'))

    form = CancelActivityForm()

    if form.validate_on_submit():
        old_state = activity.to_dict()

        activity.status = ActivityStatus.CANCELLED
        activity.cancellation_reason = form.cancellation_reason.data.strip()

        db.session.commit()
        new_state = activity.to_dict()

        # Audit event
        log_activity_event(
            action=AuditEventType.ACTIVITY_CANCEL,
            activity_id=activity.id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=new_state,
            details=f"Cancelled activity #{activity.id}. Reason: {activity.cancellation_reason}"
        )

        flash(f"Activity '{activity.subject}' has been Cancelled.", "warning")
        return redirect(url_for('activity.details', id=activity.id))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('activities/cancel.html', form=form, activity=activity), status_code


@activity_bp.route('/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete(id):
    """Delete an activity with confirmation and authorization check."""
    activity = Activity.query.get_or_404(id)

    if not activity.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to delete this activity.", "danger")
        return redirect(url_for('auth.access_denied'))

    if request.method == 'POST':
        old_state = activity.to_dict()
        act_id = activity.id
        act_subj = activity.subject

        db.session.delete(activity)
        db.session.commit()

        # Audit event
        log_activity_event(
            action=AuditEventType.ACTIVITY_DELETE,
            activity_id=act_id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=None,
            details=f"Deleted activity #{act_id} ('{act_subj}')"
        )

        flash(f"Activity '{act_subj}' was successfully deleted.", "info")
        return redirect(url_for('activity.index'))

    return render_template('activities/delete.html', activity=activity)
