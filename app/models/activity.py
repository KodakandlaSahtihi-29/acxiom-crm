"""
Activity Entity Model for Acxiom CRM.
Implements complete requirements from AcxiomCRM Functional Specifications:
- ActivityId
- ActivityType (Call, Meeting, Email, Task)
- Subject
- Description
- ActivityDate
- CustomerId
- LeadId
- AssignedTo
- Status (Pending, Completed, Cancelled)
- CreatedBy
- CreatedDate
"""
from datetime import datetime, date
from app.extensions import db


class ActivityType:
    CALL = 'Call'
    MEETING = 'Meeting'
    EMAIL = 'Email'
    TASK = 'Task'

    ALL_TYPES = [
        CALL,
        MEETING,
        EMAIL,
        TASK
    ]


class ActivityStatus:
    PENDING = 'Pending'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'

    ALL_STATUSES = [
        PENDING,
        COMPLETED,
        CANCELLED
    ]


class Activity(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    activity_type = db.Column(db.String(50), nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    activity_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(50), default=ActivityStatus.PENDING, nullable=False, index=True)

    # Foreign Keys
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id', ondelete='SET NULL'), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_date = db.Column(db.DateTime, nullable=True)
    completion_remarks = db.Column(db.Text, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)

    # Relationships
    customer = db.relationship('Customer', foreign_keys=[customer_id], backref=db.backref('customer_activities', lazy='dynamic'))
    lead = db.relationship('Lead', foreign_keys=[lead_id], backref=db.backref('lead_activities', lazy='dynamic'))
    assigned_user = db.relationship('User', foreign_keys=[assigned_to], backref=db.backref('assigned_activities', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by], backref=db.backref('created_activities', lazy='dynamic'))

    # PascalCase property aliases matching PDF specification
    @property
    def ActivityId(self):
        return self.id

    @property
    def ActivityType(self):
        return self.activity_type

    @property
    def Subject(self):
        return self.subject

    @property
    def Description(self):
        return self.description

    @property
    def ActivityDate(self):
        return self.activity_date

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
    def Status(self):
        return self.status

    @property
    def is_overdue(self):
        """Returns True if the activity is Pending and scheduled for before today."""
        if self.status == ActivityStatus.PENDING:
            return self.activity_date < date.today()
        return False

    @property
    def is_today(self):
        """Returns True if scheduled for today and Pending."""
        if self.status == ActivityStatus.PENDING:
            return self.activity_date == date.today()
        return False

    def can_be_managed_by(self, user):
        """Return True if user has authorization to view/manage this activity."""
        if not user or not user.is_authenticated:
            return False
        if user.role in ('Admin', 'Manager'):
            return True
        return self.assigned_to == user.id or self.created_by == user.id

    @classmethod
    def get_scoped_query(cls, user):
        """Return activities scoped to user's role permissions."""
        if user.role in ('Admin', 'Manager'):
            return cls.query
        return cls.query.filter((cls.assigned_to == user.id) | (cls.created_by == user.id))

    def to_dict(self):
        """Export dictionary representation for audit logging and JSON inspection."""
        return {
            'ActivityId': self.id,
            'ActivityType': self.activity_type,
            'Subject': self.subject,
            'Description': self.description,
            'ActivityDate': self.activity_date.isoformat() if self.activity_date else None,
            'Status': self.status,
            'CustomerId': self.customer_id,
            'CustomerName': self.customer.customer_name if self.customer else None,
            'LeadId': self.lead_id,
            'LeadName': self.lead.lead_name if self.lead else None,
            'AssignedTo': self.assigned_to,
            'AssignedUserName': self.assigned_user.full_name if self.assigned_user else None,
            'CreatedBy': self.created_by,
            'CreatedDate': self.created_date.isoformat() if self.created_date else None,
            'CompletedDate': self.completed_date.isoformat() if self.completed_date else None,
            'CompletionRemarks': self.completion_remarks,
            'CancellationReason': self.cancellation_reason
        }

    def __repr__(self):
        return f'<Activity #{self.id} [{self.activity_type}] {self.subject} ({self.status})>'
