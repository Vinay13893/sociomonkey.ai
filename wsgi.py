import os
from dotenv import load_dotenv

# Load .env before app initialisation so Railway/Render env vars take effect
# in local runs.  In CI/production, real env vars simply win (load_dotenv
# does NOT overwrite already-set environment variables by default).
load_dotenv()

from app import create_app
from app.config import get_config_name

application = create_app(get_config_name('production'))

if __name__ == '__main__':
    application.run()
