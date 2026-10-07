"""
Opportunity Entity Model for Acxiom CRM.
Implements complete requirements from AcxiomCRM Functional Specifications:
- OpportunityId
- OpportunityName
- CustomerId
- LeadId
- Owner/AssignedTo
- Stage
- Amount
- Probability
- ExpectedCloseDate
- Source
- Status
- CreatedDate
- Notes
"""
from datetime import datetime, date
from app.extensions import db


class OpportunityStage:
    QUALIFICATION = 'Qualification'
    PROPOSAL = 'Proposal'
    NEGOTIATION = 'Negotiation'
    WON = 'Won'
    LOST = 'Lost'

    ALL_STAGES = [
        QUALIFICATION,
        PROPOSAL,
        NEGOTIATION,
        WON,
        LOST
    ]

    DEFAULT_PROBABILITIES = {
        QUALIFICATION: 20,
        PROPOSAL: 50,
        NEGOTIATION: 80,
        WON: 100,
        LOST: 0
    }


class OpportunityStatus:
    OPEN = 'Open'
    WON = 'Won'
    LOST = 'Lost'
    ON_HOLD = 'On Hold'

    ALL_STATUSES = [OPEN, WON, LOST, ON_HOLD]


class OpportunitySource:
    WEBSITE = 'Website'
    REFERRAL = 'Referral'
    LEAD_CONVERSION = 'Lead Conversion'
    COLD_CALL = 'Cold Call'
    ADVERTISEMENT = 'Advertisement'
    PARTNER = 'Partner'
    EXISTING_CUSTOMER = 'Existing Customer'
    OTHER = 'Other'

    ALL_SOURCES = [
        WEBSITE,
        REFERRAL,
        LEAD_CONVERSION,
        COLD_CALL,
        ADVERTISEMENT,
        PARTNER,
        EXISTING_CUSTOMER,
        OTHER
    ]


class Opportunity(db.Model):
    __tablename__ = 'opportunities'

    id = db.Column(db.Integer, primary_key=True)
    opportunity_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    opportunity_name = db.Column(db.String(150), nullable=False, index=True)
    amount = db.Column(db.Float, default=0.0, nullable=False)
    probability = db.Column(db.Integer, default=20, nullable=False)  # 0 to 100 %
    stage = db.Column(db.String(50), default=OpportunityStage.QUALIFICATION, nullable=False)
    status = db.Column(db.String(50), default=OpportunityStatus.OPEN, nullable=False)
    source = db.Column(db.String(50), default=OpportunitySource.WEBSITE, nullable=True)
    expected_close_date = db.Column(db.Date, nullable=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    # Relationships & Foreign Keys
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id', ondelete='SET NULL'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # ORM Relationships
    customer = db.relationship('Customer', foreign_keys=[customer_id], backref=db.backref('customer_opportunities', lazy='dynamic'))
    lead = db.relationship('Lead', foreign_keys=[lead_id], backref=db.backref('originating_opportunities', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by], backref=db.backref('created_opportunities', lazy='dynamic'))
    owner = db.relationship('User', foreign_keys=[assigned_to], backref=db.backref('owned_opportunities', lazy='dynamic'))

    # Backward compatibility with Lead Conversion title/close_date
    @property
    def title(self):
        return self.opportunity_name

    @title.setter
    def title(self, value):
        self.opportunity_name = value

    @property
    def close_date(self):
        return self.expected_close_date

    @close_date.setter
    def close_date(self, value):
        if isinstance(value, datetime):
            self.expected_close_date = value.date()
        else:
            self.expected_close_date = value

    # PascalCase property aliases matching PDF requirements
    @property
    def OpportunityId(self):
        return self.id

    @property
    def OpportunityName(self):
        return self.opportunity_name

    @property
    def CustomerId(self):
        return self.customer_id

    @property
    def LeadId(self):
        return self.lead_id

    @property
    def AssignedTo(self):
        return self.assigned_to

    @property
    def Stage(self):
        return self.stage

    @property
    def Amount(self):
        return self.amount

    @property
    def Probability(self):
        return self.probability

    @property
    def ExpectedCloseDate(self):
        return self.expected_close_date

    @property
    def Source(self):
        return self.source

    @property
    def Status(self):
        return self.status

    @property
    def CreatedDate(self):
        return self.created_date

    @property
    def Notes(self):
        return self.notes

    @property
    def weighted_value(self):
        """Weighted Value = Amount * Probability / 100."""
        return round(float(self.amount or 0.0) * float(self.probability or 0) / 100.0, 2)

    @property
    def WeightedValue(self):
        return self.weighted_value

    def can_be_managed_by(self, user):
        """Role authorization check."""
        if not user or not user.is_authenticated:
            return False
        if user.role in ('Admin', 'Manager'):
            return True
        return self.assigned_to == user.id or self.created_by == user.id

    @classmethod
    def get_scoped_query(cls, user):
        """Return opportunities scoped to user's permissions."""
        if user.role in ('Admin', 'Manager'):
            return cls.query
        return cls.query.filter((cls.assigned_to == user.id) | (cls.created_by == user.id))

    def to_dict(self):
        return {
            'OpportunityId': self.id,
            'OpportunityCode': self.opportunity_code,
            'OpportunityName': self.opportunity_name,
            'CustomerId': self.customer_id,
            'CustomerName': self.customer.customer_name if self.customer else None,
            'LeadId': self.lead_id,
            'LeadCode': self.lead.lead_code if self.lead else None,
            'Amount': self.amount,
            'Probability': self.probability,
            'WeightedValue': self.weighted_value,
            'Stage': self.stage,
            'Status': self.status,
            'Source': self.source,
            'ExpectedCloseDate': self.expected_close_date.isoformat() if self.expected_close_date else None,
            'CreatedDate': self.created_date.isoformat() if self.created_date else None,
            'CreatedBy': self.created_by,
            'AssignedTo': self.assigned_to,
            'OwnerName': self.owner.full_name if self.owner else None,
            'Notes': self.notes
        }

    def __repr__(self):
        return f'<Opportunity {self.opportunity_code} - {self.opportunity_name} (${self.amount})>'
