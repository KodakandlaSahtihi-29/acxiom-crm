"""
REST API Module for Acxiom CRM.
Provides JSON RESTful endpoints for Customers, Leads, and Opportunities with:
- Authentication required (HTTP 401)
- Role scoping and ownership enforcement (HTTP 403)
- Data validation and error reporting (HTTP 400)
- Correct REST status codes (200, 201, 400, 401, 403, 404)
"""
import re
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from flask_login import current_user

from app.extensions import db
from app.models.customer import Customer
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.opportunity import Opportunity, OpportunityStage, OpportunityStatus, OpportunitySource
from app.services.audit_service import (
    log_customer_event,
    log_lead_event,
    log_opportunity_event,
    AuditEventType
)

api_bp = Blueprint('api', __name__, url_prefix='/api')

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'


@api_bp.before_request
def require_api_auth():
    """Ensure all API requests are made by authenticated sessions."""
    if not current_user.is_authenticated:
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication required to access CRM REST API endpoints.'
        }), 401


# ==============================================================================
# Customers API
# ==============================================================================

@api_bp.route('/customers', methods=['GET'])
def get_customers():
    """
    GET /api/customers
    List customers scoped to the authenticated user's role:
    - Admin/Manager: All customers
    - SalesExecutive: Own created customers
    """
    customers = Customer.get_scoped_query(current_user).all()
    return jsonify([c.to_dict() for c in customers]), 200


@api_bp.route('/customers', methods=['POST'])
def create_customer():
    """
    POST /api/customers
    Create a new customer with input validation.
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Bad Request', 'message': 'JSON payload is required.'}), 400

    name = data.get('customer_name') or data.get('CustomerName') or ''
    email = data.get('email') or data.get('Email') or ''
    phone = data.get('phone') or data.get('Phone') or ''
    company = data.get('company_name') or data.get('CompanyName') or ''
    address = data.get('address') or data.get('Address')
    city = data.get('city') or data.get('City')
    state = data.get('state') or data.get('State')
    status = data.get('status') or data.get('Status') or 'Active'
    code = data.get('customer_code') or data.get('CustomerCode')

    errors = []
    if not name.strip():
        errors.append("Customer name is required.")
    if not email.strip():
        errors.append("Email address is required.")
    elif not re.match(EMAIL_REGEX, email.strip()):
        errors.append("Invalid email address format.")
    elif Customer.query.filter(Customer.email.ilike(email.strip())).first():
        errors.append(f"A customer with email '{email.strip()}' already exists.")

    if not phone.strip():
        errors.append("Phone number is required.")
    elif Customer.query.filter(Customer.phone == phone.strip()).first():
        errors.append(f"A customer with phone '{phone.strip()}' already exists.")

    if errors:
        return jsonify({'error': 'Validation Error', 'messages': errors}), 400

    # Auto-generate customer_code if omitted
    if not code:
        seq = Customer.query.count() + 1
        code = f"CUST-API{seq:04d}"

    customer = Customer(
        customer_code=code,
        customer_name=name.strip(),
        email=email.strip().lower(),
        phone=phone.strip(),
        company_name=company.strip() if company else None,
        address=address.strip() if address else None,
        city=city.strip() if city else None,
        state=state.strip() if state else None,
        status=status,
        created_by=current_user.id
    )

    db.session.add(customer)
    db.session.commit()

    log_customer_event(AuditEventType.CUSTOMER_CREATE, customer.id, current_user.id, None, customer.to_dict())

    return jsonify(customer.to_dict()), 201


@api_bp.route('/customers/<int:id>', methods=['PUT'])
def update_customer(id):
    """
    PUT /api/customers/<id>
    Update an existing customer.
    """
    customer = Customer.query.get(id)
    if not customer:
        return jsonify({'error': 'Not Found', 'message': f'Customer #{id} not found.'}), 404

    if not customer.can_be_managed_by(current_user):
        return jsonify({'error': 'Forbidden', 'message': 'You do not have permission to modify this customer.'}), 403

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Bad Request', 'message': 'JSON payload is required.'}), 400

    errors = []
    name = data.get('customer_name') or data.get('CustomerName')
    if name is not None:
        if not name.strip():
            errors.append("Customer name cannot be empty.")
        else:
            customer.customer_name = name.strip()

    email = data.get('email') or data.get('Email')
    if email is not None:
        if not email.strip() or not re.match(EMAIL_REGEX, email.strip()):
            errors.append("Invalid email address format.")
        else:
            existing = Customer.query.filter(Customer.email.ilike(email.strip()), Customer.id != id).first()
            if existing:
                errors.append(f"A customer with email '{email.strip()}' already exists.")
            else:
                customer.email = email.strip().lower()

    phone = data.get('phone') or data.get('Phone')
    if phone is not None:
        if not phone.strip():
            errors.append("Phone cannot be empty.")
        else:
            existing_p = Customer.query.filter(Customer.phone == phone.strip(), Customer.id != id).first()
            if existing_p:
                errors.append(f"A customer with phone '{phone.strip()}' already exists.")
            else:
                customer.phone = phone.strip()

    if errors:
        return jsonify({'error': 'Validation Error', 'messages': errors}), 400

    company = data.get('company_name') or data.get('CompanyName')
    if company is not None:
        customer.company_name = company.strip() if company else None
    if 'address' in data or 'Address' in data:
        customer.address = (data.get('address') or data.get('Address') or '').strip() or None
    if 'city' in data or 'City' in data:
        customer.city = (data.get('city') or data.get('City') or '').strip() or None
    if 'state' in data or 'State' in data:
        customer.state = (data.get('state') or data.get('State') or '').strip() or None
    if 'status' in data or 'Status' in data:
        customer.status = data.get('status') or data.get('Status') or customer.status

    db.session.commit()
    log_customer_event(AuditEventType.CUSTOMER_UPDATE, customer.id, current_user.id, None, customer.to_dict())

    return jsonify(customer.to_dict()), 200


@api_bp.route('/customers/<int:id>', methods=['DELETE'])
def delete_customer(id):
    """
    DELETE /api/customers/<id>
    Delete an existing customer.
    """
    customer = Customer.query.get(id)
    if not customer:
        return jsonify({'error': 'Not Found', 'message': f'Customer #{id} not found.'}), 404

    if not customer.can_be_managed_by(current_user):
        return jsonify({'error': 'Forbidden', 'message': 'You do not have permission to delete this customer.'}), 403

    old_val = customer.to_dict()
    db.session.delete(customer)
    db.session.commit()

    log_customer_event(AuditEventType.CUSTOMER_DELETE, id, current_user.id, old_val, None)

    return jsonify({'message': f'Customer #{id} deleted successfully.'}), 200


# ==============================================================================
# Leads API
# ==============================================================================

@api_bp.route('/leads', methods=['GET'])
def get_leads():
    """
    GET /api/leads
    List leads scoped to the authenticated user's role.
    """
    leads = Lead.get_scoped_query(current_user).all()
    return jsonify([l.to_dict() for l in leads]), 200


@api_bp.route('/leads', methods=['POST'])
def create_lead():
    """
    POST /api/leads
    Create a new lead with validation.
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Bad Request', 'message': 'JSON payload is required.'}), 400

    name = data.get('lead_name') or data.get('LeadName') or ''
    email = data.get('email') or data.get('Email') or ''
    phone = data.get('phone') or data.get('Phone') or ''
    company = data.get('company_name') or data.get('CompanyName')
    source = data.get('source') or data.get('Source') or LeadSource.WEBSITE
    status = data.get('status') or data.get('Status') or LeadStatus.NEW
    code = data.get('lead_code') or data.get('LeadCode')
    expected_val = data.get('expected_value') or data.get('ExpectedValue') or 0.0

    errors = []
    if not name.strip():
        errors.append("Lead name is required.")
    if not email.strip() or not re.match(EMAIL_REGEX, email.strip()):
        errors.append("Valid email address is required.")
    if not phone.strip():
        errors.append("Phone number is required.")

    try:
        val_float = float(expected_val)
        if val_float < 0:
            errors.append("Expected value cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Expected value must be a valid number.")
        val_float = 0.0

    if errors:
        return jsonify({'error': 'Validation Error', 'messages': errors}), 400

    if not code:
        seq = Lead.query.count() + 1
        code = f"LEAD-API{seq:04d}"

    lead = Lead(
        lead_code=code,
        lead_name=name.strip(),
        email=email.strip().lower(),
        phone=phone.strip(),
        company_name=company.strip() if company else None,
        source=source,
        status=status,
        expected_value=val_float,
        assigned_to=current_user.id,
        created_by=current_user.id
    )

    db.session.add(lead)
    db.session.commit()

    log_lead_event(AuditEventType.LEAD_CREATE, lead.id, current_user.id, None, lead.to_dict())

    return jsonify(lead.to_dict()), 201


# ==============================================================================
# Opportunities API
# ==============================================================================

@api_bp.route('/opportunities', methods=['GET'])
def get_opportunities():
    """
    GET /api/opportunities
    List opportunities scoped to the authenticated user's role.
    """
    opps = Opportunity.get_scoped_query(current_user).all()
    return jsonify([o.to_dict() for o in opps]), 200


@api_bp.route('/opportunities', methods=['POST'])
def create_opportunity():
    """
    POST /api/opportunities
    Create a new opportunity with validation.
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Bad Request', 'message': 'JSON payload is required.'}), 400

    name = data.get('opportunity_name') or data.get('OpportunityName') or ''
    amount = data.get('amount') or data.get('Amount')
    stage = data.get('stage') or data.get('Stage') or OpportunityStage.QUALIFICATION
    status = data.get('status') or data.get('Status') or OpportunityStatus.OPEN
    prob = data.get('probability') or data.get('Probability') or 50
    source = data.get('source') or data.get('Source') or OpportunitySource.WEBSITE
    code = data.get('opportunity_code') or data.get('OpportunityCode')
    close_str = data.get('expected_close_date') or data.get('ExpectedCloseDate')

    errors = []
    if not name.strip():
        errors.append("Opportunity name is required.")

    amount_float = 0.0
    try:
        amount_float = float(amount)
        if amount_float <= 0:
            errors.append("Amount must be greater than zero.")
    except (ValueError, TypeError):
        errors.append("Valid numerical amount is required.")

    try:
        prob_int = int(prob)
        if prob_int < 0 or prob_int > 100:
            errors.append("Probability must be between 0 and 100.")
    except (ValueError, TypeError):
        errors.append("Valid probability integer is required.")
        prob_int = 50

    close_date = date.today() + timedelta(days=30)
    if close_str:
        try:
            close_date = datetime.strptime(str(close_str)[:10], '%Y-%m-%d').date()
        except Exception:
            errors.append("Expected close date must be formatted YYYY-MM-DD.")

    if errors:
        return jsonify({'error': 'Validation Error', 'messages': errors}), 400

    if not code:
        seq = Opportunity.query.count() + 1
        code = f"OPP-API{seq:04d}"

    opp = Opportunity(
        opportunity_code=code,
        opportunity_name=name.strip(),
        amount=amount_float,
        probability=prob_int,
        stage=stage,
        status=status,
        source=source,
        expected_close_date=close_date,
        assigned_to=current_user.id,
        created_by=current_user.id
    )

    db.session.add(opp)
    db.session.commit()

    log_opportunity_event(AuditEventType.OPPORTUNITY_CREATE, opp.id, current_user.id, None, opp.to_dict())

    return jsonify(opp.to_dict()), 201
