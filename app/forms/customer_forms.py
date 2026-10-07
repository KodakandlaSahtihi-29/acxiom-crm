import re
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp, Optional, ValidationError
from app.models.customer import Customer

# Phone format: 7 to 25 characters, optional leading +, allowed dashes, spaces, parentheses
PHONE_REGEX = r'^\+?[0-9\s\-()]{7,25}$'
# Email format: Standard RFC compliant pattern
EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'


class CustomerForm(FlaskForm):
    """
    Customer form for Create and Edit operations with full server-side validation.
    Enforces uniqueness of CustomerCode, Email, and Phone.
    """
    customer_code = StringField('Customer Code', validators=[
        DataRequired(message="Customer Code is required."),
        Length(min=2, max=50, message="Customer Code must be between 2 and 50 characters.")
    ])

    customer_name = StringField('Customer Name', validators=[
        DataRequired(message="Customer Name is required."),
        Length(min=2, max=150, message="Customer Name must not exceed 150 characters.")
    ])

    email = StringField('Corporate Email', validators=[
        DataRequired(message="Email address is required."),
        Regexp(EMAIL_REGEX, message="Please provide a valid email address (e.g. contact@company.com)."),
        Length(max=120, message="Email must not exceed 120 characters.")
    ])

    phone = StringField('Phone Number', validators=[
        DataRequired(message="Phone number is required."),
        Regexp(PHONE_REGEX, message="Please provide a valid phone number (7-25 digits, optional + or dashes)."),
        Length(min=7, max=25, message="Phone number must be between 7 and 25 digits.")
    ])

    company_name = StringField('Company Name', validators=[
        Optional(),
        Length(max=150, message="Company Name must not exceed 150 characters.")
    ])

    address = StringField('Street Address', validators=[
        Optional(),
        Length(max=255, message="Address must not exceed 255 characters.")
    ])

    city = StringField('City', validators=[
        Optional(),
        Length(max=100, message="City must not exceed 100 characters.")
    ])

    state = StringField('State / Province', validators=[
        Optional(),
        Length(max=100, message="State must not exceed 100 characters.")
    ])

    status = SelectField('Status', choices=[
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Prospect', 'Prospect'),
        ('Suspended', 'Suspended')
    ], default='Active', validators=[
        DataRequired(message="Please select a customer status.")
    ])

    submit = SubmitField('Save Customer')

    def __init__(self, original_customer=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_customer = original_customer

    def validate_customer_code(self, field):
        """Validate uniqueness of CustomerCode across all customers."""
        val = field.data.strip()
        query = Customer.query.filter(Customer.customer_code.ilike(val))
        if self.original_customer:
            query = query.filter(Customer.id != self.original_customer.id)
        if query.first():
            raise ValidationError(f"Customer Code '{val}' is already in use. Please specify a unique code.")

    def validate_email(self, field):
        """Validate uniqueness of Email address across all customers."""
        val = field.data.strip().lower()
        query = Customer.query.filter(Customer.email.ilike(val))
        if self.original_customer:
            query = query.filter(Customer.id != self.original_customer.id)
        if query.first():
            raise ValidationError(f"A customer with email '{val}' already exists.")

    def validate_phone(self, field):
        """Validate uniqueness of Phone number across all customers."""
        val = field.data.strip()
        query = Customer.query.filter(Customer.phone == val)
        if self.original_customer:
            query = query.filter(Customer.id != self.original_customer.id)
        if query.first():
            raise ValidationError(f"A customer with phone number '{val}' already exists.")
