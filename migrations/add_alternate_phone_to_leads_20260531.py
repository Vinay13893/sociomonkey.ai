"""
Migration: add_alternate_phone_to_leads_20260531
===============================================
Adds leads.alternate_phone for non-admin alternate contact numbers.

Run:
  cd backend
  python migrations/add_alternate_phone_to_leads_20260531.py

Set DATABASE_URL env var to target the desired database. If unset, the
application's default local database configuration is used.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import inspect, text

from app import create_app, db


def main():
    app = create_app()
    with app.app_context():
      engine = db.engine
      inspector = inspect(engine)
      columns = {col['name'] for col in inspector.get_columns('leads')}
      if 'alternate_phone' in columns:
        print('alternate_phone already exists on leads')
        return

      if engine.dialect.name == 'postgresql':
        db.session.execute(text('ALTER TABLE leads ADD COLUMN IF NOT EXISTS alternate_phone VARCHAR(50)'))
      else:
        db.session.execute(text('ALTER TABLE leads ADD COLUMN alternate_phone VARCHAR(50)'))
      db.session.commit()
      print('Added alternate_phone to leads')


if __name__ == '__main__':
    main()