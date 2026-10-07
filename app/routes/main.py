from datetime import date
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from sqlalchemy import text
from app.extensions import db
from app.utils.decorators import admin_required, manager_required, sales_executive_required
from app.models.customer import Customer
from app.models.lead import Lead, LeadStatus
from app.models.opportunity import Opportunity, OpportunityStatus, OpportunityStage

main_bp = Blueprint('main', __name__)


def _get_dashboard_metrics(user):
    """
    Compute KPI metrics and chart datasets scoped to the current user's role:
    - Admin: all data
    - Manager: permitted business/team data
    - SalesExecutive: permitted own/assigned data
    """
    cust_query = Customer.get_scoped_query(user)
    lead_query = Lead.get_scoped_query(user)
    opp_query = Opportunity.get_scoped_query(user)

    # 1. KPI Cards
    total_customers = cust_query.count()
    total_leads = lead_query.count()
    open_leads = lead_query.filter(
        Lead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED, LeadStatus.QUALIFIED])
    ).count()

    total_opportunities = opp_query.count()
    open_opportunities = opp_query.filter(Opportunity.status == OpportunityStatus.OPEN).count()
    won_opportunities = opp_query.filter(
        (Opportunity.status == OpportunityStatus.WON) | (Opportunity.stage == OpportunityStage.WON)
    ).count()
    lost_opportunities = opp_query.filter(
        (Opportunity.status == OpportunityStatus.LOST) | (Opportunity.stage == OpportunityStage.LOST)
    ).count()

    # Total Pipeline Value: sum of amounts for open opportunities
    open_opps = opp_query.filter(Opportunity.status == OpportunityStatus.OPEN).all()
    total_pipeline_value = sum(float(opp.amount or 0.0) for opp in open_opps)

    # 2. Chart 1: Lead Status Distribution
    lead_status_labels = [
        LeadStatus.NEW,
        LeadStatus.CONTACTED,
        LeadStatus.QUALIFIED,
        LeadStatus.UNQUALIFIED,
        LeadStatus.CONVERTED,
        LeadStatus.LOST
    ]
    lead_counts = {s: 0 for s in lead_status_labels}
    for lead in lead_query.all():
        if lead.status in lead_counts:
            lead_counts[lead.status] += 1
    lead_status_data = [lead_counts[s] for s in lead_status_labels]

    # 3. Chart 2: Opportunity Pipeline by Stage
    opp_stage_labels = [
        OpportunityStage.QUALIFICATION,
        OpportunityStage.PROPOSAL,
        OpportunityStage.NEGOTIATION,
        OpportunityStage.WON,
        OpportunityStage.LOST
    ]
    opp_counts = {st: 0 for st in opp_stage_labels}
    for opp in opp_query.all():
        if opp.stage in opp_counts:
            opp_counts[opp.stage] += 1
    opp_stage_data = [opp_counts[st] for st in opp_stage_labels]

    # 4. Chart 3: Monthly Sales (Won revenue across past 6 months)
    today = date.today()
    monthly_sales_labels = []
    monthly_sales_data = []

    # Get won opportunities once
    won_opps = opp_query.filter(
        (Opportunity.status == OpportunityStatus.WON) | (Opportunity.stage == OpportunityStage.WON)
    ).all()

    for i in range(5, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            m += 12
            y -= 1
        month_label = date(y, m, 1).strftime('%b %Y')
        monthly_sales_labels.append(month_label)

        month_sum = 0.0
        for opp in won_opps:
            close_d = opp.expected_close_date or (opp.created_date.date() if opp.created_date else None)
            if close_d and close_d.year == y and close_d.month == m:
                month_sum += float(opp.amount or 0.0)
        monthly_sales_data.append(round(month_sum, 2))

    return {
        'total_customers': total_customers,
        'total_leads': total_leads,
        'open_leads': open_leads,
        'total_opportunities': total_opportunities,
        'open_opportunities': open_opportunities,
        'won_opportunities': won_opportunities,
        'lost_opportunities': lost_opportunities,
        'total_pipeline_value': round(total_pipeline_value, 2),
        'lead_status_labels': lead_status_labels,
        'lead_status_data': lead_status_data,
        'opp_stage_labels': opp_stage_labels,
        'opp_stage_data': opp_stage_data,
        'monthly_sales_labels': monthly_sales_labels,
        'monthly_sales_data': monthly_sales_data,
    }


@main_bp.route('/')
def index():
    """Public landing / foundation status page."""
    db_status = "Connected"
    error_msg = None
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "Disconnected"
        error_msg = str(e)

    return render_template(
        'index.html',
        db_status=db_status,
        error_msg=error_msg,
        phase="Phase 8: Functional Dashboard"
    )


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Authenticated user dashboard landing page with KPI cards and charts."""
    metrics = _get_dashboard_metrics(current_user)
    return render_template('dashboard.html', **metrics)


@main_bp.route('/manager/portal')
@manager_required
def manager_portal():
    """Protected view requiring Manager or Admin role."""
    metrics = _get_dashboard_metrics(current_user)
    return render_template(
        'dashboard.html',
        section_title="Manager Portal",
        section_desc="Accessible by Managers and Administrators.",
        **metrics
    )


@main_bp.route('/admin/portal')
@admin_required
def admin_portal():
    """Protected view requiring Administrator role only."""
    metrics = _get_dashboard_metrics(current_user)
    return render_template(
        'dashboard.html',
        section_title="System Administration Portal",
        section_desc="Strictly restricted to Admin role accounts.",
        **metrics
    )


@main_bp.route('/health')
def health():
    """Application health endpoint."""
    db_ok = False
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return jsonify({
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "phase": 8,
        "app": "Acxiom CRM"
    })
