from .virtualargofleet import VirtualFleet
from .utilities import FloatConfiguration, ConfigParam
from .velocity_helpers import VelocityFieldFacade as Velocity
from .velocity_helpers import VelocityField

import parcels
import warnings
from packaging.version import parse as parse_version
try:
    from importlib.metadata import version as il_version
except ImportError:
    # if the fallback library is missing, we are doomed.
    from importlib_metadata import version as il_version


try:
    __version__ = il_version("virtualfleet")
except Exception:
    # Local copy or not installed with setuptools.
    # Disable minimum version checks on downstream libraries.
    __version__ = '999'


parcels_version = parcels.__version__.replace("v","").split(".")
if int(parcels_version[0]) < 2 or (int(parcels_version[0]) == 2 and int(parcels_version[1]) < 4):
    msg = "You're running Parcels %s but VirtualFleet no longer support Parcels versions " \
          "strictly lower than 2.4, please upgrade." % parcels.__version__,
    warnings.warn(str(msg))

#
__all__ = (
    # Classes:
    "Velocity",
    "VelocityField",
    "VirtualFleet",
    "FloatConfiguration",
    "ConfigParam",
    # Constants
    "__version__"
)
