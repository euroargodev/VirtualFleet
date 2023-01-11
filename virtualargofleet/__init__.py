from packaging import version as pack_version
from .virtualargofleet import VirtualFleet
from .utilities import FloatConfiguration, ConfigParam
from .velocity_helpers import VelocityFieldFacade as VelocityField
from ._version import version
__version__ = version
import parcels


if pack_version.parse(parcels.__version__) < pack_version.parse("2.4.0"):
    msg = "You're running Parcels %s but VirtualFleet no longer support Parcels versions " \
          "lower than 2.4.0, please upgrade." % pack_version.parse(parcels.__version__),
    raise ValueError(msg)

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
