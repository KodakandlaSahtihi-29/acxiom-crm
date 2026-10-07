"""
Follow-Up Management Forms for Acxiom CRM.
Implements client-side and server-side validation for:
- Schedule Follow-Up
- Edit Follow-Up
- Reschedule Follow-Up
- Complete Follow-Up
"""
from datetime import date
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError

from app.models.follow_up import FollowUpType, FollowUpStatus
from app.models.user import User
from app.models.customer import Customer
from app.models.lead import Lead


class FollowUpForm(FlaskForm):
    """Form for Scheduling and Editing a Follow-Up."""

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

    follow_up_date = DateField(
        'Follow-Up Date',
        validators=[DataRequired(message="Follow-up date is required.")],
        default=date.today
    )

    follow_up_type = SelectField(
        'Follow-Up Type',
        validators=[DataRequired(message="Follow-up type is required.")],
        choices=[(t, t) for t in FollowUpType.ALL_TYPES]
    )

    status = SelectField(
        'Status',
        validators=[DataRequired(message="Status is required.")],
        choices=[(s, s) for s in FollowUpStatus.ALL_STATUSES],
        default=FollowUpStatus.PENDING
    )

    assigned_to = SelectField(
        'Assigned Representative',
        coerce=int,
        validators=[DataRequired(message="Assigned user is required.")]
    )

    remarks = TextAreaField(
        'Remarks & Objectives',
        validators=[Optional(), Length(max=1000, message="Remarks cannot exceed 1000 characters.")]
    )

    submit = SubmitField('Save Follow-Up')

    def __init__(self, *args, original_follow_up=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_follow_up = original_follow_up

    def validate_follow_up_date(self, field):
        """Date must not be in the past for active or newly scheduled follow-ups."""
        if field.data:
            # If creating or active status, cannot be before today
            is_active_or_new = self.original_follow_up is None or self.status.data in (
                FollowUpStatus.PENDING, FollowUpStatus.RESCHEDULED
            )
            if is_active_or_new and field.data < date.today():
                raise ValidationError("Follow-up date must not be before today.")

    def validate_follow_up_type(self, field):
        """Must be one of the configured follow-up types."""
        if field.data not in FollowUpType.ALL_TYPES:
            raise ValidationError("Invalid follow-up type selected.")

    def validate_status(self, field):
        """Must be one of the configured follow-up statuses."""
        if field.data not in FollowUpStatus.ALL_STATUSES:
            raise ValidationError("Invalid status value selected.")

    def validate_assigned_to(self, field):
        """Assigned user must be valid and active."""
        if not field.data or field.data <= 0:
            raise ValidationError("A valid assigned user must be selected.")
        user = User.query.get(field.data)
        if not user or not user.is_active:
            raise ValidationError("Assigned user does not exist or is inactive.")

    def validate(self, extra_validators=None):
        """Cross-field validation: At least one of Customer or Lead relationship must be maintained."""
        if not super().validate(extra_validators=extra_validators):
            return False

        has_customer = self.customer_id.data and self.customer_id.data > 0
        has_lead = self.lead_id.data and self.lead_id.data > 0

        if not has_customer and not has_lead:
            self.customer_id.errors.append("A valid Customer and/or Lead relationship must be maintained.")
            self.lead_id.errors.append("Please associate this follow-up with a Customer, Lead, or both.")
            return False

        if has_customer:
            cust = Customer.query.get(self.customer_id.data)
            if not cust:
                self.customer_id.errors.append("Selected customer was not found.")
                return False

        if has_lead:
            lead = Lead.query.get(self.lead_id.data)
            if not lead:
                self.lead_id.errors.append("Selected lead was not found.")
                return False

        return True


class CompleteFollowUpForm(FlaskForm):
    """Form to mark a Follow-Up as Completed."""

    completion_remarks = TextAreaField(
        'Outcome & Completion Remarks',
        validators=[Optional(), Length(max=1000, message="Remarks cannot exceed 1000 characters.")]
    )
    submit = SubmitField('Mark as Completed')


class RescheduleFollowUpForm(FlaskForm):
    """Form to Reschedule a Follow-Up."""

    follow_up_date = DateField(
        'New Follow-Up Date',
        validators=[DataRequired(message="New follow-up date is required.")],
        default=date.today
    )

    remarks = TextAreaField(
        'Reason for Rescheduling / Updated Notes',
        validators=[Optional(), Length(max=1000, message="Remarks cannot exceed 1000 characters.")]
    )

    submit = SubmitField('Reschedule Follow-Up')

    def validate_follow_up_date(self, field):
        if field.data and field.data < date.today():
            raise ValidationError("New follow-up date must not be before today.")
