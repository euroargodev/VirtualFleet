from .virtualargofleet import VirtualFleet as virtualfleet
from .velocity_helpers import VelocityField as velocityfield
from ._version import version
__version__ = version

#
__all__ = (
    # Classes:
    "velocityfield",
    "virtualfleet",
    # Constants
    "__version__"
)
