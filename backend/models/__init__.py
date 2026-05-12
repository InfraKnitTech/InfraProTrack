# models/__init__.py — import all models here so SQLAlchemy Base knows about them
from models.user import User            # noqa
from models.manager import Manager      # noqa
from models.shift import Shift, EmployeeShiftAssignment  # noqa
from models.project import Project, ProjectTask  # noqa
from models.groups import CustomGroup, CustomGroupMember  # noqa
from models.employee import EmployeeAsset, EmployeeHistory  # noqa
from models.activity_log import ActivityLog  # noqa
from models.usage import AppUsage, BrowserUrlActivity, UrlUsage  # noqa
from models.monitoring import (         # noqa
    IdleLog,
    Screenshot,
    ProductivityScore,
    AppRule,
)
from models.agent import (              # noqa
    AgentDevice,
    AgentRegistrationRequest,
    AgentHeartbeat,
    RawAgentEvent,
    FileUsage,
)
