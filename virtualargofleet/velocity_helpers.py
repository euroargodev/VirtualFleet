"""
Velocity Field Helper
"""

from parcels import FieldSet, ParticleSet, Field
import xarray as xr
import glob
from abc import ABC

from .app_parcels import ArgoParticle


def VelocityFieldFacade(model: str = 'GLOBAL_ANALYSIS_FORECAST_PHY_001_024', *args, **kwargs):
    """Thin layer above Parcels to manage velocity fields definition for known products

    .. warning::

        This is so thin, it may be removed in the future

    Parameters
    ----------
    model: str
        Model string definition

    Example
    -------
    >>> from virtualargofleet import VelocityField
    >>> src = "/home/datawork-lops-oh/somovar/WP1/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"  # from Datarmor
    >>> VELfield = VelocityField(model='GLOBAL_ANALYSIS_FORECAST_PHY_001_024', src="%s/2019*.nc" % src)
    >>> VELfield.plot()

    """
    if model in ['GLOBAL_ANALYSIS_FORECAST_PHY_001_024', 'PSY4QV3R1', 'GLORYS12V1']:
        V = VelocityField_GLOBAL_ANALYSIS_FORECAST_PHY_001_024(*args, **kwargs)
        V.name = 'PSY4QV3R1' if model == 'PSY4QV3R1' else V.name
        return V
    elif model in ['MEDSEA_ANALYSISFORECAST_PHY_006_013']:
        return VelocityField_MEDSEA_ANALYSISFORECAST_PHY_006_013(*args, **kwargs)
    elif model in ['MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012', 'ARMOR3D']:
        return VelocityField_MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012(*args, **kwargs)
    elif model.lower() in ['custom']:
        return VelocityField_CUSTOM(*args, **kwargs)
    else:
        raise ValueError('Unknown model')


class VelocityFieldProto(ABC):
    name = "?"

    def __repr__(self):
        summary = ["<VelocityField.%s>" % self.name]
        return "\n".join(summary)

    def plot(self):
        """Show ParticleSet"""
        temp_pset = ParticleSet(fieldset=self.fieldset,
                                pclass=ArgoParticle, lon=0, lat=0, depth=0)
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
            if not isinstance(self.field, xr.core.dataset.Dataset):
                mask_file = glob.glob(self.field['U'])[0]
                ds = xr.open_dataset(mask_file)
                ds = ds[{self.dim['time']: 0}]
                ds = ds[[self.var['U'], self.var['V']]].squeeze()
            else:
                ds = self.field[{self.dim['time']: 0}]
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


class VelocityField_CUSTOM(VelocityFieldProto):
    name = "CUSTOM"

    def __init__(self, src,
                 filenames: dict,
                 variables: dict,
                 dimensions: dict,
                 isglobal: bool = False,
                 **kwargs):

        if 'U' not in filenames:
            raise ValueError("'filenames' dictionary must have a 'U' key")
        if 'V' not in filenames:
            raise ValueError("'filenames' dictionary must have a 'V' key")
        if 'U' not in variables:
            raise ValueError("'variables' dictionary must have a 'U' key")
        if 'V' not in variables:
            raise ValueError("'variables' dictionary must have a 'V' key")

        if 'name' in kwargs:
            self.name = kwargs['name']

        if not isinstance(src, xr.core.dataset.Dataset):
            self.field = filenames  # Dictionary with 'U' and 'V' as keys and list of corresponding files as values
        else:
            self.field = src  # Xarray dataset

        self.var = variables  # Dictionary mapping 'U' and 'V' to netcdf velocity variable names
        self.dim = dimensions  # Dictionary mapping 'time', 'depth', 'lat' and 'lon' to netcdf velocity variable names
        self.isglobal = isglobal

        # Define parcels fieldset
        if not isinstance(self.field, xr.core.dataset.Dataset):
            self.fieldset = FieldSet.from_netcdf(
                self.field, self.var, self.dim,
                allow_time_extrapolation=True,
                time_periodic=False,
                deferred_load=True)
        else:
            self.fieldset = FieldSet.from_xarray_dataset(
                self.field, self.var, self.dim,
                allow_time_extrapolation=True,
                time_periodic=False)

        # Possibly handle a global field:
        self.set_global()

        # Create mask to manage grounding:
        self.add_mask()


class VelocityField_GLOBAL_ANALYSIS_FORECAST_PHY_001_024(VelocityFieldProto):
    """Velocity Field Helper for CMEMS/GLOBAL-ANALYSIS-FORECAST-PHY-001-024 product.

    Reference
    ---------
    https://resources.marine.copernicus.eu/product-detail/GLOBAL_ANALYSIS_FORECAST_PHY_001_024/DATA-ACCESS

    """
    name = "GLOBAL_ANALYSIS_FORECAST_PHY_001_024"

    def __init__(self, src, isglobal: bool = False, **kwargs):
        """

        Parameters
        ----------
        src: pattern
            Pattern to list netcdf source files
        isglobal : bool, default False
            Set to 1 if field is global, 0 otherwise
        """
        variables = {'U': 'uo', 'V': 'vo'}
        dimensions = {'time': 'time', 'depth': 'depth', 'lat': 'latitude', 'lon': 'longitude'}
        if not isinstance(src, xr.core.dataset.Dataset):
            filenames = {'U': src, 'V': src}
            self.field = filenames  # Dictionary with 'U' and 'V' as keys and list of corresponding files as values
        else:
            self.field = src  # Xarray dataset

        self.var = variables  # Dictionary mapping 'U' and 'V' to netcdf velocity variable names
        self.dim = dimensions  # Dictionary mapping 'time', 'depth', 'lat' and 'lon' to netcdf velocity variable names
        self.isglobal = isglobal

        # define parcels fieldset
        if not isinstance(src, xr.core.dataset.Dataset):
            self.fieldset = FieldSet.from_netcdf(
                self.field, self.var, self.dim,
                allow_time_extrapolation=True,
                time_periodic=False,
                deferred_load=True)
        else:
            self.fieldset = FieldSet.from_xarray_dataset(
                self.field, self.var, self.dim,
                allow_time_extrapolation=True,
                time_periodic=False)

        # Possible handle a global field:
        self.set_global()

        # Create mask to manage grounding:
        self.add_mask()


class VelocityField_MEDSEA_ANALYSISFORECAST_PHY_006_013(VelocityFieldProto):
    """Velocity Field Helper for CMEMS/MEDSEA_ANALYSISFORECAST_PHY_006_013 product.

    Reference
    ---------
    https://resources.marine.copernicus.eu/product-detail/MEDSEA_ANALYSISFORECAST_PHY_006_013/DATA-ACCESS

    """
    name = "MEDSEA_ANALYSISFORECAST_PHY_006_013"

    def __init__(self, src, **kwargs):
        """

        Parameters
        ----------
        src: pattern
            Pattern to list netcdf source files
        isglobal : bool, default False
            Set to 1 if field is global, 0 otherwise
        """
        filenames = {'U': src, 'V': src}
        variables = {'U': 'uo', 'V': 'vo'}
        dimensions = {'time': 'time', 'depth': 'depth', 'lat': 'lat', 'lon': 'lon'}

        self.field = filenames  # Dictionary with 'U' and 'V' as keys and list of corresponding files as values
        self.var = variables  # Dictionary mapping 'U' and 'V' to netcdf velocity variable names
        self.dim = dimensions  # Dictionary mapping 'time', 'depth', 'lat' and 'lon' to netcdf velocity variable names

        # define parcels fieldset
        self.fieldset = FieldSet.from_netcdf(
            self.field, self.var, self.dim,
            allow_time_extrapolation=True,
            time_periodic=False,
            deferred_load=True)

        # Create mask to manage grounding:
        self.add_mask()


class VelocityField_MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012(VelocityFieldProto):
    """Velocity Field Helper for CMEMS/ARMOR3D product.

    Reference
    ---------
    https://resources.marine.copernicus.eu/product-detail/MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012/DATA-ACCESS

    """
    name = "ARMOR3D.MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012"

    def __init__(self, src, isglobal: bool = False, **kwargs):
        """

        Parameters
        ----------
        src: pattern
            Pattern to list netcdf source files
        isglobal : bool, default False
            Set to 1 if field is global, 0 otherwise
        """
        variables = {'U': 'ugo', 'V': 'vgo'}
        dimensions = {'time': 'time', 'depth': 'depth', 'lat': 'latitude', 'lon': 'longitude'}
        if not isinstance(src, xr.core.dataset.Dataset):
            filenames = {'U': src, 'V': src}
            self.field = filenames  # Dictionary with 'U' and 'V' as keys and list of corresponding files as values
        else:
            self.field = src  # Xarray dataset

        self.var = variables  # Dictionary mapping 'U' and 'V' to netcdf velocity variable names
        self.dim = dimensions  # Dictionary mapping 'time', 'depth', 'lat' and 'lon' to netcdf velocity variable names
        self.isglobal = isglobal

        # define parcels fieldset
        if not isinstance(src, xr.core.dataset.Dataset):
            self.fieldset = FieldSet.from_netcdf(
                self.field, self.var, self.dim,
                allow_time_extrapolation=True,
                time_periodic=False,
                deferred_load=True)
        else:
            self.fieldset = FieldSet.from_xarray_dataset(
                self.field, self.var, self.dim,
                allow_time_extrapolation=True,
                time_periodic=False)

        # Possible handle a global field:
        self.set_global()

        # Create mask to manage grounding:
        self.add_mask()
