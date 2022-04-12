__author__ = 'kbalem@ifremer.fr, gmaze@ifremer.fr'  # Should be removed in the future

import warnings

from parcels import FieldSet, ParticleSet, AdvectionRK4, ErrorCode, Field
from datetime import timedelta
import xarray as xr
import os
import glob
import tempfile

from .application_kernels import ArgoParticle, DeleteParticle, ArgoVerticalMovement, periodicBC


class VelocityField:
    """Velocity Field Helper."""

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


class VirtualFleet:
    """Argo Virtual Fleet simulator."""

    def __init__(self, **kwargs):
        """
        Parameters
        ----------
        lat,lon,depth,time : numpy arrays describing where Argo floats are deployed
        vfield : :class:`virtualargofleet.velocityfield`
        mission : dictionary {'parking_depth':parking_depth, 'profile_depth':profile_depth, 'vertical_speed':vertical_speed, 'cycle_duration':cycle_duration}
        """
        # props
        self.lat = kwargs['lat']
        self.lon = kwargs['lon']
        self.depth = kwargs['depth']
        self.time = kwargs['time']
        vfield = kwargs['vfield']
        mission = kwargs['mission']
        # Pass mission parameters to simulation through fieldset
        vfield.fieldset.add_constant('parking_depth', mission['parking_depth'])
        vfield.fieldset.add_constant('profile_depth', mission['profile_depth'])
        vfield.fieldset.add_constant('v_speed', mission['vertical_speed'])
        vfield.fieldset.add_constant(
            'cycle_duration', mission['cycle_duration'])

        # Define parcels :class:`parcels.particleset.particlesetsoa.ParticleSetSOA`
        self.pset = ParticleSet(fieldset=vfield.fieldset,
                                pclass=ArgoParticle,
                                lon=self.lon,
                                lat=self.lat,
                                depth=self.depth,
                                time=self.time)
        if vfield.isglobal:
            # combine Argo vertical movement kernel with Advection kernel + boundaries
            self.kernels = ArgoVerticalMovement + \
                self.pset.Kernel(AdvectionRK4) + self.pset.Kernel(periodicBC)
        else:
            self.kernels = ArgoVerticalMovement + \
                self.pset.Kernel(AdvectionRK4)

    @property
    def ParticleSet(self):
        """Container class for storing particle and executing kernel over them.

        Returns
        -------
        :class:`parcels.particleset.particlesetsoa.ParticleSetSOA`
        """
        return self.pset

    def show_deployment(self):
        """Method to show where Argo Floats have been deployed

        Using parcels psel builtin show function for now
        """
        self.pset.show()

    def plotfloat(self):
        warnings.warn("'plotfloat' has been replaced by 'show_deployment'", category=DeprecationWarning, stacklevel=2)
        return self.show_deployment()

    def simulate(self, **kwargs):
        """Execute Virtual Fleet simulation

        Inputs
        ------
        duration: int,
            Number of days (365)
        dt_run: float
            Time step in hours for the computation (1/12)
        dt_out: float
            Time step in hours for writing the output (24)
        output_file: str
            Name of the netcdf file where to store simulation results
        """
        duration = kwargs['duration']
        dt_run = kwargs['dt_run']
        dt_out = kwargs['dt_out']
        output_path = kwargs['output_file']

        if ((os.path.exists(output_path)) | (output_path == '')):
            temp_name = next(tempfile._get_candidate_names())+'.nc'
            while os.path.exists(temp_name):
                temp_name = next(tempfile._get_candidate_names())+'.nc'
            output_path = temp_name
            print(
                "Filename empty of file already exists, simulation will be saved in : " + output_path)
        else:
            print("Simulation will be saved in : " + output_path)
        self.run_params = {'duration': duration, 'dt_run': dt_run,
                           'dt_out': dt_out, 'output_file': output_path}

        output_file = self.pset.ParticleFile(
            name=output_path, outputdt=timedelta(hours=dt_out))
        # Now execute the kernels for X days, saving data every Y minutes
        self.pset.execute(self.kernels,
                          runtime=timedelta(days=duration),
                          dt=timedelta(hours=dt_run),
                          output_file=output_file,
                          recovery={ErrorCode.ErrorOutOfBounds: DeleteParticle})
        output_file.export()
        output_file.close()
