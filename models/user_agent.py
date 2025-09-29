# Backward compatibility imports
# This file is deprecated - use src.scrapers.user_agents.models instead
import warnings

warnings.warn(
    "models/user_agent.py is deprecated. Use 'from src.scrapers.user_agents.models import *' instead.",
    DeprecationWarning,
    stacklevel=2
)

from src.scrapers.user_agents.models import *


