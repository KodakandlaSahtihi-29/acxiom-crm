"""
Audit Service Module for Acxiom CRM.
Provides structured recording for authentication, customer, lead, and opportunity lifecycle events.
"""
import logging
from datetime import datetime
from flask import request

logger = logging.getLogger('acxiom.audit')

# In-memory event audit trail for testing and inspection prior to DB viewer phase
AUDIT_TRAIL = []


class AuditEventType:
    # Auth Events
    LOGIN_SUCCESS = 'LOGIN_SUCCESS'
    LOGIN_FAILED = 'LOGIN_FAILED'
    ACCOUNT_LOCKED = 'ACCOUNT_LOCKED'
    LOGOUT = 'LOGOUT'
    REGISTER_SUCCESS = 'REGISTER_SUCCESS'
    ACCESS_DENIED = 'ACCESS_DENIED'

    # Customer Lifecycle Events
    CUSTOMER_CREATE = 'CUSTOMER_CREATE'
    CUSTOMER_UPDATE = 'CUSTOMER_UPDATE'
    CUSTOMER_DELETE = 'CUSTOMER_DELETE'

    # Lead Lifecycle Events
    LEAD_CREATE = 'LEAD_CREATE'
    LEAD_UPDATE = 'LEAD_UPDATE'
    LEAD_DELETE = 'LEAD_DELETE'
    LEAD_STATUS_CHANGE = 'LEAD_STATUS_CHANGE'
    LEAD_CONVERSION = 'LEAD_CONVERSION'

    # Opportunity Lifecycle Events
    OPPORTUNITY_CREATE = 'OPPORTUNITY_CREATE'
    OPPORTUNITY_UPDATE = 'OPPORTUNITY_UPDATE'
    OPPORTUNITY_DELETE = 'OPPORTUNITY_DELETE'
    OPPORTUNITY_STAGE_CHANGE = 'OPPORTUNITY_STAGE_CHANGE'
    OPPORTUNITY_STATUS_CHANGE = 'OPPORTUNITY_STATUS_CHANGE'

    # Follow-Up Lifecycle Events
    FOLLOWUP_CREATE = 'FOLLOWUP_CREATE'
    FOLLOWUP_UPDATE = 'FOLLOWUP_UPDATE'
    FOLLOWUP_COMPLETE = 'FOLLOWUP_COMPLETE'
    FOLLOWUP_RESCHEDULE = 'FOLLOWUP_RESCHEDULE'
    FOLLOWUP_MISSED = 'FOLLOWUP_MISSED'
    FOLLOWUP_DELETE = 'FOLLOWUP_DELETE'

    # Activity Lifecycle Events
    ACTIVITY_CREATE = 'ACTIVITY_CREATE'
    ACTIVITY_UPDATE = 'ACTIVITY_UPDATE'
    ACTIVITY_COMPLETE = 'ACTIVITY_COMPLETE'
    ACTIVITY_CANCEL = 'ACTIVITY_CANCEL'
    ACTIVITY_DELETE = 'ACTIVITY_DELETE'

    # User Management Events
    USER_CREATE = 'USER_CREATE'
    USER_UPDATE = 'USER_UPDATE'
    USER_STATUS_CHANGE = 'USER_STATUS_CHANGE'
    USER_ROLE_CHANGE = 'USER_ROLE_CHANGE'


def log_auth_event(event_type: str, username: str = None, user_id: int = None, details: str = None):
    """Record an authentication audit event."""
    client_ip = request.remote_addr if request else '127.0.0.1'
    user_agent = request.headers.get('User-Agent', 'Unknown') if request else 'Unknown'

    log_entry = {
        'event_type': event_type,
        'username': username,
        'user_id': user_id,
        'ip_address': client_ip,
        'user_agent': user_agent,
        'details': details,
        'timestamp': datetime.utcnow().isoformat()
    }

    AUDIT_TRAIL.append(log_entry)
    logger.info(f"[AUDIT AUTH] {event_type} | User: {username or user_id} | IP: {client_ip} | Details: {details}")
    return log_entry


def log_customer_event(action: str, customer_id: int, user_id: int = None,
                       old_value: dict = None, new_value: dict = None, details: str = None):
    """Record Customer Create, Update, and Delete audit events."""
    client_ip = request.remote_addr if request else '127.0.0.1'

    event_record = {
        'UserId': user_id,
        'Action': action,
        'EntityName': 'Customer',
        'RecordId': customer_id,
        'OldValue': old_value,
        'NewValue': new_value,
        'CreatedDate': datetime.utcnow().isoformat(),
        'IpAddress': client_ip,
        'Details': details
    }

    AUDIT_TRAIL.append(event_record)
    logger.info(
        f"[AUDIT ENTITY] {action} | Entity: Customer #{customer_id} | "
        f"User: {user_id} | IP: {client_ip}"
    )
    return event_record


def log_lead_event(action: str, lead_id: int, user_id: int = None,
                   old_value: dict = None, new_value: dict = None, details: str = None):
    """Record Lead Create, Update, Delete, Status Change, and Conversion audit events."""
    client_ip = request.remote_addr if request else '127.0.0.1'

    event_record = {
        'UserId': user_id,
        'Action': action,
        'EntityName': 'Lead',
        'RecordId': lead_id,
        'OldValue': old_value,
        'NewValue': new_value,
        'CreatedDate': datetime.utcnow().isoformat(),
        'IpAddress': client_ip,
        'Details': details
    }

    AUDIT_TRAIL.append(event_record)
    logger.info(
        f"[AUDIT ENTITY] {action} | Entity: Lead #{lead_id} | "
        f"User: {user_id} | IP: {client_ip}"
    )
    return event_record


def log_opportunity_event(action: str, opportunity_id: int, user_id: int = None,
                          old_value: dict = None, new_value: dict = None, details: str = None):
    """
    Record Opportunity Create, Update, Delete, Stage Change, and Status Change audit events.
    Captures:
    - UserId, Action, EntityName ('Opportunity'), RecordId, OldValue, NewValue, CreatedDate, IpAddress
    """
    client_ip = request.remote_addr if request else '127.0.0.1'

    event_record = {
        'UserId': user_id,
        'Action': action,
        'EntityName': 'Opportunity',
        'RecordId': opportunity_id,
        'OldValue': old_value,
        'NewValue': new_value,
        'CreatedDate': datetime.utcnow().isoformat(),
        'IpAddress': client_ip,
        'Details': details
    }

    AUDIT_TRAIL.append(event_record)
    logger.info(
        f"[AUDIT ENTITY] {action} | Entity: Opportunity #{opportunity_id} | "
        f"User: {user_id} | IP: {client_ip}"
    )
    return event_record


def log_follow_up_event(action: str, follow_up_id: int, user_id: int = None,
                       old_value: dict = None, new_value: dict = None, details: str = None):
    """
    Record Follow-Up Create, Update, Complete, Reschedule, Missed, and Delete audit events.
    Captures:
    - UserId, Action, EntityName ('FollowUp'), RecordId, OldValue, NewValue, CreatedDate, IpAddress
    """
    client_ip = request.remote_addr if request else '127.0.0.1'

    event_record = {
        'UserId': user_id,
        'Action': action,
        'EntityName': 'FollowUp',
        'RecordId': follow_up_id,
        'OldValue': old_value,
        'NewValue': new_value,
        'CreatedDate': datetime.utcnow().isoformat(),
        'IpAddress': client_ip,
        'Details': details
    }

    AUDIT_TRAIL.append(event_record)
    logger.info(
        f"[AUDIT ENTITY] {action} | Entity: FollowUp #{follow_up_id} | "
        f"User: {user_id} | IP: {client_ip}"
    )
    return event_record


def log_activity_event(action: str, activity_id: int, user_id: int = None,
                      old_value: dict = None, new_value: dict = None, details: str = None):
    """
    Record Activity Create, Update, Complete, Cancel, and Delete audit events.
    Captures:
    - UserId, Action, EntityName ('Activity'), RecordId, OldValue, NewValue, CreatedDate, IpAddress
    """
    client_ip = request.remote_addr if request else '127.0.0.1'

    event_record = {
        'UserId': user_id,
        'Action': action,
        'EntityName': 'Activity',
        'RecordId': activity_id,
        'OldValue': old_value,
        'NewValue': new_value,
        'CreatedDate': datetime.utcnow().isoformat(),
        'IpAddress': client_ip,
        'Details': details
    }

    AUDIT_TRAIL.append(event_record)
    logger.info(
        f"[AUDIT ENTITY] {action} | Entity: Activity #{activity_id} | "
        f"User: {user_id} | IP: {client_ip}"
    )
    return event_record
