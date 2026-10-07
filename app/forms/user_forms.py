"""
User & Role Management Forms for Acxiom CRM.
Implements client-side and server-side validation for:
- User Creation (Admin only)
- User Editing & Role Assignment
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Regexp, Length, EqualTo, Optional, ValidationError

from app.models.user import User, Role
from app.utils.security import validate_password_policy

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'


class CreateUserForm(FlaskForm):
    """Admin form to create a new CRM user."""

    username = StringField(
        'Username',
        validators=[
            DataRequired(message="Username is required."),
            Length(min=3, max=80, message="Username must be between 3 and 80 characters.")
        ]
    )

    email = StringField(
        'Corporate Email',
        validators=[
            DataRequired(message="Corporate email is required."),
            Regexp(EMAIL_REGEX, message="Please enter a valid email address."),
            Length(max=120, message="Email cannot exceed 120 characters.")
        ]
    )

    full_name = StringField(
        'Full Name',
        validators=[
            DataRequired(message="Full name is required."),
            Length(max=120, message="Full name cannot exceed 120 characters.")
        ]
    )

    role = SelectField(
        'Assigned Role',
        choices=[
            (Role.ADMIN, 'Admin'),
            (Role.MANAGER, 'Manager'),
            (Role.SALES_EXECUTIVE, 'Sales Executive')
        ],
        validators=[DataRequired(message="Role selection is required.")],
        default=Role.SALES_EXECUTIVE
    )

    password = PasswordField(
        'Initial Password',
        validators=[
            DataRequired(message="Password is required.")
        ]
    )

    confirm_password = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(message="Please confirm the password."),
            EqualTo('password', message="Passwords do not match.")
        ]
    )

    is_active = BooleanField('Active Account', default=True)

    submit = SubmitField('Create User')

    def validate_username(self, field):
        """Enforce username uniqueness."""
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("This username is already taken. Please choose another.")

    def validate_email(self, field):
        """Enforce email uniqueness."""
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("This corporate email is already registered.")

    def validate_password(self, field):
        """Validate against password complexity policy."""
        is_valid, errors = validate_password_policy(field.data)
        if not is_valid:
            raise ValidationError(errors[0])


class EditUserForm(FlaskForm):
    """Admin form to edit existing user details, assign roles, or reset password."""

    username = StringField(
        'Username',
        validators=[
            DataRequired(message="Username is required."),
            Length(min=3, max=80, message="Username must be between 3 and 80 characters.")
        ]
    )

    email = StringField(
        'Corporate Email',
        validators=[
            DataRequired(message="Corporate email is required."),
            Regexp(EMAIL_REGEX, message="Please enter a valid email address."),
            Length(max=120, message="Email cannot exceed 120 characters.")
        ]
    )

    full_name = StringField(
        'Full Name',
        validators=[
            DataRequired(message="Full name is required."),
            Length(max=120, message="Full name cannot exceed 120 characters.")
        ]
    )

    role = SelectField(
        'Assigned Role',
        choices=[
            (Role.ADMIN, 'Admin'),
            (Role.MANAGER, 'Manager'),
            (Role.SALES_EXECUTIVE, 'Sales Executive')
        ],
        validators=[DataRequired(message="Role selection is required.")]
    )

    new_password = PasswordField(
        'New Password (leave blank to keep current)',
        validators=[Optional()]
    )

    confirm_new_password = PasswordField(
        'Confirm New Password',
        validators=[
            EqualTo('new_password', message="New passwords do not match.")
        ]
    )

    is_active = BooleanField('Active Account')

    submit = SubmitField('Update User')

    def __init__(self, original_user=None, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.original_user = original_user

    def validate_username(self, field):
        """Enforce unique username excluding original."""
        target_username = field.data.strip()
        if self.original_user and target_username == self.original_user.username:
            return
        existing = User.query.filter_by(username=target_username).first()
        if existing:
            raise ValidationError("This username is already taken by another account.")

    def validate_email(self, field):
        """Enforce unique email excluding original."""
        target_email = field.data.strip().lower()
        if self.original_user and target_email == self.original_user.email.lower():
            return
        existing = User.query.filter_by(email=target_email).first()
        if existing:
            raise ValidationError("This email is already registered to another account.")

    def validate_new_password(self, field):
        """Validate new password complexity if provided."""
        if field.data:
            is_valid, errors = validate_password_policy(field.data)
            if not is_valid:
                raise ValidationError(errors[0])
