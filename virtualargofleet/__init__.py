from .virtualargofleet import VirtualFleet
from .utilities import FloatConfiguration, ConfigParam
from .velocity_helpers import VelocityFieldFacade as VelocityField
from ._version import version
__version__ = version

#
__all__ = (
    # Classes:
    "VelocityField",
    "VirtualFleet",
    "FloatConfiguration",
    "ConfigParam",
    # Constants
    "__version__"
)
