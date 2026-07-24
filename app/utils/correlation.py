"""Correlation identifiers shared by operational business events."""

import uuid


def correlation_id(value=None):
    """Return a bounded correlation ID, generating one when absent."""
    candidate = str(value or '').strip()
    if candidate:
        return candidate[:36]
    return str(uuid.uuid4())


def request_correlation_id(request):
    """Read the public request correlation header without trusting its length."""
    return correlation_id(request.headers.get('X-Correlation-ID'))
