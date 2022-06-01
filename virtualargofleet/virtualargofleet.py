import warnings
from parcels import ParticleSet, AdvectionRK4, ErrorCode
import datetime
from datetime import timedelta
import os
import tempfile
import numpy as np
from .app_parcels import ArgoParticle, DeleteParticleKernel, ArgoFloatKernel, PeriodicBoundaryConditionKernel


class VirtualFleet:
    """Argo Virtual Fleet simulator helper.

    This class should make it easier to process and analyse a simulation.

    """

    def __init__(self, **kwargs):
        """
        Parameters
        ----------
        lat, lon, depth, time:
            Numpy arrays describing where Argo floats are deployed. Depth is optional, if not provided it will be set to 1m.
        vfield: :class:`virtualargofleet.VelocityFieldProto`
        mission: dict
            Dictionary with Argo float parameters {'parking_depth': parking_depth, 'profile_depth': profile_depth, 'vertical_speed': vertical_speed, 'cycle_duration': cycle_duration}
        """
        # props
        self.lat = kwargs['lat']
        self.lon = kwargs['lon']
        if 'depth' not in kwargs:
            self.depth = np.full(self.lat.shape, 1.0)
        else:
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
        self.run_params = {}
        if vfield.isglobal:
            # combine Argo vertical movement kernel with Advection kernel + boundaries
            self.kernels = ArgoFloatKernel + \
                           self.pset.Kernel(AdvectionRK4) + self.pset.Kernel(PeriodicBoundaryConditionKernel)
        else:
            self.kernels = ArgoFloatKernel + \
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
        duration: timedelta,
            Eg: timedelta(days=365)
        step: timedelta
            Time step for the computation
            Eg: timedelta(minutes=5)
        record: timedelta
            Time step for writing the output
            Eg: timedelta(hours=1)
        output_file: str
            Name of the netcdf file where to store simulation results
        output_folder: str
            Name of folder where to store 'output_file'
        """
        duration = kwargs['duration'] if isinstance(kwargs['duration'], datetime.timedelta) else timedelta(hours=kwargs['duration'])
        dt_run = kwargs['step'] if isinstance(kwargs['step'], datetime.timedelta) else timedelta(hours=kwargs['step'])
        dt_out = kwargs['record'] if isinstance(kwargs['record'], datetime.timedelta) else timedelta(hours=kwargs['record'])
        output_file = kwargs['output_file'] if 'output_file' in kwargs else ""
        output_folder = kwargs['output_folder'] if 'output_folder' in kwargs else "."
        output_path = os.path.join(output_folder, output_file)

        if os.path.exists(output_path) or output_path[0] == ".":
            temp_name = next(tempfile._get_candidate_names())+'.nc'
            while os.path.exists(temp_name):
                temp_name = next(tempfile._get_candidate_names())+'.nc'
            output_path = os.path.join(output_folder, temp_name)
            print("Empty 'output_file' or file already exists, simulation will be saved in : " + output_path)
        else:
            print("Simulation will be saved in : " + output_path)
        self.run_params = {'duration': duration,
                           'step': dt_run,
                           'record': dt_out,
                           'output_file': output_path}

        output_file = self.pset.ParticleFile(name=self.run_params['output_file'],
                                             outputdt=self.run_params['record'])
        # Now execute the kernels for X days, saving data every Y minutes
        self.pset.execute(self.kernels,
                          runtime=self.run_params['duration'],
                          dt=self.run_params['step'],
                          output_file=output_file,
                          recovery={ErrorCode.ErrorOutOfBounds: DeleteParticleKernel})
        output_file.export()
        output_file.close()
