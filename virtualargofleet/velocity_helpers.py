"""
Velocity Field Helper
"""

from parcels import FieldSet, ParticleSet, Field
import xarray as xr
import glob
from abc import ABC
import logging
from .app_parcels import ArgoParticle


log = logging.getLogger("virtualfleet.velocity")


class VelocityField(ABC):
    """Class prototype to manage a Virtual Fleet velocity field

    This prototype provides useful methods to prepare a :class:`parcels.fieldset.FieldSet` for a VirtualFleet simulation.
    A :class:`VelocityField` instance can be passed directly to a :class:`.VirtualFleet` instance.

    You can use the :meth:`Velocity` function to instantiate such a class for known products.

    """
    name = "?"
    """shortname ID for this velocity field"""

    field = None
    """Internal definition of the velocity fields; it can be a :class:`xarray.Dataset` or a dictionary with ``U`` 
    and ``V`` as keys and list of corresponding files as values"""

    fieldset = None
    """Instance of :class:`parcels.fieldset.FieldSet` created using the ``field`` attribute"""

    var = None
    """Variable dictionary mapping of ``U`` and ``V`` on netcdf velocity variable names"""

    dim = None
    """Dimensions dictionary mapping of ``time``, ``depth``, ``lat`` and ``lon`` on netcdf velocity variable names"""

    isglobal = None
    """Boolean indicating weather the velocity field is global or not, used to add ``halo_*`` constants on the 
    ``fieldset`` attribute"""


    def __repr__(self):
        summary = ["<VelocityField.%s>" % self.name]
        return "\n".join(summary)

    def plot(self):
        """Quick plot of the ParticleSet"""
        temp_pset = ParticleSet(fieldset=self.fieldset, pclass=ArgoParticle, lon=0, lat=0, depth=0)
        temp_pset.show(field=self.fieldset.U, with_particles=False)
        # temp_pset.show(field = self.fieldset.V,with_particles = False)

    def add_mask(self):
        """Create mask for grounding management

        Requires:
            - ``self.field`` with ``U`` and ``V`` keys
            - ``self.dim`` with ``lon``, ``lat``, ``depth`` and ``time`` keys
            - ``self.var`` with ``U`` and ``V`` keys
        """
        if self.fieldset:
            if isinstance(self.field, xr.core.dataset.Dataset):
                ds = self.field[{self.dim['time']: 0}]
                ds = ds[[self.var['U'], self.var['V']]].squeeze()
            else:
                mask_file = glob.glob(self.field['U'])[0]
                # log.debug('mask_file: %s' % mask_file)
                ds = xr.open_dataset(mask_file)
                ds = ds[{self.dim['time']: 0}]
                ds = ds[[self.var['U'], self.var['V']]].squeeze()

            mask = ~(ds.where((~ds[self.var['U']].isnull()) | (~ds[self.var['V']].isnull()))[
                     self.var['U']].isnull()).transpose(self.dim['lon'], self.dim['lat'], self.dim['depth'])
            mask = mask.values

            # create a new parcels field that's going to be interpolated during simulation
            self.fieldset.add_field(Field('mask',
                                          data=mask,
                                          lon=ds[self.dim['lon']].values,
                                          lat=ds[self.dim['lat']].values,
                                          depth=ds[self.dim['depth']].values,
                                          transpose=True,
                                          mesh='spherical',
                                          interp_method='nearest'))
        else:
            raise ValueError("Can't create mask because `fieldset` is not defined")

    def set_global(self):
        """Ensure a global fieldset"""
        if self.isglobal:
            self.fieldset.add_constant(
                'halo_west', self.fieldset.U.grid.lon[0])
            self.fieldset.add_constant(
                'halo_east', self.fieldset.U.grid.lon[-1])
            self.fieldset.add_constant(
                'halo_south', self.fieldset.U.grid.lat[0])
            self.fieldset.add_constant(
                'halo_north', self.fieldset.U.grid.lat[-1])
            self.fieldset.add_periodic_halo(zonal=True, meridional=True)


class VelocityField_CUSTOM(VelocityField):
    name = "CUSTOM"

    def __init__(self,
                 src,
                 variables: dict,
                 dimensions: dict,
                 isglobal: bool = False,
                 **kwargs):
        """Create a custom VelocityField for known products"""

        if 'U' not in variables:
            raise ValueError("'variables' dictionary must have a 'U' key")
        if 'V' not in variables:
            raise ValueError("'variables' dictionary must have a 'V' key")

        if isinstance(src, xr.core.dataset.Dataset):
            # If the source data is a Xarray dataset, we ensure to have all the required variables and coordinates:
            for v in variables:
                if variables[v] not in src.data_vars:
                    raise ValueError("'src' xarray DataSet must have a '%s' variable for %s" % (variables[v], v))
            for dim in dimensions:
                if dimensions[dim] not in src.coords:
                    raise ValueError("'src' xarray DataSet must have a '%s' coordinate for %s" % (dimensions[dim], dim))

        elif isinstance(src, dict):
            if 'U' not in src:
                raise ValueError("'src' as a dictionary must have a 'U' key")
            if 'V' not in src:
                raise ValueError("'src' as a dictionary must have a 'V' key")

        else:
            raise ValueError("'src' must be a dictionary or a xarray Dataset")

        if 'name' in kwargs:
            self.name = kwargs['name']

        self.var = variables  # Dictionary mapping 'U' and 'V' to netcdf velocity variable names
        self.dim = dimensions  # Dictionary mapping 'time', 'depth', 'lat' and 'lon' to netcdf velocity variable names
        self.isglobal = isglobal

        # Define parcels fieldset
        if not isinstance(src, xr.core.dataset.Dataset):
            self.field = src  # Dictionary with 'U' and 'V' as keys and list of corresponding files as values
            self.fieldset = FieldSet.from_netcdf(
                src, self.var, self.dim,
                allow_time_extrapolation=True,
                time_periodic=False,
                deferred_load=True)
        else:
            self.field = src  # Xarray dataset
            self.fieldset = FieldSet.from_xarray_dataset(
                src, self.var, self.dim,
                allow_time_extrapolation=True,
                time_periodic=False)

        # Possibly handle a global field:
        self.set_global()

        # Create mask to manage grounding:
        self.add_mask()


def VelocityFieldFacade(model: str = 'GLOBAL_ANALYSIS_FORECAST_PHY_001_024', *args, **kwargs):
    """Function to return a :class:`VelocityField` instance for known products

    Note that you can provide a :class:`VelocityField` or :attr:`VelocityField.fieldset`
    to a :class:`VirtualFleet` instance.

    Parameters
    ----------
    model: str
        Indicate which model to use by its string definition. Possible values are:
            -  ``custom`` if you want to set your own model definition
            -  ``GLORYS12V1``, ``PSY4QV3R1``, ``GLOBAL_ANALYSIS_FORECAST_PHY_001_024``
            -  ``MEDSEA_ANALYSISFORECAST_PHY_006_013``
            -  ``ARMOR3D``, ``MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012``

    Returns
    -------
    :class:`VelocityField`

    Examples
    --------
    Import the module and define the root folder to data:

    >>> from virtualargofleet import Velocity
    >>> root = "/home/datawork-lops-oh/somovar/WP1/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"

    And then define a velocity field with one of the following 3 methods:

    1/ with a ``custom`` product:

    >>> filenames = {'U': root + "/20201210*.nc",
    >>>              'V': root + "/20201210*.nc"}
    >>> variables = {'U':'uo','V':'vo'}
    >>> dimensions = {'time': 'time', 'depth':'depth', 'lat': 'latitude', 'lon': 'longitude'}
    >>> VELfield = Velocity(model='custom', src=filenames, variables=variables, dimensions=dimensions)

    2/ with a :class:`xarray.Dataset`:

    >>> ds = xr.open_mfdataset(glob.glob("%s/20201210*.nc" % root))
    >>> VELfield = Velocity(model='GLOBAL_ANALYSIS_FORECAST_PHY_001_024', src=ds)

    3/ with a file path pattern:

    >>> VELfield = Velocity(model='GLORYS12V1', src="%s/20201210*.nc" % root)
    """
    if model in ['PSY4QV3R1', 'GLOBAL_ANALYSIS_FORECAST_PHY_001_024', 'GLORYS12V1']:
        V = VelocityField_PSY4QV3R1(**kwargs)
        V.name = 'GLOBAL_ANALYSIS_FORECAST_PHY_001_024' if model == 'GLOBAL_ANALYSIS_FORECAST_PHY_001_024' else V.name
        V.name = 'PSY4QV3R1' if model == 'PSY4QV3R1' else V.name
        V.name = 'GLORYS12V1' if model == 'GLORYS12V1' else V.name
        return V

    elif model in ['MEDSEA_ANALYSISFORECAST_PHY_006_013']:
        V = VelocityField_MEDSEA_ANALYSISFORECAST_PHY_006_013(**kwargs)
        return V

    elif model in ['MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012', 'ARMOR3D']:
        V = VelocityField_ARMOR3D(**kwargs)
        V.name = 'ARMOR3D.MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012' if "MULTIOBS" in model else V.name
        return V

    elif model.lower() in ['custom']:
        return VelocityField_CUSTOM(*args, **kwargs)

    else:
        raise ValueError('Unknown model')


def VelocityField_PSY4QV3R1(**kwargs):
    """Velocity Field Helper for CMEMS/GLOBAL-ANALYSIS-FORECAST-PHY-001-024 product.

    Reference
    ---------
    https://resources.marine.copernicus.eu/product-detail/GLOBAL_ANALYSIS_FORECAST_PHY_001_024/DATA-ACCESS

    """
    if 'src' not in kwargs:
        raise ValueError("You must provide a 'src' dictionary or xarray dataset.")
    elif isinstance(kwargs['src'], xr.core.dataset.Dataset):
        src = kwargs['src']
    else:
        src = {'U': kwargs['src'],
               'V': kwargs['src']}
    variables = {'U': 'uo',
                 'V': 'vo'}
    dimensions = {'time': 'time',
                  'depth': 'depth',
                  'lat': 'latitude',
                  'lon': 'longitude'}
    isglobal = kwargs['isglobal'] if 'isglobal' in kwargs else False
    V = VelocityField_CUSTOM(src=src, variables=variables, dimensions=dimensions, isglobal=isglobal)
    V.name = 'PSY4QV3R1'
    return V


def VelocityField_MEDSEA_ANALYSISFORECAST_PHY_006_013(**kwargs):
    """Velocity Field Helper for CMEMS/MEDSEA_ANALYSISFORECAST_PHY_006_013 product.

    Reference
    ---------
    https://resources.marine.copernicus.eu/product-detail/MEDSEA_ANALYSISFORECAST_PHY_006_013/DATA-ACCESS

    """
    if 'src' not in kwargs:
        raise ValueError("You must provide a 'src' dictionary or xarray dataset.")
    elif isinstance(kwargs['src'], xr.core.dataset.Dataset):
        src = kwargs['src']
    else:
        src = {'U': kwargs['src'],
               'V': kwargs['src']}
    variables = {'U': 'uo',
                 'V': 'vo'}
    dimensions = {'time': 'time',
                  'depth': 'depth',
                  'lat': 'lat',
                  'lon': 'lon'}
    V = VelocityField_CUSTOM(src=src, variables=variables, dimensions=dimensions, isglobal=False)
    V.name = 'MEDSEA_ANALYSISFORECAST_PHY_006_013'
    return V


def VelocityField_ARMOR3D(**kwargs):
    """Velocity Field Helper for CMEMS/ARMOR3D product.

    Reference
    ---------
    https://resources.marine.copernicus.eu/product-detail/MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012/DATA-ACCESS

    """
    if 'src' not in kwargs:
        raise ValueError("You must provide a 'src' dictionary or xarray dataset.")
    elif isinstance(kwargs['src'], xr.core.dataset.Dataset):
        src = kwargs['src']
    else:
        src = {'U': kwargs['src'],
               'V': kwargs['src']}
    variables = {'U': 'ugo',
                 'V': 'vgo'}
    dimensions = {'time': 'time',
                  'depth': 'depth',
                  'lat': 'latitude',
                  'lon': 'longitude'}
    isglobal = kwargs['isglobal'] if 'isglobal' in kwargs else False
    V = VelocityField_CUSTOM(src=src, variables=variables, dimensions=dimensions, isglobal=isglobal)
    V.name = 'ARMOR3D'
    return V