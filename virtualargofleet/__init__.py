from packaging import version as pack_version
from .virtualargofleet import VirtualFleet
from .utilities import FloatConfiguration, ConfigParam
from .velocity_helpers import VelocityFieldFacade as VelocityField
import parcels
import warnings

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


if pack_version.parse(parcels.__version__) < pack_version.parse("2.4.0"):
    msg = "You're running Parcels %s but VirtualFleet no longer support Parcels versions " \
          "lower than 2.4.0, please upgrade." % pack_version.parse(parcels.__version__),
    warnings.warn(str(msg))

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
