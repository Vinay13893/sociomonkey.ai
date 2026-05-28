#!/usr/bin/env python3
"""
Migration: create otp_codes table in Neon PostgreSQL.

Run once on Railway:
    railway run python migrate_add_otp_codes.py

Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS.
"""
import os, sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.", file=sys.stderr)
    sys.exit(1)

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

print(f"Connecting to: {DATABASE_URL[:60]}...")

import psycopg2

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor()

DDL = """
CREATE TABLE IF NOT EXISTS otp_codes (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(200) NOT NULL,
    otp_hash    VARCHAR(64)  NOT NULL,
    tenant_slug VARCHAR(100),
    expires_at  TIMESTAMP    NOT NULL,
    used        BOOLEAN      NOT NULL DEFAULT FALSE,
    attempts    INTEGER      NOT NULL DEFAULT 0,
    ip_address  VARCHAR(45),
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_otp_codes_email
    ON otp_codes (email);

CREATE INDEX IF NOT EXISTS ix_otp_codes_email_used
    ON otp_codes (email, used);

CREATE INDEX IF NOT EXISTS ix_otp_codes_tenant_slug
    ON otp_codes (tenant_slug);
"""

try:
    cur.execute(DDL)
    conn.commit()
    print("✓ otp_codes table and indexes created (or already exist).")
except Exception as exc:
    conn.rollback()
    print(f"ERROR: {exc}", file=sys.stderr)
    sys.exit(1)
finally:
    cur.close()
    conn.close()
