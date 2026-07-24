from flask import request
from app.models.base import db
from app.models.activity import ActivityLog


def log_activity(
    user_id: int,
    action: str,
    module: str,
    resource_id: int = None,
    resource_type: str = None,
    old_value=None,
    new_value=None,
    description: str = None,
    tenant_id=None,
    correlation_id=None,
):
    """Persist an activity log entry. Safe to call from any request context."""
    try:
        ip = request.remote_addr
    except RuntimeError:
        ip = None

    entry = ActivityLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        module=module,
        resource_id=resource_id,
        resource_type=resource_type,
        old_value=old_value,
        new_value=new_value,
        description=description,
        correlation_id=correlation_id,
        ip_address=ip,
    )
    db.session.add(entry)
    db.session.commit()
