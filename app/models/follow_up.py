"""
Follow-Up Entity Model for Acxiom CRM.
Implements complete requirements from AcxiomCRM Functional Specifications:
- FollowUpId
- CustomerId
- LeadId
- FollowUpDate
- FollowUpType
- Remarks
- Status
- AssignedTo
- CreatedBy
- CreatedDate
"""
from datetime import datetime, date
from app.extensions import db


class FollowUpType:
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


class FollowUpStatus:
    PENDING = 'Pending'
    COMPLETED = 'Completed'
    MISSED = 'Missed'
    RESCHEDULED = 'Rescheduled'

    ALL_STATUSES = [
        PENDING,
        COMPLETED,
        MISSED,
        RESCHEDULED
    ]


class FollowUp(db.Model):
    __tablename__ = 'follow_ups'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id', ondelete='SET NULL'), nullable=True)
    follow_up_date = db.Column(db.Date, nullable=False, index=True)
    follow_up_type = db.Column(db.String(50), default=FollowUpType.CALL, nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default=FollowUpStatus.PENDING, nullable=False, index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_date = db.Column(db.DateTime, nullable=True)
    completion_remarks = db.Column(db.Text, nullable=True)

    # ORM Relationships
    customer = db.relationship('Customer', foreign_keys=[customer_id], backref=db.backref('customer_follow_ups', lazy='dynamic'))
    lead = db.relationship('Lead', foreign_keys=[lead_id], backref=db.backref('lead_follow_ups', lazy='dynamic'))
    assigned_user = db.relationship('User', foreign_keys=[assigned_to], backref=db.backref('assigned_follow_ups', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by], backref=db.backref('created_follow_ups', lazy='dynamic'))

    # PascalCase property aliases matching PDF specification
    @property
    def FollowUpId(self):
        return self.id

    @property
    def CustomerId(self):
        return self.customer_id

    @property
    def LeadId(self):
        return self.lead_id

    @property
    def FollowUpDate(self):
        return self.follow_up_date

    @property
    def FollowUpType(self):
        return self.follow_up_type

    @property
    def Remarks(self):
        return self.remarks

    @property
    def Status(self):
        return self.status

    @property
    def AssignedTo(self):
        return self.assigned_to

    @property
    def is_overdue(self):
        """Returns True if the follow-up is still active (Pending or Rescheduled) and past due."""
        if self.status in [FollowUpStatus.PENDING, FollowUpStatus.RESCHEDULED]:
            return self.follow_up_date < date.today()
        return False

    @property
    def is_today(self):
        """Returns True if scheduled for today and active."""
        if self.status in [FollowUpStatus.PENDING, FollowUpStatus.RESCHEDULED]:
            return self.follow_up_date == date.today()
        return False

    def can_be_managed_by(self, user):
        """Return True if user has authorization to view/manage this follow-up."""
        if not user or not user.is_authenticated:
            return False
        if user.role in ('Admin', 'Manager'):
            return True
        return self.assigned_to == user.id or self.created_by == user.id

    @classmethod
    def get_scoped_query(cls, user):
        """Return follow-ups scoped to user's role permissions."""
        if user.role in ('Admin', 'Manager'):
            return cls.query
        return cls.query.filter((cls.assigned_to == user.id) | (cls.created_by == user.id))

    def to_dict(self):
        """Export dictionary representation for audit logging and JSON inspection."""
        return {
            'FollowUpId': self.id,
            'CustomerId': self.customer_id,
            'CustomerName': self.customer.customer_name if self.customer else None,
            'LeadId': self.lead_id,
            'LeadName': self.lead.lead_name if self.lead else None,
            'FollowUpDate': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'FollowUpType': self.follow_up_type,
            'Remarks': self.remarks,
            'Status': self.status,
            'AssignedTo': self.assigned_to,
            'AssignedUserName': self.assigned_user.full_name if self.assigned_user else None,
            'CreatedBy': self.created_by,
            'CreatedDate': self.created_date.isoformat() if self.created_date else None,
            'CompletedDate': self.completed_date.isoformat() if self.completed_date else None,
            'CompletionRemarks': self.completion_remarks
        }

    def __repr__(self):
        return f'<FollowUp #{self.id} {self.follow_up_type} on {self.follow_up_date} [{self.status}]>'
