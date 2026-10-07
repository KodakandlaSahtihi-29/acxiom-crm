import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Regexp, Length, EqualTo, ValidationError
from app.models.user import User
from app.utils.security import validate_password_policy


class LoginForm(FlaskForm):
    """User authentication form."""
    username_or_email = StringField('Username or Email', validators=[
        DataRequired(message="Username or email is required."),
        Length(min=3, max=120)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required.")
    ])
    remember_me = BooleanField('Keep me logged in for 30 days')
    submit = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    """User self-registration form. Assigns safe default SalesExecutive role."""
    full_name = StringField('Full Name', validators=[
        DataRequired(message="Full name is required."),
        Length(min=2, max=120, message="Full name must be between 2 and 120 characters.")
    ])
    username = StringField('Username', validators=[
        DataRequired(message="Username is required."),
        Length(min=3, max=80, message="Username must be between 3 and 80 characters.")
    ])
    email = StringField('Email Address', validators=[
        DataRequired(message="Email address is required."),
        Regexp(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', message="Please enter a valid email address."),
        Length(max=120)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password."),
        EqualTo('password', message="Passwords do not match.")
    ])
    submit = SubmitField('Create Account')

    def validate_username(self, field):
        """Validate username format and uniqueness."""
        val = field.data.strip()
        if not re.match(r'^[A-Za-z0-9_.-]+$', val):
            raise ValidationError("Username can only contain letters, numbers, dots, hyphens, and underscores.")
        existing = User.query.filter(User.username.ilike(val)).first()
        if existing:
            raise ValidationError("This username is already taken. Please choose another.")

    def validate_email(self, field):
        """Validate email uniqueness."""
        val = field.data.strip().lower()
        existing = User.query.filter(User.email.ilike(val)).first()
        if existing:
            raise ValidationError("An account with this email address already exists.")

    def validate_password(self, field):
        """Validate against password complexity policy."""
        is_valid, errors = validate_password_policy(field.data)
        if not is_valid:
            raise ValidationError(errors[0])
