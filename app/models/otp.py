from datetime import datetime
from .base import db


class OtpCode(db.Model):
    """One-time password tokens for email-based login.

    Security properties:
      - otp_hash: SHA-256 of the raw OTP (never stored in plain text)
      - expires_at: configurable via OTP_EXPIRY_MINUTES (default 5 min)
      - used: set True on first successful verification OR on expiry
      - attempts: incremented on every wrong guess; blocked after 5
      - ip_address: logged for audit purposes
    """
    __tablename__ = 'otp_codes'

    __table_args__ = (
        db.Index('ix_otp_codes_email_used', 'email', 'used'),
        db.Index('ix_otp_codes_tenant_slug', 'tenant_slug'),
    )

    id          = db.Column(db.Integer, primary_key=True)
    email       = db.Column(db.String(200), nullable=False, index=True)
    otp_hash    = db.Column(db.String(64),  nullable=False)
    tenant_slug = db.Column(db.String(100), nullable=True)
    expires_at  = db.Column(db.DateTime,    nullable=False)
    used        = db.Column(db.Boolean,     default=False, nullable=False)
    attempts    = db.Column(db.Integer,     default=0,     nullable=False)
    ip_address  = db.Column(db.String(45),  nullable=True)
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Backward-compat alias (old table kept in DB; new code only writes otp_codes)
# ---------------------------------------------------------------------------
class OtpToken(db.Model):
    """Legacy table — no longer written; kept so SQLAlchemy doesn't error."""
    __tablename__ = 'otp_tokens'

    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(200), nullable=False)
    otp_hash   = db.Column(db.String(200), nullable=False)
    expires_at = db.Column(db.DateTime,    nullable=False)
    used       = db.Column(db.Boolean,     default=False, nullable=False)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow, nullable=False)
