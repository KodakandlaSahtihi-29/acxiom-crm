"""
Lead Entity Model for Acxiom CRM.
Implements all fields, status workflow, scoping, and conversion tracking specified in the AcxiomCRM specifications.
"""
from datetime import datetime
from app.extensions import db


class LeadStatus:
    NEW = 'New'
    CONTACTED = 'Contacted'
    QUALIFIED = 'Qualified'
    UNQUALIFIED = 'Unqualified'
    CONVERTED = 'Converted'
    LOST = 'Lost'

    ALL_STATUSES = [
        NEW,
        CONTACTED,
        QUALIFIED,
        UNQUALIFIED,
        CONVERTED,
        LOST
    ]

    # Configured workflow transitions
    VALID_TRANSITIONS = {
        NEW: [NEW, CONTACTED, QUALIFIED, UNQUALIFIED, LOST],
        CONTACTED: [CONTACTED, QUALIFIED, UNQUALIFIED, LOST],
        QUALIFIED: [QUALIFIED, CONVERTED, CONTACTED, UNQUALIFIED, LOST],
        UNQUALIFIED: [UNQUALIFIED, NEW, CONTACTED, QUALIFIED],
        LOST: [LOST, NEW, CONTACTED, QUALIFIED],
        CONVERTED: [CONVERTED]  # Terminal state once converted
    }


class LeadSource:
    WEBSITE = 'Website'
    REFERRAL = 'Referral'
    COLD_CALL = 'Cold Call'
    ADVERTISEMENT = 'Advertisement'
    EVENT = 'Event'
    PARTNER = 'Partner'
    OTHER = 'Other'

    ALL_SOURCES = [
        WEBSITE,
        REFERRAL,
        COLD_CALL,
        ADVERTISEMENT,
        EVENT,
        PARTNER,
        OTHER
    ]


class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)
    lead_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    lead_name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True, index=True)
    phone = db.Column(db.String(25), nullable=True, index=True)
    company_name = db.Column(db.String(150), nullable=True)
    source = db.Column(db.String(50), default=LeadSource.WEBSITE, nullable=True)
    status = db.Column(db.String(50), default=LeadStatus.NEW, nullable=False)
    expected_value = db.Column(db.Float, default=0.0, nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Ownership & Assignment
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Conversion Tracking
    converted_customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True)
    converted_opportunity_id = db.Column(db.Integer, nullable=True)
    converted_date = db.Column(db.DateTime, nullable=True)

    # ORM Relationships
    creator = db.relationship('User', foreign_keys=[created_by], backref=db.backref('created_leads', lazy='dynamic'))
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref=db.backref('assigned_leads', lazy='dynamic'))
    converted_customer = db.relationship('Customer', foreign_keys=[converted_customer_id])

    @property
    def converted_opportunity(self):
        if self.converted_opportunity_id:
            from app.models.opportunity import Opportunity
            return db.session.get(Opportunity, self.converted_opportunity_id)
        return None

    # PascalCase property aliases for specification compliance
    @property
    def LeadId(self):
        return self.id

    @property
    def LeadCode(self):
        return self.lead_code

    @property
    def LeadName(self):
        return self.lead_name

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
    def Source(self):
        return self.source

    @property
    def Status(self):
        return self.status

    @property
    def ExpectedValue(self):
        return self.expected_value

    @property
    def CreatedDate(self):
        return self.created_date

    @property
    def AssignedTo(self):
        return self.assigned_to

    @property
    def CreatedBy(self):
        return self.created_by

    def is_converted(self):
        return self.status == LeadStatus.CONVERTED

    def can_be_converted(self):
        """Lead can be converted if not already converted."""
        return self.status != LeadStatus.CONVERTED

    def can_be_managed_by(self, user):
        """Check if user has permission to view/edit/delete this lead."""
        if not user or not user.is_authenticated:
            return False
        if user.role in ('Admin', 'Manager'):
            return True
        return self.assigned_to == user.id or self.created_by == user.id

    @classmethod
    def get_scoped_query(cls, user):
        """Return leads query scoped to user role."""
        if user.role in ('Admin', 'Manager'):
            return cls.query
        return cls.query.filter((cls.assigned_to == user.id) | (cls.created_by == user.id))

    @staticmethod
    def is_valid_status_transition(current_status, new_status):
        """Check if status transition follows workflow."""
        if new_status not in LeadStatus.ALL_STATUSES:
            return False, f"Invalid status '{new_status}'."
        allowed = LeadStatus.VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            return False, f"Transition from '{current_status}' to '{new_status}' is not permitted."
        return True, None

    def to_dict(self):
        return {
            'LeadId': self.id,
            'LeadCode': self.lead_code,
            'LeadName': self.lead_name,
            'Email': self.email,
            'Phone': self.phone,
            'CompanyName': self.company_name,
            'Source': self.source,
            'Status': self.status,
            'ExpectedValue': self.expected_value,
            'CreatedDate': self.created_date.isoformat() if self.created_date else None,
            'CreatedBy': self.created_by,
            'AssignedTo': self.assigned_to,
            'AssigneeName': self.assignee.full_name if self.assignee else None,
            'ConvertedCustomerId': self.converted_customer_id,
            'ConvertedOpportunityId': self.converted_opportunity_id,
            'ConvertedDate': self.converted_date.isoformat() if self.converted_date else None
        }

    def __repr__(self):
        return f'<Lead {self.lead_code} - {self.lead_name} ({self.status})>'
