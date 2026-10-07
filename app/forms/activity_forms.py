"""
Activity Management Forms for Acxiom CRM.
Implements client-side and server-side validation for:
- Activity Creation & Editing
- Activity Completion
- Activity Cancellation
"""
from datetime import date
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError

from app.models.activity import ActivityType, ActivityStatus
from app.models.user import User
from app.models.customer import Customer
from app.models.lead import Lead


class ActivityForm(FlaskForm):
    """Form for Creating and Editing Activities (Call, Meeting, Email, Task)."""

    activity_type = SelectField(
        'Activity Type',
        validators=[DataRequired(message="Activity type is required.")],
        choices=[(t, t) for t in ActivityType.ALL_TYPES],
        default=ActivityType.CALL
    )

    subject = StringField(
        'Subject',
        validators=[
            DataRequired(message="Subject is required."),
            Length(max=200, message="Subject cannot exceed 200 characters.")
        ]
    )

    description = TextAreaField(
        'Description & Agenda',
        validators=[Optional(), Length(max=2000, message="Description cannot exceed 2000 characters.")]
    )

    activity_date = DateField(
        'Activity Date',
        validators=[DataRequired(message="Activity date is required.")],
        default=date.today
    )

    customer_id = SelectField(
        'Associated Customer',
        coerce=int,
        default=0
    )

    lead_id = SelectField(
        'Associated Lead',
        coerce=int,
        default=0
    )

    assigned_to = SelectField(
        'Assigned Representative',
        coerce=int,
        validators=[DataRequired(message="Assigned user is required.")]
    )

    status = SelectField(
        'Status',
        validators=[DataRequired(message="Status is required.")],
        choices=[(s, s) for s in ActivityStatus.ALL_STATUSES],
        default=ActivityStatus.PENDING
    )

    submit = SubmitField('Save Activity')

    def validate_activity_type(self, field):
        """Must be one of the four configured activity types."""
        if field.data not in ActivityType.ALL_TYPES:
            raise ValidationError("Invalid activity type selected.")

    def validate_status(self, field):
        """Must be one of the configured statuses."""
        if field.data not in ActivityStatus.ALL_STATUSES:
            raise ValidationError("Invalid activity status selected.")

    def validate_assigned_to(self, field):
        """Assigned user must exist and be active."""
        if not field.data or field.data <= 0:
            raise ValidationError("A valid assigned user must be selected.")
        user = User.query.get(field.data)
        if not user or not user.is_active:
            raise ValidationError("Assigned user does not exist or is inactive.")

    def validate_customer_id(self, field):
        """Validate customer exists if supplied."""
        if field.data and field.data > 0:
            cust = Customer.query.get(field.data)
            if not cust:
                raise ValidationError("Selected customer does not exist.")

    def validate_lead_id(self, field):
        """Validate lead exists if supplied."""
        if field.data and field.data > 0:
            lead = Lead.query.get(field.data)
            if not lead:
                raise ValidationError("Selected lead does not exist.")


class CompleteActivityForm(FlaskForm):
    """Form to mark an Activity as Completed with outcome remarks."""

    completion_remarks = TextAreaField(
        'Outcome & Completion Remarks',
        validators=[Optional(), Length(max=1000, message="Completion remarks cannot exceed 1000 characters.")]
    )
    submit = SubmitField('Mark Completed')


class CancelActivityForm(FlaskForm):
    """Form to cancel an Activity with a required reason."""

    cancellation_reason = TextAreaField(
        'Cancellation Reason',
        validators=[
            DataRequired(message="Cancellation reason is required."),
            Length(max=1000, message="Reason cannot exceed 1000 characters.")
        ]
    )
    submit = SubmitField('Cancel Activity')
