"""
Follow-Up Management Routes for Acxiom CRM.
Implements:
- /follow-ups (List with search and filter)
- /follow-ups/pending (Pending & Overdue follow-ups view)
- /follow-ups/schedule & /follow-ups/create (Schedule new follow-up)
- /follow-ups/details/<id> (Follow-up details)
- /follow-ups/edit/<id> (Edit follow-up)
- /follow-ups/complete/<id> (Complete follow-up)
- /follow-ups/reschedule/<id> (Reschedule follow-up)
- /follow-ups/mark-missed/<id> (Mark follow-up as missed)
- /follow-ups/delete/<id> (Delete with confirmation)
"""
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import or_, and_

from app.extensions import db
from app.models.follow_up import FollowUp, FollowUpType, FollowUpStatus
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.user import User, Role
from app.forms.follow_up_forms import FollowUpForm, CompleteFollowUpForm, RescheduleFollowUpForm
from app.services.audit_service import log_follow_up_event, AuditEventType

follow_up_bp = Blueprint('follow_up', __name__, url_prefix='/follow-ups')


def populate_form_choices(form):
    """Populate dynamic choices for Customers, Leads, and Users."""
    customers = Customer.query.order_by(Customer.customer_name.asc()).all()
    form.customer_id.choices = [(0, '— None (Lead only) —')] + [
        (c.id, f"{c.customer_name} ({c.customer_code})") for c in customers
    ]

    leads = Lead.query.order_by(Lead.lead_name.asc()).all()
    form.lead_id.choices = [(0, '— None (Customer only) —')] + [
        (l.id, f"{l.lead_name} ({l.lead_code})") for l in leads
    ]

    users = User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    form.assigned_to.choices = [(u.id, f"{u.full_name} ({u.role})") for u in users]


@follow_up_bp.route('', strict_slashes=False)
@follow_up_bp.route('/', strict_slashes=False)
@login_required
def index():
    """
    Follow-Up List view with search, filtering, and pagination.
    Supports filtering by type, status, and date category.
    """
    search_query = request.args.get('q', '').strip()
    type_filter = request.args.get('type', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_filter = request.args.get('date_filter', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 15

    query = FollowUp.get_scoped_query(current_user)

    # Search keyword in remarks, customer name, lead name
    if search_query:
        query = query.outerjoin(Customer, FollowUp.customer_id == Customer.id)\
                     .outerjoin(Lead, FollowUp.lead_id == Lead.id)\
                     .filter(
                         or_(
                             FollowUp.remarks.ilike(f'%{search_query}%'),
                             FollowUp.follow_up_type.ilike(f'%{search_query}%'),
                             Customer.customer_name.ilike(f'%{search_query}%'),
                             Customer.customer_code.ilike(f'%{search_query}%'),
                             Lead.lead_name.ilike(f'%{search_query}%'),
                             Lead.lead_code.ilike(f'%{search_query}%')
                         )
                     )

    # Filter by Type
    if type_filter and type_filter in FollowUpType.ALL_TYPES:
        query = query.filter(FollowUp.follow_up_type == type_filter)

    # Filter by Status
    if status_filter and status_filter in FollowUpStatus.ALL_STATUSES:
        query = query.filter(FollowUp.status == status_filter)

    # Filter by Date
    today = date.today()
    if date_filter == 'today':
        query = query.filter(FollowUp.follow_up_date == today)
    elif date_filter == 'upcoming':
        query = query.filter(FollowUp.follow_up_date > today)
    elif date_filter == 'overdue':
        query = query.filter(
            FollowUp.follow_up_date < today,
            FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.RESCHEDULED])
        )

    # Order by follow_up_date ascending for active, descending for completed
    query = query.order_by(FollowUp.follow_up_date.asc(), FollowUp.id.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    follow_ups = pagination.items

    # Compute summary metrics scoped to current user
    base_scoped = FollowUp.get_scoped_query(current_user)
    total_count = base_scoped.count()
    pending_count = base_scoped.filter(FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.RESCHEDULED])).count()
    completed_count = base_scoped.filter_by(status=FollowUpStatus.COMPLETED).count()
    missed_count = base_scoped.filter_by(status=FollowUpStatus.MISSED).count()
    today_count = base_scoped.filter(
        FollowUp.follow_up_date == today,
        FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.RESCHEDULED])
    ).count()

    return render_template(
        'follow_ups/index.html',
        follow_ups=follow_ups,
        pagination=pagination,
        search_query=search_query,
        type_filter=type_filter,
        status_filter=status_filter,
        date_filter=date_filter,
        FollowUpType=FollowUpType,
        FollowUpStatus=FollowUpStatus,
        total_count=total_count,
        pending_count=pending_count,
        completed_count=completed_count,
        missed_count=missed_count,
        today_count=today_count,
        today=today
    )


@follow_up_bp.route('/pending')
@login_required
def pending():
    """
    Dedicated view for Pending & Rescheduled follow-ups.
    Clearly flags overdue vs today vs upcoming items.
    """
    type_filter = request.args.get('type', '').strip()
    assigned_filter = request.args.get('assigned_to', type=int)
    customer_filter = request.args.get('customer_id', type=int)
    lead_filter = request.args.get('lead_id', type=int)
    date_filter = request.args.get('date_filter', '').strip()

    today = date.today()

    query = FollowUp.get_scoped_query(current_user).filter(
        FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.RESCHEDULED])
    )

    if type_filter and type_filter in FollowUpType.ALL_TYPES:
        query = query.filter(FollowUp.follow_up_type == type_filter)
    if assigned_filter:
        query = query.filter(FollowUp.assigned_to == assigned_filter)
    if customer_filter:
        query = query.filter(FollowUp.customer_id == customer_filter)
    if lead_filter:
        query = query.filter(FollowUp.lead_id == lead_filter)

    if date_filter == 'overdue':
        query = query.filter(FollowUp.follow_up_date < today)
    elif date_filter == 'today':
        query = query.filter(FollowUp.follow_up_date == today)
    elif date_filter == 'upcoming':
        query = query.filter(FollowUp.follow_up_date > today)

    # Sort overdue first, then by date
    pending_items = query.order_by(FollowUp.follow_up_date.asc()).all()

    # Partition for high-visibility UI groups
    overdue_items = [f for f in pending_items if f.follow_up_date < today]
    today_items = [f for f in pending_items if f.follow_up_date == today]
    upcoming_items = [f for f in pending_items if f.follow_up_date > today]

    # Dropdown choices for filter bar
    active_users = User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    customers = Customer.query.order_by(Customer.customer_name.asc()).all()
    leads = Lead.query.order_by(Lead.lead_name.asc()).all()

    return render_template(
        'follow_ups/pending.html',
        pending_items=pending_items,
        overdue_items=overdue_items,
        today_items=today_items,
        upcoming_items=upcoming_items,
        today=today,
        type_filter=type_filter,
        assigned_filter=assigned_filter,
        customer_filter=customer_filter,
        lead_filter=lead_filter,
        date_filter=date_filter,
        FollowUpType=FollowUpType,
        FollowUpStatus=FollowUpStatus,
        active_users=active_users,
        customers=customers,
        leads=leads
    )


@follow_up_bp.route('/schedule', methods=['GET', 'POST'])
@follow_up_bp.route('/create', methods=['GET', 'POST'])
@login_required
def schedule():
    """
    Schedule a new follow-up.
    Maintains Customer/Lead relationship, validates future date, type, status, and assignee.
    Generates FOLLOWUP_CREATE audit event.
    """
    form = FollowUpForm()
    populate_form_choices(form)

    # Pre-select customer or lead from query parameters if provided
    if request.method == 'GET':
        pre_cust = request.args.get('customer_id', type=int)
        pre_lead = request.args.get('lead_id', type=int)
        if pre_cust:
            form.customer_id.data = pre_cust
        if pre_lead:
            form.lead_id.data = pre_lead
        form.assigned_to.data = current_user.id
        form.follow_up_date.data = date.today()
        form.status.data = FollowUpStatus.PENDING

    if form.validate_on_submit():
        new_follow_up = FollowUp(
            customer_id=form.customer_id.data if form.customer_id.data > 0 else None,
            lead_id=form.lead_id.data if form.lead_id.data > 0 else None,
            follow_up_date=form.follow_up_date.data,
            follow_up_type=form.follow_up_type.data,
            remarks=form.remarks.data.strip() if form.remarks.data else None,
            status=form.status.data or FollowUpStatus.PENDING,
            assigned_to=form.assigned_to.data,
            created_by=current_user.id
        )

        db.session.add(new_follow_up)
        db.session.commit()

        # Generate FOLLOWUP_CREATE audit event
        log_follow_up_event(
            action=AuditEventType.FOLLOWUP_CREATE,
            follow_up_id=new_follow_up.id,
            user_id=current_user.id,
            old_value=None,
            new_value=new_follow_up.to_dict(),
            details=f"Scheduled {new_follow_up.follow_up_type} for {new_follow_up.follow_up_date}"
        )

        flash(f"Follow-up ({new_follow_up.follow_up_type}) successfully scheduled for {new_follow_up.follow_up_date}.", "success")
        return redirect(url_for('follow_up.details', id=new_follow_up.id))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('follow_ups/schedule.html', form=form), status_code


@follow_up_bp.route('/details/<int:id>')
@login_required
def details(id):
    """View complete follow-up details with timeline and actions."""
    follow_up = FollowUp.query.get_or_404(id)

    if not follow_up.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to access this follow-up.", "danger")
        return redirect(url_for('auth.access_denied'))

    complete_form = CompleteFollowUpForm()
    reschedule_form = RescheduleFollowUpForm(follow_up_date=date.today())

    return render_template(
        'follow_ups/details.html',
        follow_up=follow_up,
        complete_form=complete_form,
        reschedule_form=reschedule_form,
        today=date.today(),
        can_manage=follow_up.can_be_managed_by(current_user)
    )


@follow_up_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """
    Edit follow-up record.
    Generates FOLLOWUP_UPDATE audit event.
    """
    follow_up = FollowUp.query.get_or_404(id)

    if not follow_up.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to edit this follow-up.", "danger")
        return redirect(url_for('auth.access_denied'))

    form = FollowUpForm(original_follow_up=follow_up, obj=follow_up)
    populate_form_choices(form)

    if request.method == 'GET':
        form.customer_id.data = follow_up.customer_id or 0
        form.lead_id.data = follow_up.lead_id or 0
        form.assigned_to.data = follow_up.assigned_to

    if form.validate_on_submit():
        old_state = follow_up.to_dict()

        follow_up.customer_id = form.customer_id.data if form.customer_id.data > 0 else None
        follow_up.lead_id = form.lead_id.data if form.lead_id.data > 0 else None
        follow_up.follow_up_date = form.follow_up_date.data
        follow_up.follow_up_type = form.follow_up_type.data
        follow_up.status = form.status.data
        follow_up.assigned_to = form.assigned_to.data
        follow_up.remarks = form.remarks.data.strip() if form.remarks.data else None

        db.session.commit()
        new_state = follow_up.to_dict()

        # Audit event
        log_follow_up_event(
            action=AuditEventType.FOLLOWUP_UPDATE,
            follow_up_id=follow_up.id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=new_state,
            details=f"Updated follow-up #{follow_up.id}"
        )

        flash("Follow-up successfully updated.", "success")
        return redirect(url_for('follow_up.details', id=follow_up.id))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('follow_ups/edit.html', form=form, follow_up=follow_up), status_code


@follow_up_bp.route('/complete/<int:id>', methods=['GET', 'POST'])
@login_required
def complete(id):
    """
    Mark a pending or rescheduled follow-up as Completed.
    Preserves original follow-up details and records outcome remarks.
    Generates FOLLOWUP_COMPLETE audit event.
    """
    follow_up = FollowUp.query.get_or_404(id)

    if not follow_up.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to complete this follow-up.", "danger")
        return redirect(url_for('auth.access_denied'))

    form = CompleteFollowUpForm()

    if form.validate_on_submit() or request.method == 'POST':
        old_state = follow_up.to_dict()

        follow_up.status = FollowUpStatus.COMPLETED
        follow_up.completed_date = datetime.utcnow()
        if form.completion_remarks.data:
            follow_up.completion_remarks = form.completion_remarks.data.strip()

        db.session.commit()
        new_state = follow_up.to_dict()

        # Audit event
        log_follow_up_event(
            action=AuditEventType.FOLLOWUP_COMPLETE,
            follow_up_id=follow_up.id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=new_state,
            details=f"Completed follow-up #{follow_up.id} ({follow_up.follow_up_type})"
        )

        flash(f"Follow-up #{follow_up.id} has been marked as Completed.", "success")
        return redirect(url_for('follow_up.details', id=follow_up.id))

    return render_template('follow_ups/complete.html', form=form, follow_up=follow_up)


@follow_up_bp.route('/reschedule/<int:id>', methods=['GET', 'POST'])
@login_required
def reschedule(id):
    """
    Reschedule a follow-up.
    Updates follow_up_date (must not be in the past) and sets status to Rescheduled.
    Preserves original follow-up record without creating unnecessary duplicates.
    Generates FOLLOWUP_RESCHEDULE audit event.
    """
    follow_up = FollowUp.query.get_or_404(id)

    if not follow_up.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to reschedule this follow-up.", "danger")
        return redirect(url_for('auth.access_denied'))

    form = RescheduleFollowUpForm(obj=follow_up)

    if form.validate_on_submit():
        old_state = follow_up.to_dict()

        new_date = form.follow_up_date.data
        if new_date < date.today():
            flash("New follow-up date must not be before today.", "danger")
            return render_template('follow_ups/reschedule.html', form=form, follow_up=follow_up), 400

        follow_up.follow_up_date = new_date
        follow_up.status = FollowUpStatus.RESCHEDULED
        if form.remarks.data:
            # Append or update remarks
            orig = follow_up.remarks or ''
            follow_up.remarks = f"{orig}\n[Rescheduled to {new_date}]: {form.remarks.data.strip()}".strip()

        db.session.commit()
        new_state = follow_up.to_dict()

        # Audit event
        log_follow_up_event(
            action=AuditEventType.FOLLOWUP_RESCHEDULE,
            follow_up_id=follow_up.id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=new_state,
            details=f"Rescheduled follow-up #{follow_up.id} to {new_date}"
        )

        flash(f"Follow-up successfully rescheduled to {new_date}.", "info")
        return redirect(url_for('follow_up.details', id=follow_up.id))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('follow_ups/reschedule.html', form=form, follow_up=follow_up), status_code


@follow_up_bp.route('/mark-missed/<int:id>', methods=['POST'])
@login_required
def mark_missed(id):
    """
    Mark an active overdue follow-up as Missed.
    Generates FOLLOWUP_MISSED audit event.
    """
    follow_up = FollowUp.query.get_or_404(id)

    if not follow_up.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to modify this follow-up.", "danger")
        return redirect(url_for('auth.access_denied'))

    old_state = follow_up.to_dict()
    follow_up.status = FollowUpStatus.MISSED

    db.session.commit()
    new_state = follow_up.to_dict()

    log_follow_up_event(
        action=AuditEventType.FOLLOWUP_MISSED,
        follow_up_id=follow_up.id,
        user_id=current_user.id,
        old_value=old_state,
        new_value=new_state,
        details=f"Marked follow-up #{follow_up.id} as Missed"
    )

    flash(f"Follow-up #{follow_up.id} marked as Missed.", "warning")
    return redirect(url_for('follow_up.details', id=follow_up.id))


@follow_up_bp.route('/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete(id):
    """Delete a follow-up with confirmation and authorization check."""
    follow_up = FollowUp.query.get_or_404(id)

    if not follow_up.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to delete this follow-up.", "danger")
        return redirect(url_for('auth.access_denied'))

    if request.method == 'POST':
        old_state = follow_up.to_dict()
        fid = follow_up.id
        ftype = follow_up.follow_up_type

        db.session.delete(follow_up)
        db.session.commit()

        # Audit event
        log_follow_up_event(
            action=AuditEventType.FOLLOWUP_DELETE,
            follow_up_id=fid,
            user_id=current_user.id,
            old_value=old_state,
            new_value=None,
            details=f"Deleted follow-up #{fid} ({ftype})"
        )

        flash(f"Follow-up #{fid} was successfully deleted.", "info")
        return redirect(url_for('follow_up.index'))

    return render_template('follow_ups/delete.html', follow_up=follow_up)
