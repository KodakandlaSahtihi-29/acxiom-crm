from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.extensions import db
from app.models.customer import Customer
from app.models.user import Role
from app.forms.customer_forms import CustomerForm
from app.services.audit_service import log_customer_event, AuditEventType

customer_bp = Blueprint('customer', __name__, url_prefix='/customers')


@customer_bp.route('', strict_slashes=False)
@customer_bp.route('/', strict_slashes=False)
@login_required
def index():
    """
    Customer Listing page with:
    - Search by CustomerName, Email, Phone, CustomerCode, CompanyName
    - Filter by Status
    - Sorting by column
    - Pagination
    - Role-based scoping (Admin/Manager: Full; SalesExecutive: Own scope)
    """
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    sort_by = request.args.get('sort', 'created_date').strip()
    direction = request.args.get('dir', 'desc').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Start with role-scoped query
    query = Customer.get_scoped_query(current_user)

    # Apply search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Customer.customer_name.ilike(search_pattern),
                Customer.email.ilike(search_pattern),
                Customer.phone.ilike(search_pattern),
                Customer.customer_code.ilike(search_pattern),
                Customer.company_name.ilike(search_pattern)
            )
        )

    # Apply status filter
    if status_filter and status_filter != 'All':
        query = query.filter(Customer.status == status_filter)

    # Apply sorting
    sort_column = getattr(Customer, sort_by, Customer.created_date)
    if direction == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    customers = pagination.items

    return render_template(
        'customers/index.html',
        customers=customers,
        pagination=pagination,
        search_query=search_query,
        status_filter=status_filter,
        sort_by=sort_by,
        direction=direction,
        is_scoped=(current_user.role == Role.SALES_EXECUTIVE)
    )


@customer_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    Create a new customer.
    Auto-sets CreatedDate and CreatedBy from authenticated user.
    Generates CUSTOMER_CREATE audit event upon success.
    """
    form = CustomerForm()

    if form.validate_on_submit():
        new_customer = Customer(
            customer_code=form.customer_code.data.strip(),
            customer_name=form.customer_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=form.phone.data.strip(),
            company_name=form.company_name.data.strip() if form.company_name.data else None,
            address=form.address.data.strip() if form.address.data else None,
            city=form.city.data.strip() if form.city.data else None,
            state=form.state.data.strip() if form.state.data else None,
            status=form.status.data,
            created_by=current_user.id
        )

        db.session.add(new_customer)
        db.session.commit()

        # Audit logging for Customer Create
        log_customer_event(
            action=AuditEventType.CUSTOMER_CREATE,
            customer_id=new_customer.id,
            user_id=current_user.id,
            old_value=None,
            new_value=new_customer.to_dict(),
            details=f"Created customer '{new_customer.customer_name}' ({new_customer.customer_code})"
        )

        flash(f"Customer '{new_customer.customer_name}' was successfully created.", "success")
        return redirect(url_for('customer.details', id=new_customer.id))

    return render_template('customers/create.html', form=form)


@customer_bp.route('/details/<int:id>')
@login_required
def details(id):
    """
    Display complete customer information without exposing sensitive authentication info.
    """
    customer = Customer.query.get_or_404(id)

    # Scoping check: SalesExecutive can only view details if scoped/allowed
    if not customer.can_be_managed_by(current_user) and current_user.role == Role.SALES_EXECUTIVE:
        flash("You are not authorized to view this customer record.", "danger")
        return redirect(url_for('auth.access_denied'))

    return render_template(
        'customers/details.html',
        customer=customer,
        can_manage=customer.can_be_managed_by(current_user)
    )


@customer_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """
    Edit an existing customer record.
    Enforces authorization check and uniqueness validation against other records.
    Generates CUSTOMER_UPDATE audit event with OldValue and NewValue.
    """
    customer = Customer.query.get_or_404(id)

    # Authorization verification
    if not customer.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to edit this customer record.", "danger")
        return redirect(url_for('auth.access_denied'))

    form = CustomerForm(original_customer=customer, obj=customer)

    if form.validate_on_submit():
        old_state = customer.to_dict()

        # Update entity fields
        customer.customer_code = form.customer_code.data.strip()
        customer.customer_name = form.customer_name.data.strip()
        customer.email = form.email.data.strip().lower()
        customer.phone = form.phone.data.strip()
        customer.company_name = form.company_name.data.strip() if form.company_name.data else None
        customer.address = form.address.data.strip() if form.address.data else None
        customer.city = form.city.data.strip() if form.city.data else None
        customer.state = form.state.data.strip() if form.state.data else None
        customer.status = form.status.data

        db.session.commit()
        new_state = customer.to_dict()

        # Audit logging for Customer Update
        log_customer_event(
            action=AuditEventType.CUSTOMER_UPDATE,
            customer_id=customer.id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=new_state,
            details=f"Updated customer '{customer.customer_name}' ({customer.customer_code})"
        )

        flash(f"Customer '{customer.customer_name}' updated successfully.", "success")
        return redirect(url_for('customer.details', id=customer.id))

    return render_template('customers/edit.html', form=form, customer=customer)


@customer_bp.route('/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete(id):
    """
    Delete a customer record with confirmation and authorization check.
    Generates CUSTOMER_DELETE audit event.
    """
    customer = Customer.query.get_or_404(id)

    # Server-side authorization: SalesExecutive cannot delete other users' customers
    if not customer.can_be_managed_by(current_user):
        flash("Unauthorized: You do not have permission to delete this customer record.", "danger")
        return redirect(url_for('auth.access_denied'))

    if request.method == 'POST':
        # Capture old value for audit logging prior to deletion
        old_state = customer.to_dict()
        cust_name = customer.customer_name
        cust_id = customer.id

        db.session.delete(customer)
        db.session.commit()

        # Audit logging for Customer Delete
        log_customer_event(
            action=AuditEventType.CUSTOMER_DELETE,
            customer_id=cust_id,
            user_id=current_user.id,
            old_value=old_state,
            new_value=None,
            details=f"Deleted customer '{cust_name}' (ID: #{cust_id})"
        )

        flash(f"Customer '{cust_name}' has been permanently deleted.", "info")
        return redirect(url_for('customer.index'))

    # GET displays the confirmation page
    return render_template('customers/delete.html', customer=customer)
