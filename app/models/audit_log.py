"""
AuditLog Model Placeholder
Full entity implementation reserved for Phase 2.
"""
from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<AuditLog {self.id} - {self.action}>'
