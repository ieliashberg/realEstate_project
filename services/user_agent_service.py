# Backward compatibility imports
# This file is deprecated - use src.scrapers.user_agents.service instead
import warnings

warnings.warn(
    "services/user_agent_service.py is deprecated. Use 'from src.scrapers.user_agents.service import *' instead.",
    DeprecationWarning,
    stacklevel=2
)

from src.scrapers.user_agents.service import *


