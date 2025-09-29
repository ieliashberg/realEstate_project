# Backward compatibility imports
# This file is deprecated - use src.utils.http instead
import warnings

warnings.warn(
    "utils/http_utils.py is deprecated. Use 'from src.utils.http import *' instead.",
    DeprecationWarning,
    stacklevel=2
)

from src.utils.http import *


