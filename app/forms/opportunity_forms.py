from datetime import date
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, IntegerField, TextAreaField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError
from app.models.opportunity import Opportunity, OpportunityStage, OpportunityStatus, OpportunitySource
from app.models.customer import Customer
from app.models.lead import Lead


class OpportunityForm(FlaskForm):
    """
    Opportunity Create and Edit form.
    Enforces strict business validation:
    - Amount must be > 0 for active deals
    - Probability must be between 0 and 100
    - ExpectedCloseDate cannot be in the past for active deals
    - Stage and Status must be from configured enum sets
    """
    opportunity_code = StringField('Opportunity Code', validators=[
        DataRequired(message="Opportunity Code is required."),
        Length(min=2, max=50, message="Opportunity Code must be between 2 and 50 characters.")
    ])

    opportunity_name = StringField('Opportunity Name', validators=[
        DataRequired(message="Opportunity Name is required."),
        Length(min=2, max=150, message="Opportunity Name must not exceed 150 characters.")
    ])

    customer_id = SelectField('Customer / Account', coerce=int, validators=[
        DataRequired(message="Please select a Customer for this opportunity.")
    ])

    lead_id = SelectField('Originating Lead (Optional)', coerce=int, validators=[Optional()])

    amount = FloatField('Deal Amount ($)', validators=[
        DataRequired(message="Deal Amount is required and must be a valid number.")
    ])

    probability = IntegerField('Win Probability (%)', validators=[
        DataRequired(message="Probability is required."),
        NumberRange(min=0, max=100, message="Probability must be an integer between 0 and 100 inclusive.")
    ], default=20)

    stage = SelectField('Pipeline Stage', choices=[
        (s, s) for s in OpportunityStage.ALL_STAGES
    ], default=OpportunityStage.QUALIFICATION, validators=[
        DataRequired(message="Please select a pipeline stage.")
    ])

    status = SelectField('Opportunity Status', choices=[
        (s, s) for s in OpportunityStatus.ALL_STATUSES
    ], default=OpportunityStatus.OPEN, validators=[
        DataRequired(message="Please select an opportunity status.")
    ])

    expected_close_date = DateField('Expected Close Date', validators=[
        DataRequired(message="Expected Close Date is required.")
    ])

    source = SelectField('Deal Source', choices=[
        (s, s) for s in OpportunitySource.ALL_SOURCES
    ], default=OpportunitySource.WEBSITE)

    assigned_to = SelectField('Owner / Sales Representative', coerce=int, validators=[Optional()])

    notes = TextAreaField('Opportunity Notes & Strategy', validators=[
        Optional(),
        Length(max=2000, message="Notes must not exceed 2000 characters.")
    ])

    submit = SubmitField('Save Opportunity')

    def __init__(self, original_opportunity=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_opportunity = original_opportunity

    def validate_opportunity_code(self, field):
        """Ensure uniqueness of OpportunityCode."""
        val = field.data.strip()
        query = Opportunity.query.filter(Opportunity.opportunity_code.ilike(val))
        if self.original_opportunity:
            query = query.filter(Opportunity.id != self.original_opportunity.id)
        if query.first():
            raise ValidationError(f"Opportunity Code '{val}' is already in use. Please specify a unique code.")

    def validate_amount(self, field):
        """Validate that Amount > 0 for active opportunities; reject 0 and negative amounts."""
        if field.data is None:
            raise ValidationError("Amount is required.")
        val = float(field.data)
        # Check active deal status
        is_active = self.status.data in (OpportunityStatus.OPEN, OpportunityStatus.ON_HOLD) or self.stage.data not in (OpportunityStage.WON, OpportunityStage.LOST)
        if is_active and val <= 0:
            raise ValidationError("For an active opportunity, Amount must be strictly greater than $0.00.")
        elif val < 0:
            raise ValidationError("Amount cannot be negative.")

    def validate_probability(self, field):
        """Validate that Probability is between 0 and 100."""
        if field.data is None:
            raise ValidationError("Probability is required.")
        if field.data < 0 or field.data > 100:
            raise ValidationError("Probability must be between 0% and 100% inclusive.")

    def validate_expected_close_date(self, field):
        """For active opportunities, ExpectedCloseDate cannot be in the past."""
        if not field.data:
            return
        is_active = self.status.data in (OpportunityStatus.OPEN, OpportunityStatus.ON_HOLD) and self.stage.data not in (OpportunityStage.WON, OpportunityStage.LOST)
        if is_active and field.data < date.today():
            raise ValidationError("Expected Close Date cannot be in the past for active opportunities.")

    def validate_stage(self, field):
        """Stage must be in configured OpportunityStage."""
        if field.data not in OpportunityStage.ALL_STAGES:
            raise ValidationError(f"Invalid stage '{field.data}'.")

    def validate_status(self, field):
        """Status must be in configured OpportunityStatus."""
        if field.data not in OpportunityStatus.ALL_STATUSES:
            raise ValidationError(f"Invalid status '{field.data}'.")
