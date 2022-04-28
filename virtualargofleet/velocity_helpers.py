
from parcels import FieldSet, ParticleSet, Field
import xarray as xr
import glob

from .application_kernels import ArgoParticle


class VelocityField:
    """Velocity Field Helper.

    Thin layer above Parcels to manage velocity fields definition.

    (This is so thin, it may be remove in the future).

    """

    def __init__(self, ds, var, dim, isglobal: bool = False, **kwargs):
        """

        .. warning::

            This should evolve as more grid/dataset become supported


        Parameters
        ----------
        ds: dict
            Dictionary with 'U' and 'V' as keys and list of corresponding files as values
        var: dict
            Dictionary mapping 'U' and 'V' to netcdf velocity variable names
        dim: dict
            Dictionary mapping 'time', 'depth', 'lat' and 'lon' to netcdf velocity variable names
        isglobal : bool, default False
            Set to 1 if field is global, 0 otherwise
        """
        self.field = ds
        self.var = var
        self.dim = dim
        self.isglobal = isglobal

        # define parcels fieldset
        self.fieldset = FieldSet.from_netcdf(
            self.field, self.var, self.dim, allow_time_extrapolation=True, time_periodic=False)

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

        # create mask for grounding management
        mask_file = glob.glob(self.field['U'])[0]
        ds = xr.open_dataset(mask_file)
        ds = eval("ds.isel("+self.dim['time']+"=0)")
        ds = ds[[self.var['U'],self.var['V']]].squeeze()

        mask = ~(ds.where((~ds[self.var['U']].isnull()) | (~ds[self.var['V']].isnull()))[
                 self.var['U']].isnull()).transpose(self.dim['lon'], self.dim['lat'], self.dim['depth'])
        mask = mask.values
        # create a new parcels field that's going to be interpolated during simulation
        self.fieldset.add_field(Field('mask', data=mask, lon=ds[self.dim['lon']].values, lat=ds[self.dim['lat']].values, depth=ds[self.dim['depth']].values,
                                      transpose=True, mesh='spherical', interp_method='nearest'))

    def plot(self):
        """Show ParticleSet"""
        temp_pset = ParticleSet(fieldset=self.fieldset,
                                pclass=ArgoParticle, lon=0, lat=0, depth=0)
        temp_pset.show(field=self.fieldset.U, with_particles=False)
        #temp_pset.show(field = self.fieldset.V,with_particles = False)

