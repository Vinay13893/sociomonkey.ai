from datetime import datetime


# 18 Jun 2026 03:21 pm IST, stored as naive UTC to match the app DB timestamps.
GANGA_LEAD_SOURCE_CUTOFF_UTC = datetime(2026, 6, 18, 9, 51)


def _tenant_slug_from(obj) -> str:
    tenant = getattr(obj, 'tenant', None)
    slug = getattr(tenant, 'slug', None)
    return str(slug or '').strip().lower()


def is_ganga_tenant(obj=None, tenant_id=None) -> bool:
    if _tenant_slug_from(obj) == 'ganga':
        return True
    if tenant_id is None and obj is not None:
        tenant_id = getattr(obj, 'tenant_id', None)
    return str(tenant_id or '').strip() == '1'


def lead_source_cutoff_for(obj=None, tenant_id=None):
    if is_ganga_tenant(obj, tenant_id=tenant_id):
        return GANGA_LEAD_SOURCE_CUTOFF_UTC
    return None


def effective_start_with_cutoff(source_obj=None, requested_start=None):
    candidates = [
        value for value in (
            requested_start,
            lead_source_cutoff_for(source_obj),
        )
        if value is not None
    ]
    return max(candidates) if candidates else None


def is_before_lead_source_cutoff(value, obj=None, tenant_id=None) -> bool:
    cutoff = lead_source_cutoff_for(obj, tenant_id=tenant_id)
    return bool(cutoff and value and value < cutoff)
