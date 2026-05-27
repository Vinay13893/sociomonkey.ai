import sys
import os

# Add the backend directory to path so 'app' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.config import get_config_name

app = create_app(get_config_name('production'))
