"""
Cron endpoints for background job processing.

Designed for Vercel Cron Jobs (vercel.json crons array).
Auth: Bearer token matching CRON_SECRET env var.  Set the same secret
in vercel.json under `crons[].headers` or send it as a query param
(query param is fine since Vercel cron calls are internal).

Endpoints:
  GET  /api/cron/drain-notifications
       Process queued NotificationEvent rows → Web Push delivery.
       Run every minute in production.

  GET  /api/cron/health
       Lightweight health-check for cron monitoring.
"""
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app

logger = logging.getLogger(__name__)

cron_bp = Blueprint('cron', __name__, url_prefix='/api/cron')


def _auth_cron():
    """Return True if the cron request carries the correct CRON_SECRET or Vercel cron header."""
    # Vercel automatically injects 'x-vercel-cron: 1' on all cron invocations.
    from flask import request as _req
    if _req.headers.get('x-vercel-cron') == '1':
        return True
    secret = current_app.config.get('CRON_SECRET', '')
    if not secret:
        # No secret configured — open in dev / staging only.
        # In production you MUST set CRON_SECRET.
        env = current_app.config.get('ENV', 'development')
        if env in ('production', 'prod'):
            return False
        return True

    # Accept: Authorization: Bearer <secret>  OR  ?secret=<secret>
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip() == secret
    query_secret = request.args.get('secret', '')
    return query_secret == secret


@cron_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'ok': True, 'ts': datetime.utcnow().isoformat()}), 200


@cron_bp.route('/drain-notifications', methods=['GET', 'POST'])
def drain_notifications():
    """
    Process queued notification events and deliver them via Web Push.

    Vercel Cron configuration (vercel.json):
      {
        "crons": [
          {
            "path": "/api/cron/drain-notifications",
            "schedule": "* * * * *"
          }
        ]
      }
    """
    if not _auth_cron():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from app.services.notification_processor import process_notification_queue
        batch = int(request.args.get('batch', 50))
        batch = max(1, min(batch, 200))  # clamp 1\u2013200
        summary = process_notification_queue(batch_size=batch)

        logger.info('[Cron] drain-notifications complete: %s', summary)
        return jsonify({
            'ok': True,
            'ts': datetime.utcnow().isoformat(),
            'summary': summary,
        }), 200

    except Exception as exc:
        logger.exception('[Cron] drain-notifications error: %s', exc)
        return jsonify({'ok': False, 'error': str(exc)}), 500
