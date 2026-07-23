from .auth import auth_bp
from .leads import leads_bp
from .team import team_bp
from .organisation import organisation_bp
from .configuration import configuration_bp
from .locations import locations_bp
from .projects import projects_bp
from .pipeline import pipeline_bp
from .reports import reports_bp
from .uploads import uploads_bp

__all__ = [
    'auth_bp', 'leads_bp', 'team_bp', 'organisation_bp', 'configuration_bp', 'locations_bp', 'projects_bp',
    'pipeline_bp', 'reports_bp', 'uploads_bp',
]
