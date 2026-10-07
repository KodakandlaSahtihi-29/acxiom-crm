"""
Customer Entity Model for Acxiom CRM.
Implements all fields specified in the Acxiom CRM Functional Requirements.
"""
from datetime import datetime
from app.extensions import db


class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    customer_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(25), unique=True, nullable=False, index=True)
    company_name = db.Column(db.String(150), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default='Active', nullable=False)  # Active, Inactive, Prospect, Suspended
    created_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Relationship to User (Creator)
    creator = db.relationship('User', backref=db.backref('created_customers', lazy='dynamic'))

    # PascalCase property aliases for specification compliance
    @property
    def CustomerId(self):
        return self.id

    @property
    def CustomerCode(self):
        return self.customer_code

    @property
    def CustomerName(self):
        return self.customer_name

    @property
    def Email(self):
        return self.email

    @property
    def Phone(self):
        return self.phone

    @property
    def CompanyName(self):
        return self.company_name

    @property
    def Address(self):
        return self.address

    @property
    def City(self):
        return self.city

    @property
    def State(self):
        return self.state

    @property
    def Status(self):
        return self.status

    @property
    def CreatedDate(self):
        return self.created_date

    @property
    def CreatedBy(self):
        return self.created_by

    def to_dict(self):
        """Serialize customer attributes for audit logging and API representation."""
        return {
            'CustomerId': self.id,
            'CustomerCode': self.customer_code,
            'CustomerName': self.customer_name,
            'Email': self.email,
            'Phone': self.phone,
            'CompanyName': self.company_name,
            'Address': self.address,
            'City': self.city,
            'State': self.state,
            'Status': self.status,
            'CreatedDate': self.created_date.isoformat() if self.created_date else None,
            'CreatedBy': self.created_by,
            'CreatorName': self.creator.full_name if self.creator else None
        }

    def can_be_managed_by(self, user):
        """
        Check if user has permission to edit/delete this customer.
        Admin: Full access.
        Manager: Full access across team.
        SalesExecutive: Only permitted for customers created by themselves.
        """
        if not user or not user.is_authenticated:
            return False
        if user.role in ('Admin', 'Manager'):
            return True
        return self.created_by == user.id

    @classmethod
    def get_scoped_query(cls, user):
        """
        Return query scoped to the current user's role.
        Admin / Manager: All customers.
        SalesExecutive: Customers created by the user (foundation for assignment scoping).
        """
        if user.role in ('Admin', 'Manager'):
            return cls.query
        return cls.query.filter(cls.created_by == user.id)

    def __repr__(self):
        return f'<Customer {self.customer_code} - {self.customer_name}>'
