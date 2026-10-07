import re
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, BooleanField, SubmitField, DateField
from wtforms.validators import DataRequired, Length, Regexp, Optional, NumberRange, ValidationError
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.opportunity import OpportunityStage

# Common RFC email and international phone regex patterns
EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
PHONE_REGEX = r'^\+?[0-9\s\-()]{7,25}$'


class LeadForm(FlaskForm):
    """Lead create and edit form with dual client/server validation."""
    lead_code = StringField('Lead Code', validators=[
        DataRequired(message="Lead Code is required."),
        Length(min=2, max=50, message="Lead Code must be between 2 and 50 characters.")
    ])

    lead_name = StringField('Lead Name', validators=[
        DataRequired(message="Lead Name is required."),
        Length(min=2, max=150, message="Lead Name must not exceed 150 characters.")
    ])

    email = StringField('Email Address', validators=[
        Optional(),
        Regexp(EMAIL_REGEX, message="Please enter a valid email address (e.g. lead@company.com)."),
        Length(max=120, message="Email must not exceed 120 characters.")
    ])

    phone = StringField('Phone Number', validators=[
        Optional(),
        Regexp(PHONE_REGEX, message="Please enter a valid phone number (7-25 digits, optional + or dashes)."),
        Length(min=7, max=25, message="Phone number must be between 7 and 25 digits.")
    ])

    company_name = StringField('Company Name', validators=[
        Optional(),
        Length(max=150, message="Company Name must not exceed 150 characters.")
    ])

    source = SelectField('Lead Source', choices=[
        (s, s) for s in LeadSource.ALL_SOURCES
    ], default=LeadSource.WEBSITE)

    status = SelectField('Lead Status', choices=[
        (s, s) for s in LeadStatus.ALL_STATUSES
    ], default=LeadStatus.NEW, validators=[
        DataRequired(message="Please select a lead status.")
    ])

    expected_value = FloatField('Expected Deal Value ($)', validators=[
        DataRequired(message="Expected value must be a valid number."),
        NumberRange(min=0.0, max=1000000000.0, message="Expected value must be a non-negative number up to 1,000,000,000.")
    ], default=0.0)

    assigned_to = SelectField('Assigned Sales Representative', coerce=int, validators=[Optional()])

    submit = SubmitField('Save Lead')

    def __init__(self, original_lead=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_lead = original_lead

    def validate_lead_code(self, field):
        """Ensure uniqueness of LeadCode."""
        val = field.data.strip()
        query = Lead.query.filter(Lead.lead_code.ilike(val))
        if self.original_lead:
            query = query.filter(Lead.id != self.original_lead.id)
        if query.first():
            raise ValidationError(f"Lead Code '{val}' is already in use. Please specify a unique code.")

    def validate_status(self, field):
        """Enforce configured statuses only."""
        if field.data not in LeadStatus.ALL_STATUSES:
            raise ValidationError(f"Invalid status '{field.data}'. Allowed: {', '.join(LeadStatus.ALL_STATUSES)}.")


class LeadConvertForm(FlaskForm):
    """Lead conversion wizard form to create Customer and/or Opportunity."""
    # Customer options
    convert_to_customer = BooleanField('Convert to Customer', default=True)
    customer_code = StringField('New Customer Code', validators=[
        Optional(),
        Length(min=2, max=50)
    ])
    customer_name = StringField('Customer Name', validators=[
        Optional(),
        Length(min=2, max=150)
    ])
    existing_customer_id = SelectField('Or Select Existing Customer', coerce=int, validators=[Optional()])

    # Opportunity options
    create_opportunity = BooleanField('Create Opportunity', default=True)
    opportunity_code = StringField('Opportunity Code', validators=[
        Optional(),
        Length(min=2, max=50)
    ])
    opportunity_title = StringField('Opportunity Title', validators=[
        Optional(),
        Length(min=2, max=150)
    ])
    opportunity_amount = FloatField('Opportunity Amount ($)', validators=[
        Optional(),
        NumberRange(min=0.0, message="Opportunity amount must be non-negative.")
    ], default=0.0)
    opportunity_stage = SelectField('Initial Stage', choices=[
        (s, s) for s in OpportunityStage.ALL_STAGES
    ], default=OpportunityStage.QUALIFICATION)
    close_date = DateField('Estimated Close Date', validators=[Optional()])

    submit = SubmitField('Complete Lead Conversion')
