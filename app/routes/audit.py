"""
Audit Log Viewer Routes for Acxiom CRM.
Admin-only read-only interface displaying system audit trail and filtering.
"""
from datetime import datetime
from flask import Blueprint, render_template, request
from flask_login import current_user
from app.utils.decorators import admin_required
from app.services.audit_service import AUDIT_TRAIL
from app.models.user import User

audit_bp = Blueprint('audit', __name__)


@audit_bp.route('/audit-logs')
@admin_required
def index():
    """
    Admin-only read-only Audit Log viewer.
    Supports filtering by Action, Entity, User, and Search keyword.
    """
    action_filter = request.args.get('action', '').strip()
    entity_filter = request.args.get('entity', '').strip()
    user_filter = request.args.get('user', '').strip()
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 25

    # Normalize records from AUDIT_TRAIL (most recent first)
    normalized_logs = []
    # Build user lookup cache
    users_cache = {u.id: u.username for u in User.query.all()}

    for item in reversed(AUDIT_TRAIL):
        # Extract normalized attributes
        action = item.get('Action') or item.get('event_type') or 'UNKNOWN'
        entity = item.get('EntityName') or ('Auth' if 'event_type' in item else 'System')
        record_id = item.get('RecordId')
        user_id = item.get('UserId') or item.get('user_id')
        username = item.get('username') or users_cache.get(user_id) or (f"User #{user_id}" if user_id else "Anonymous/System")
        ip_addr = item.get('IpAddress') or item.get('ip_address') or '127.0.0.1'
        created_date = item.get('CreatedDate') or item.get('timestamp') or ''
        old_val = item.get('OldValue')
        new_val = item.get('NewValue')
        details = item.get('Details') or item.get('details') or ''

        # Apply Filters
        if action_filter and action_filter.lower() != action.lower():
            continue
        if entity_filter and entity_filter.lower() != entity.lower():
            continue
        if user_filter and user_filter.lower() not in username.lower() and str(user_id) != user_filter:
            continue
        if search_query:
            searchable = f"{action} {entity} {record_id} {username} {ip_addr} {details} {old_val} {new_val}".lower()
            if search_query.lower() not in searchable:
                continue

        normalized_logs.append({
            'created_date': created_date,
            'user': username,
            'user_id': user_id,
            'action': action,
            'entity_name': entity,
            'record_id': record_id,
            'old_value': old_val,
            'new_value': new_val,
            'ip_address': ip_addr,
            'details': details
        })

    # Available filter options for dropdowns
    available_actions = sorted(list(set(
        (e.get('Action') or e.get('event_type') or 'UNKNOWN') for e in AUDIT_TRAIL
    )))
    available_entities = sorted(list(set(
        (e.get('EntityName') or ('Auth' if 'event_type' in e else 'System')) for e in AUDIT_TRAIL
    )))

    total_count = len(normalized_logs)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_logs = normalized_logs[start_idx:end_idx]
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template(
        'audit/index.html',
        logs=paginated_logs,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        available_actions=available_actions,
        available_entities=available_entities,
        action_filter=action_filter,
        entity_filter=entity_filter,
        user_filter=user_filter,
        search_query=search_query
    )
