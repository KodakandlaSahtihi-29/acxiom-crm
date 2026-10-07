from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.customer import Customer
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.user import User, Role
from app.forms.lead_forms import LeadForm, LeadConvertForm
from app.services.audit_service import log_lead_event, log_customer_event, log_opportunity_event, AuditEventType

lead_bp = Blueprint('lead', __name__, url_prefix='/leads')


def populate_user_choices(form):
    """Populate active user choices for lead assignment."""
    users = User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    form.assigned_to.choices = [(0, '— Unassigned —')] + [(u.id, f"{u.full_name} ({u.role})") for u in users]


@lead_bp.route('', strict_slashes=False)
@lead_bp.route('/', strict_slashes=False)
@login_required
def index():
    """
    Lead Listing page with:
    - Search by LeadName, Email, Phone, CompanyName
    - Filter by Source and Status
    - Sorting and Pagination
    - Role-based scoping (Admin/Manager: Full; SalesExecutive: Assigned/Own)
    """
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    source_filter = request.args.get('source', '').strip()
    sort_by = request.args.get('sort', 'created_date').strip()
    direction = request.args.get('dir', 'desc').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Role-scoped base query
    query = Lead.get_scoped_query(current_user)

    # Search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Lead.lead_name.ilike(search_pattern),
                Lead.email.ilike(search_pattern),
                Lead.phone.ilike(search_pattern),
                Lead.company_name.ilike(search_pattern),
                Lead.lead_code.ilike(search_pattern)
            )
        )

    # Status filter
    if status_filter and status_filter != 'All':
        query = query.filter(Lead.status == status_filter)

    # Source filter
    if source_filter and source_filter != 'All':
        query = query.filter(Lead.source == source_filter)

    # Sorting
    sort_column = getattr(Lead, sort_by, Lead.created_date)
    if direction == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    leads = pagination.items

    return render_template(
        'leads/index.html',
        leads=leads,
        pagination=pagination,
        search_query=search_query,
        status_filter=status_filter,
        source_filter=source_filter,
        sort_by=sort_by,
        direction=direction,
        all_statuses=LeadStatus.ALL_STATUSES,
        all_sources=LeadSource.ALL_SOURCES,
        is_scoped=(current_user.role == Role.SALES_EXECUTIVE)
    )


@lead_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    Create a new lead.
    Enforces validation, assigns creator and optional assignee.
    Generates LEAD_CREATE audit event.
    """
    form = LeadForm()
    populate_user_choices(form)

    # Default assigned_to to current user
    if request.method == 'GET' and not form.assigned_to.data:
        form.assigned_to.data = current_user.id

    if form.validate_on_submit():
        # Validate status against configured statuses
        if form.status.data not in LeadStatus.ALL_STATUSES:
            flash(f"Invalid status '{form.status.data}'.", "danger")
            return render_template('leads/create.html', form=form), 400

        assignee_id = form.assigned_to.data if form.assigned_to.data and form.assigned_to.data > 0 else None

        new_lead = Lead(
            lead_code=form.lead_code.data.strip(),
            lead_name=form.lead_name.data.strip(),
            email=form.email.data.strip().lower() if form.email.data else None,
            phone=form.phone.data.strip() if form.phone.data else None,
            company_name=form.company_name.data.strip() if form.company_name.data else None,
            source=form.source.data,
            status=form.status.data,
            expected_value=float(form.expected_value.data or 0.0),
            created_by=current_user.id,
            assigned_to=assignee_id
        )

        db.session.add(new_lead)
        db.session.commit()

        # Audit logging
        log_lead_event(
            action=AuditEventType.LEAD_CREATE,
            lead_id=new_lead.id,
            user_id=current_user.id,
            old_value=None,
            new_value=new_lead.to_dict(),
            details=f"Created lead '{new_lead.lead_name}' ({new_lead.lead_code})"
        )

        flash(f"Lead '{new_lead.lead_name}' created successfully.", "success")
        return redirect(url_for('lead.details', id=new_lead.id))

    return render_template('leads/create.html', form=form)


@lead_bp.route('/details/<int:id>')
@login_required
def details(id):
    """View lead details and conversion status."""
    lead = Lead.query.get_or_404(id)

    # Scoping check
    if not lead.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to access this lead.", "danger")
        return redirect(url_for('auth.access_denied'))

    return render_template(
        'leads/details.html',
        lead=lead,
        can_manage=lead.can_be_managed_by(current_user),
        can_convert=lead.can_be_converted()
    )


@lead_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """
    Edit lead details and enforce valid status workflow transitions.
    Generates LEAD_UPDATE and LEAD_STATUS_CHANGE audit events.
    """
    lead = Lead.query.get_or_404(id)

    if not lead.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to edit this lead.", "danger")
        return redirect(url_for('auth.access_denied'))

    form = LeadForm(original_lead=lead, obj=lead)
    populate_user_choices(form)

    if form.validate_on_submit():
        old_state = lead.to_dict()
        old_status = lead.status
        new_status = form.status.data

        # Enforce valid workflow transitions
        if old_status != new_status:
            is_valid, err_msg = Lead.is_valid_status_transition(old_status, new_status)
            if not is_valid:
                flash(err_msg, "danger")
                return render_template('leads/edit.html', form=form, lead=lead), 400

        assignee_id = form.assigned_to.data if form.assigned_to.data and form.assigned_to.data > 0 else None

        lead.lead_code = form.lead_code.data.strip()
        lead.lead_name = form.lead_name.data.strip()
        lead.email = form.email.data.strip().lower() if form.email.data else None
        lead.phone = form.phone.data.strip() if form.phone.data else None
        lead.company_name = form.company_name.data.strip() if form.company_name.data else None
        lead.source = form.source.data
        lead.status = new_status
        lead.expected_value = float(form.expected_value.data or 0.0)
        lead.assigned_to = assignee_id

        db.session.commit()
        new_state = lead.to_dict()

        # Audit events
        log_lead_event(
            action=AuditEventType.LEAD_UPDATE,
            lead_id=lead.id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=new_state,
            details=f"Updated lead '{lead.lead_name}'"
        )

        if old_status != new_status:
            log_lead_event(
                action=AuditEventType.LEAD_STATUS_CHANGE,
                lead_id=lead.id,
                user_id=current_user.id,
                old_value={'Status': old_status},
                new_value={'Status': new_status},
                details=f"Status changed from {old_status} to {new_status}"
            )

        flash(f"Lead '{lead.lead_name}' updated successfully.", "success")
        return redirect(url_for('lead.details', id=lead.id))

    return render_template('leads/edit.html', form=form, lead=lead)


@lead_bp.route('/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete(id):
    """Delete a lead with confirmation and server-side authorization check."""
    lead = Lead.query.get_or_404(id)

    if not lead.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to delete this lead.", "danger")
        return redirect(url_for('auth.access_denied'))

    if request.method == 'POST':
        old_state = lead.to_dict()
        lead_id = lead.id
        lead_name = lead.lead_name

        db.session.delete(lead)
        db.session.commit()

        log_lead_event(
            action=AuditEventType.LEAD_DELETE,
            lead_id=lead_id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=None,
            details=f"Deleted lead '{lead_name}' (ID: #{lead_id})"
        )

        flash(f"Lead '{lead_name}' was successfully deleted.", "info")
        return redirect(url_for('lead.index'))

    return render_template('leads/delete.html', lead=lead)


@lead_bp.route('/convert/<int:id>', methods=['GET', 'POST'])
@login_required
def convert(id):
    """
    Lead Conversion:
    Converts qualified lead into a Customer and/or an Opportunity.
    Prevents duplicate customer creation.
    Preserves relationship to originating Lead using LeadId.
    """
    lead = Lead.query.get_or_404(id)

    if not lead.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to convert this lead.", "danger")
        return redirect(url_for('auth.access_denied'))

    if lead.status == LeadStatus.CONVERTED:
        flash(f"This lead was already converted on {lead.converted_date.strftime('%Y-%m-%d')}.", "warning")
        return redirect(url_for('lead.details', id=lead.id))

    form = LeadConvertForm()

    # Populate existing customers dropdown
    existing_customers = Customer.query.order_by(Customer.customer_name.asc()).all()
    form.existing_customer_id.choices = [(0, '— Create New Customer from Lead —')] + [
        (c.id, f"{c.customer_name} ({c.customer_code})") for c in existing_customers
    ]

    # Pre-populate defaults on GET
    if request.method == 'GET':
        form.customer_code.data = f"CUST-{lead.lead_code.replace('LEAD-', '')}"
        form.customer_name.data = lead.company_name or lead.lead_name
        form.opportunity_code = getattr(form, 'opportunity_code', None)
        if hasattr(form, 'opportunity_code') and form.opportunity_code:
            form.opportunity_code.data = f"OPP-{lead.lead_code.replace('LEAD-', '')}"
        form.opportunity_title.data = f"{lead.company_name or lead.lead_name} - Deal"
        form.opportunity_amount.data = lead.expected_value
        form.opportunity_stage.data = OpportunityStage.QUALIFICATION

    if form.validate_on_submit():
        target_customer = None

        # 1. Handle Customer Creation or Linking
        if form.convert_to_customer.data:
            chosen_cust_id = form.existing_customer_id.data

            if chosen_cust_id and chosen_cust_id > 0:
                # Link to existing customer selected
                target_customer = Customer.query.get(chosen_cust_id)
            else:
                # Create NEW Customer from Lead details
                cust_code = (form.customer_code.data or f"CUST-{lead.lead_code}").strip()
                cust_name = (form.customer_name.data or lead.company_name or lead.lead_name).strip()
                cust_email = (lead.email or f"{lead.lead_code.lower()}@customer.com").strip().lower()
                cust_phone = (lead.phone or "+1 555-0000").strip()

                # Check for duplicate customer email / phone
                dup_email = Customer.query.filter(Customer.email.ilike(cust_email)).first()
                if dup_email:
                    flash(f"Duplicate Customer Prevention: A customer with email '{cust_email}' already exists ({dup_email.customer_name}). Please select the existing customer or resolve the email conflict.", "danger")
                    return render_template('leads/convert.html', form=form, lead=lead), 400

                dup_phone = Customer.query.filter(Customer.phone == cust_phone).first()
                if dup_phone:
                    flash(f"Duplicate Customer Prevention: A customer with phone '{cust_phone}' already exists ({dup_phone.customer_name}). Please select the existing customer or resolve the phone conflict.", "danger")
                    return render_template('leads/convert.html', form=form, lead=lead), 400

                dup_code = Customer.query.filter(Customer.customer_code.ilike(cust_code)).first()
                if dup_code:
                    cust_code = f"{cust_code}-{lead.id}"

                target_customer = Customer(
                    customer_code=cust_code,
                    customer_name=cust_name,
                    email=cust_email,
                    phone=cust_phone,
                    company_name=lead.company_name,
                    status='Active',
                    created_by=current_user.id
                )
                db.session.add(target_customer)
                db.session.flush()  # Generate target_customer.id

                log_customer_event(
                    action=AuditEventType.CUSTOMER_CREATE,
                    customer_id=target_customer.id,
                    user_id=current_user.id,
                    old_value=None,
                    new_value=target_customer.to_dict(),
                    details=f"Created via conversion from Lead #{lead.id} ({lead.lead_code})"
                )

        # 2. Handle Opportunity Creation
        created_opp = None
        if form.create_opportunity.data:
            opp_code = (form.opportunity_code.data if hasattr(form, 'opportunity_code') and form.opportunity_code.data else f"OPP-{lead.lead_code}").strip()
            # Ensure unique code
            if Opportunity.query.filter(Opportunity.opportunity_code.ilike(opp_code)).first():
                opp_code = f"{opp_code}-{lead.id}"

            opp_title = (form.opportunity_title.data or f"{lead.lead_name} Opportunity").strip()
            opp_amount = float(form.opportunity_amount.data or 0.0)
            opp_stage = form.opportunity_stage.data or OpportunityStage.QUALIFICATION
            close_dt = form.close_date.data

            created_opp = Opportunity(
                opportunity_code=opp_code,
                title=opp_title,
                amount=opp_amount,
                stage=opp_stage,
                close_date=datetime.combine(close_dt, datetime.min.time()) if close_dt else None,
                lead_id=lead.id,  # Preserves relationship to originating Lead!
                customer_id=target_customer.id if target_customer else None,
                created_by=current_user.id,
                assigned_to=lead.assigned_to or current_user.id
            )
            db.session.add(created_opp)
            db.session.flush()

            log_opportunity_event(
                action=AuditEventType.OPPORTUNITY_CREATE,
                opportunity_id=created_opp.id,
                user_id=current_user.id,
                old_value=None,
                new_value=created_opp.to_dict(),
                details=f"Created via conversion from Lead #{lead.id} ({lead.lead_code})"
            )

        # 3. Finalize Lead Conversion
        old_lead_state = lead.to_dict()
        lead.status = LeadStatus.CONVERTED
        lead.converted_date = datetime.utcnow()
        if target_customer:
            lead.converted_customer_id = target_customer.id
        if created_opp:
            lead.converted_opportunity_id = created_opp.id

        db.session.commit()
        new_lead_state = lead.to_dict()

        # Log LEAD_CONVERSION audit event
        log_lead_event(
            action=AuditEventType.LEAD_CONVERSION,
            lead_id=lead.id,
            user_id=current_user.id,
            old_value=old_lead_state,
            new_value=new_lead_state,
            details=f"Converted to Customer #{target_customer.id if target_customer else 'N/A'}, Opportunity #{created_opp.id if created_opp else 'N/A'}"
        )

        flash(
            f"Lead '{lead.lead_name}' successfully converted! "
            f"{'Customer created/linked. ' if target_customer else ''}"
            f"{'Opportunity created.' if created_opp else ''}",
            "success"
        )

        if target_customer:
            return redirect(url_for('customer.details', id=target_customer.id))
        return redirect(url_for('lead.details', id=lead.id))

    return render_template('leads/convert.html', form=form, lead=lead)
