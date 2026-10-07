from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models.opportunity import Opportunity, OpportunityStage, OpportunityStatus, OpportunitySource
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.user import User, Role
from app.forms.opportunity_forms import OpportunityForm
from app.services.audit_service import log_opportunity_event, AuditEventType

opportunity_bp = Blueprint('opportunity', __name__, url_prefix='/opportunities')


def populate_form_choices(form):
    """Populate Customer, Lead, and User choices for Opportunity forms."""
    customers = Customer.query.order_by(Customer.customer_name.asc()).all()
    form.customer_id.choices = [(0, '— Select Customer / Account —')] + [
        (c.id, f"{c.customer_name} ({c.customer_code})") for c in customers
    ]

    leads = Lead.query.order_by(Lead.lead_name.asc()).all()
    form.lead_id.choices = [(0, '— Direct Deal / No Originating Lead —')] + [
        (l.id, f"{l.lead_name} ({l.lead_code})") for l in leads
    ]

    users = User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    form.assigned_to.choices = [(0, '— Unassigned —')] + [
        (u.id, f"{u.full_name} ({u.role})") for u in users
    ]


@opportunity_bp.route('', strict_slashes=False)
@opportunity_bp.route('/', strict_slashes=False)
@login_required
def index():
    """
    Opportunity Listing page with:
    - Search by OpportunityName, Customer, Lead, Owner
    - Filter by Stage, Status, Close-Date range
    - Weighted Value calculation & totals
    - Role-based scoping (Admin/Manager: Full; SalesExecutive: Assigned/Own)
    - Sorting and Pagination
    """
    search_query = request.args.get('q', '').strip()
    stage_filter = request.args.get('stage', '').strip()
    status_filter = request.args.get('status', '').strip()
    sort_by = request.args.get('sort', 'created_date').strip()
    direction = request.args.get('dir', 'desc').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Start with role-scoped query
    query = Opportunity.get_scoped_query(current_user)

    # Search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.outerjoin(Customer, Opportunity.customer_id == Customer.id)\
                     .outerjoin(Lead, Opportunity.lead_id == Lead.id)\
                     .outerjoin(User, Opportunity.assigned_to == User.id)\
                     .filter(
                         or_(
                             Opportunity.opportunity_name.ilike(search_pattern),
                             Opportunity.opportunity_code.ilike(search_pattern),
                             Customer.customer_name.ilike(search_pattern),
                             Lead.lead_name.ilike(search_pattern),
                             User.full_name.ilike(search_pattern)
                         )
                     )

    # Stage filter
    if stage_filter and stage_filter != 'All':
        query = query.filter(Opportunity.stage == stage_filter)

    # Status filter
    if status_filter and status_filter != 'All':
        query = query.filter(Opportunity.status == status_filter)

    # Sorting
    sort_column = getattr(Opportunity, sort_by, Opportunity.created_date)
    if direction == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    opportunities = pagination.items

    # Server-side summary metrics
    scoped_all = Opportunity.get_scoped_query(current_user).all()
    total_pipeline = sum(o.amount for o in scoped_all if o.stage not in (OpportunityStage.WON, OpportunityStage.LOST))
    total_weighted = sum(o.weighted_value for o in scoped_all if o.stage not in (OpportunityStage.WON, OpportunityStage.LOST))
    total_won = sum(o.amount for o in scoped_all if o.stage == OpportunityStage.WON)

    return render_template(
        'opportunities/index.html',
        opportunities=opportunities,
        pagination=pagination,
        search_query=search_query,
        stage_filter=stage_filter,
        status_filter=status_filter,
        sort_by=sort_by,
        direction=direction,
        all_stages=OpportunityStage.ALL_STAGES,
        all_statuses=OpportunityStatus.ALL_STATUSES,
        total_pipeline=total_pipeline,
        total_weighted=total_weighted,
        total_won=total_won,
        is_scoped=(current_user.role == Role.SALES_EXECUTIVE)
    )


@opportunity_bp.route('/pipeline')
@login_required
def pipeline():
    """
    Sales Pipeline Visual View:
    Displays opportunities grouped by stage:
    Qualification, Proposal, Negotiation, Won, Lost
    Shows opportunity name, customer, lead, owner, stage, amount, probability, close date, weighted value.
    Server-side calculated summary metrics.
    """
    scoped_all = Opportunity.get_scoped_query(current_user).all()

    # Group deals by configured stages
    pipeline_groups = {
        OpportunityStage.QUALIFICATION: [],
        OpportunityStage.PROPOSAL: [],
        OpportunityStage.NEGOTIATION: [],
        OpportunityStage.WON: [],
        OpportunityStage.LOST: []
    }

    stage_totals = {stage: {'amount': 0.0, 'weighted': 0.0, 'count': 0} for stage in pipeline_groups}

    for opp in scoped_all:
        target_stage = opp.stage if opp.stage in pipeline_groups else OpportunityStage.QUALIFICATION
        pipeline_groups[target_stage].append(opp)
        stage_totals[target_stage]['amount'] += float(opp.amount or 0.0)
        stage_totals[target_stage]['weighted'] += float(opp.weighted_value or 0.0)
        stage_totals[target_stage]['count'] += 1

    total_active_value = sum(
        stage_totals[s]['amount'] for s in [OpportunityStage.QUALIFICATION, OpportunityStage.PROPOSAL, OpportunityStage.NEGOTIATION]
    )
    total_active_weighted = sum(
        stage_totals[s]['weighted'] for s in [OpportunityStage.QUALIFICATION, OpportunityStage.PROPOSAL, OpportunityStage.NEGOTIATION]
    )
    won_total = stage_totals[OpportunityStage.WON]['amount']

    return render_template(
        'opportunities/pipeline.html',
        pipeline_groups=pipeline_groups,
        stage_totals=stage_totals,
        stages=OpportunityStage.ALL_STAGES,
        total_active_value=total_active_value,
        total_active_weighted=total_active_weighted,
        won_total=won_total,
        is_scoped=(current_user.role == Role.SALES_EXECUTIVE)
    )


@opportunity_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new opportunity with strict business validation."""
    form = OpportunityForm()
    populate_form_choices(form)

    # Default assigned_to to current user
    if request.method == 'GET':
        if not form.assigned_to.data:
            form.assigned_to.data = current_user.id
        if not form.expected_close_date.data:
            form.expected_close_date.data = date.today()

    if form.validate_on_submit():
        lead_id_val = form.lead_id.data if form.lead_id.data and form.lead_id.data > 0 else None
        assigned_to_val = form.assigned_to.data if form.assigned_to.data and form.assigned_to.data > 0 else None
        cust_id_val = form.customer_id.data if form.customer_id.data and form.customer_id.data > 0 else None

        if not cust_id_val:
            flash("A valid Customer must be selected.", "danger")
            return render_template('opportunities/create.html', form=form), 400

        new_opp = Opportunity(
            opportunity_code=form.opportunity_code.data.strip(),
            opportunity_name=form.opportunity_name.data.strip(),
            customer_id=cust_id_val,
            lead_id=lead_id_val,
            amount=float(form.amount.data),
            probability=int(form.probability.data),
            stage=form.stage.data,
            status=form.status.data,
            expected_close_date=form.expected_close_date.data,
            source=form.source.data,
            notes=form.notes.data.strip() if form.notes.data else None,
            created_by=current_user.id,
            assigned_to=assigned_to_val
        )

        db.session.add(new_opp)
        db.session.commit()

        # Audit event
        log_opportunity_event(
            action=AuditEventType.OPPORTUNITY_CREATE,
            opportunity_id=new_opp.id,
            user_id=current_user.id,
            old_value=None,
            new_value=new_opp.to_dict(),
            details=f"Created opportunity '{new_opp.opportunity_name}' ({new_opp.opportunity_code}) for ${new_opp.amount}"
        )

        flash(f"Opportunity '{new_opp.opportunity_name}' created successfully.", "success")
        return redirect(url_for('opportunity.details', id=new_opp.id))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('opportunities/create.html', form=form), status_code


@opportunity_bp.route('/details/<int:id>')
@login_required
def details(id):
    """View complete opportunity details, linked Customer, originating Lead, and weighted value."""
    opp = Opportunity.query.get_or_404(id)

    if not opp.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to access this opportunity.", "danger")
        return redirect(url_for('auth.access_denied'))

    return render_template(
        'opportunities/details.html',
        opp=opp,
        can_manage=opp.can_be_managed_by(current_user)
    )


@opportunity_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """
    Edit opportunity record.
    Generates OPPORTUNITY_UPDATE, OPPORTUNITY_STAGE_CHANGE, OPPORTUNITY_STATUS_CHANGE audit events.
    """
    opp = Opportunity.query.get_or_404(id)

    if not opp.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to edit this opportunity.", "danger")
        return redirect(url_for('auth.access_denied'))

    form = OpportunityForm(original_opportunity=opp, obj=opp)
    populate_form_choices(form)

    if form.validate_on_submit():
        old_state = opp.to_dict()
        old_stage = opp.stage
        old_status = opp.status

        lead_id_val = form.lead_id.data if form.lead_id.data and form.lead_id.data > 0 else None
        assigned_to_val = form.assigned_to.data if form.assigned_to.data and form.assigned_to.data > 0 else None
        cust_id_val = form.customer_id.data if form.customer_id.data and form.customer_id.data > 0 else None

        opp.opportunity_code = form.opportunity_code.data.strip()
        opp.opportunity_name = form.opportunity_name.data.strip()
        opp.customer_id = cust_id_val
        opp.lead_id = lead_id_val
        opp.amount = float(form.amount.data)
        opp.probability = int(form.probability.data)
        opp.stage = form.stage.data
        opp.status = form.status.data
        opp.expected_close_date = form.expected_close_date.data
        opp.source = form.source.data
        opp.assigned_to = assigned_to_val
        opp.notes = form.notes.data.strip() if form.notes.data else None

        db.session.commit()
        new_state = opp.to_dict()

        # Audit events
        log_opportunity_event(
            action=AuditEventType.OPPORTUNITY_UPDATE,
            opportunity_id=opp.id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=new_state,
            details=f"Updated opportunity '{opp.opportunity_name}'"
        )

        if old_stage != opp.stage:
            log_opportunity_event(
                action=AuditEventType.OPPORTUNITY_STAGE_CHANGE,
                opportunity_id=opp.id,
                user_id=current_user.id,
                old_value={'Stage': old_stage},
                new_value={'Stage': opp.stage},
                details=f"Stage changed from {old_stage} to {opp.stage}"
            )

        if old_status != opp.status:
            log_opportunity_event(
                action=AuditEventType.OPPORTUNITY_STATUS_CHANGE,
                opportunity_id=opp.id,
                user_id=current_user.id,
                old_value={'Status': old_status},
                new_value={'Status': opp.status},
                details=f"Status changed from {old_status} to {opp.status}"
            )

        flash(f"Opportunity '{opp.opportunity_name}' updated successfully.", "success")
        return redirect(url_for('opportunity.details', id=opp.id))

    status_code = 400 if request.method == 'POST' else 200
    return render_template('opportunities/edit.html', form=form, opp=opp), status_code


@opportunity_bp.route('/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete(id):
    """Delete an opportunity with confirmation and authorization check."""
    opp = Opportunity.query.get_or_404(id)

    if not opp.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to delete this opportunity.", "danger")
        return redirect(url_for('auth.access_denied'))

    if request.method == 'POST':
        old_state = opp.to_dict()
        opp_id = opp.id
        opp_name = opp.opportunity_name

        db.session.delete(opp)
        db.session.commit()

        log_opportunity_event(
            action=AuditEventType.OPPORTUNITY_DELETE,
            opportunity_id=opp_id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=None,
            details=f"Deleted opportunity '{opp_name}' (ID: #{opp_id})"
        )

        flash(f"Opportunity '{opp_name}' was successfully deleted.", "info")
        return redirect(url_for('opportunity.index'))

    return render_template('opportunities/delete.html', opportunity=opp)
