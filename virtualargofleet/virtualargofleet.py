import warnings
import parcels
from parcels import ParticleSet, FieldSet, AdvectionRK4, ErrorCode
import datetime
from datetime import timedelta
import os
import tempfile
import pandas as pd
import numpy as np
import xarray as xr
import logging
from .app_parcels import (
    ArgoParticle,
    ArgoParticle_exp,
    DeleteParticleKernel,
    ArgoFloatKernel,
    ArgoFloatKernel_exp,
    PeriodicBoundaryConditionKernel,
)
from .velocity_helpers import VelocityFieldProto
from .utilities import simu2csv, simu2index, strfdelta, getSystemInfo
from packaging import version
import time


log = logging.getLogger("virtualfleet.virtualfleet")


class VirtualFleet:
    """Argo Virtual Fleet simulator helper.

    This class should make it easier to process and analyse a simulation.

    """

    def __init__(self, isglobal: bool=False, **kwargs):
        """
        Parameters
        ----------
        lat, lon, depth, time:
            Numpy arrays describing where Argo floats are deployed.
            Depth is optional, if not provided it will be set to 1m.
        fieldset: :class:`parcels.fieldset`
            Velocity field
        mission: dict
            Dictionary with Argo float parameters {'parking_depth': parking_depth, 'profile_depth': profile_depth, 'vertical_speed': vertical_speed, 'cycle_duration': cycle_duration}
        isglobal: False
        """
        self._isglobal = isglobal

        # Deployment plan:
        self._plan = {'lat': kwargs["lat"], 'lon': kwargs["lon"], 'depth': None, 'time': kwargs["time"]}
        if "depth" not in kwargs:
            self._plan['depth'] = np.full(self._plan['lat'].shape, 1.0)
        else:
            self._plan['depth'] = kwargs["depth"]

        if kwargs['mission']['parking_depth'] < 0 or kwargs['mission']['parking_depth'] > 6000:
            raise ValueError('Parking depth must be in [0-6000] db')

        if kwargs['mission']['profile_depth'] < 0 or kwargs['mission']['profile_depth'] > 6000:
            raise ValueError('Profile depth must be in [0-6000] db')

        if kwargs['mission']['cycle_duration'] < 0:
            raise ValueError('Cycle duration must be positive')

        if kwargs['mission']['vertical_speed'] < 0:
            raise ValueError('Vertical speed must be positive')
        if kwargs['mission']['vertical_speed'] > 1:
            warnings.warn("%f m/s is pretty fast for an Argo float ! Typical speed is 0.09 m/s" % kwargs['mission']['vertical_speed'])

        if 'vfield' in kwargs:
            raise ValueError("The 'vfield' option is deprecated. You can use the 'fieldset' "
                             "option to pass on the Ocean Parcels fieldset.")

        # Velocity/Hydrodynamic field:
        fieldset = kwargs["fieldset"]
        if isinstance(fieldset, VelocityFieldProto):
            fieldset = fieldset.fieldset
        if not isinstance(fieldset, FieldSet):
            raise TypeError("The `fieldset` option must be a `FieldSet` Parcels instance")

        # Forward mission parameters to the simulation through fieldset
        mission = kwargs["mission"]
        fieldset.add_constant("parking_depth", mission["parking_depth"])
        fieldset.add_constant("profile_depth", mission["profile_depth"])
        fieldset.add_constant("v_speed", mission["vertical_speed"])
        fieldset.add_constant("cycle_duration", mission["cycle_duration"])
        fieldset.add_constant("life_expectancy", mission["life_expectancy"])

        Particle = ArgoParticle
        FloatKernel = ArgoFloatKernel

        if "area_cycle_duration" in mission:
            fieldset.add_constant("area_cycle_duration", mission["area_cycle_duration"])
            fieldset.add_constant("area_parking_depth", mission["area_parking_depth"])
            fieldset.add_constant("area_xmin", mission["area_xmin"])
            fieldset.add_constant("area_xmax", mission["area_xmax"])
            fieldset.add_constant("area_ymin", mission["area_ymin"])
            fieldset.add_constant("area_ymax", mission["area_ymax"])
            Particle = ArgoParticle_exp
            FloatKernel = ArgoFloatKernel_exp

        # More useful parameters to be sent to floats:
        verbose_events = (
            kwargs["verbose_events"]
            if "verbose_events" in kwargs
            else 1
        )
        fieldset.add_constant("verbose_events", verbose_events)

        # Define Ocean parcels elements
        self._parcels = {'fieldset': fieldset,
                         'Particle': Particle,
                         'FloatKernel': FloatKernel,
                         'ParticleSet': None,
                         'kernels': None}
        self.__init_ParticleSet().__init_kernels()  # Will modify the 'ParticleSet' and 'kernels' of self._parcels

        self.simulated = False  # Will be set to True if self.simulate() is used
        self.simulation_parameters = None

    def __init_ParticleSet(self):
        P = ParticleSet(
            fieldset=self._parcels['fieldset'],
            pclass=self._parcels['Particle'],
            lon=self._plan['lon'],
            lat=self._plan['lat'],
            depth=self._plan['depth'],
            time=self._plan['time'],
            pid_orig=np.arange(self._plan['lon'].size),
        )
        self._parcels['ParticleSet'] = P
        return self

    def __init_kernels(self):
        if self._isglobal:
            # combine Argo vertical movement kernel with Advection kernel + boundaries
            K = (
                    self._parcels['FloatKernel']
                    + self._parcels['ParticleSet'].Kernel(AdvectionRK4)
                    + self._parcels['ParticleSet'].Kernel(PeriodicBoundaryConditionKernel)
            )
        else:
            K = self._parcels['FloatKernel'] + self._parcels['ParticleSet'].Kernel(AdvectionRK4)
        self._parcels['kernels'] = K
        return self

    def __repr__(self):
        summary = ["<VirtualFleet>"]
        summary.append("- %i floats in the deployment plan" % self._parcels['ParticleSet'].size)
        if self.simulated:
            summary.append("- A simulation of %s with data recording every %s has been performed"
                           % (strfdelta(self.simulation_parameters["duration"].total_seconds(),
                                        inputtype='s'),
                              strfdelta(self.simulation_parameters["record"].total_seconds(),
                                        fmt='{H:02}h {M:02}m', inputtype='s')))
            if self.simulation_parameters['output_path'] is not None:
                summary.append("- Simulation trajectories saved in: %s" % self.simulation_parameters['output_path'])
            else:
                summary.append("- Simulation trajectories not saved on disk. Last positions available with the `ParticleSet` property of this instance")
            summary.append("- Simulation executed in %s on %s" % (strfdelta(self.simulation_parameters['execution_wall_time']),
                                                   self.simulation_parameters['execution_system']['hostname']))
        else:
            summary.append("- No simulation performed")

        # self.simulation_parameters = {'duration': duration, 'step': step, 'record': record, 'output_path': output_path}


        return "\n".join(summary)

    @property
    def ParticleSet(self):
        """Container class for storing particle and executing kernel over them.

        Returns
        -------
        :class:`parcels.particleset.particlesetsoa.ParticleSetSOA`
        """
        return self._parcels['ParticleSet']

    @property
    def fieldset(self):
        """Container class for storing velocity FieldSet

        Returns
        -------
        :class:`parcels.fieldset.FieldSet`
        """
        return self._parcels['ParticleSet'].fieldset
        # return self._parcels['fieldset']

    def plot_positions(self):
        """Method to show where are Argo Floats

        Using parcels psel builtin show function for now
        """
        self._parcels['ParticleSet'].show()

    def simulate(self,
                 step=timedelta(minutes=5),
                 record=timedelta(hours=1),
                 output=False,
                 verbose_progress=True,
                 restart=False,
                 **kwargs):
        """Execute a Virtual Fleet simulation

        Inputs
        ------
        duration: timedelta,
            Length of the simulation
            Eg: timedelta(days=365)

        step: timedelta, default timedelta(minutes=5)
            Time step for the computation

        record: timedelta, default timedelta(hours=1)
            Time step for writing the output

        output: bool, default=False
            Should the simulation trajectories be saved on file or not

        output_file: str
            Name of the netcdf file where to store simulation results

        output_folder: str
            Name of folder where to store 'output_file'
        """
        def get_an_output_filename(output_folder):
            # This older version support should be removed
            if version.parse(parcels.__version__) >= version.parse("2.4.0"):
                ext = ".zarr"
            else:
                ext = ".nc"
            temp_name = next(tempfile._get_candidate_names()) + ext
            while os.path.exists(os.path.join(output_folder, temp_name)):
                temp_name = next(tempfile._get_candidate_names()) + ext
            return temp_name

        if self.simulated:
            log.warning("A simulation has already been performed with this VirtualFleet")

        if not restart:
            # Start a new simulation, from scratch
            # We need to reinitialize the 'ParticleSet' of self._parcels
            log.debug('start simulation from scratch')
            self.__init_ParticleSet()#.__init_kernels()
        else:
            log.debug('restart simulation where it was')
        # print("self._parcels['fieldset']", hex(id(self._parcels['fieldset'])))
        # print("self._parcels['ParticleSet'].fieldset", hex(id(self._parcels['ParticleSet'].fieldset)))
        # print("self._parcels['kernels']", hex(id(self._parcels['kernels'])))
        # print("self._parcels['ParticleSet']", hex(id(self._parcels['ParticleSet'])))
        # print("self._parcels['ParticleSet'].collection", hex(id(self._parcels['ParticleSet'].collection)))

        duration = (
            kwargs["duration"]
            if isinstance(kwargs["duration"], datetime.timedelta)
            else timedelta(hours=kwargs["duration"])
        )
        step = (
            step
            if isinstance(step, datetime.timedelta)
            else timedelta(hours=step)
        )
        record = (
            record
            if isinstance(record, datetime.timedelta)
            else timedelta(hours=record)
        )
        if step > record:
            raise ValueError('The computation time step cannot be larger than the recording period')
        if np.remainder(record, step) > timedelta(0):
            raise ValueError('The recording period must be a multiple of the computation time step')

        # Handle output
        if not output:
            output_path = None
            output_msg = "Simulation will NOT be saved on file !"
        else:
            output_file = kwargs["output_file"] if "output_file" in kwargs else None
            output_folder = kwargs["output_folder"] if "output_folder" in kwargs else "."
            if output_folder is None:
                output_folder = "."
            if output_file is None:
                output_file = get_an_output_filename(output_folder)
            output_path = os.path.join(output_folder, output_file)
            output_msg = "Simulation will be saved in : " + output_path

        warnings.warn(output_msg)
        log.info(output_msg)

        # Now execute kernels
        log.info(
            "Starting Virtual Fleet simulation of %i days, with data recording every %f hours"
            % (duration.days, record.seconds/3600)
        )
        opts = {'runtime': duration,
                'dt': step,
                'verbose_progress': verbose_progress,
                'recovery': {ErrorCode.ErrorOutOfBounds: DeleteParticleKernel,
                             ErrorCode.ErrorThroughSurface: DeleteParticleKernel},
                'output_file': None,
                }
        if output:
            # log.info("Creating ParticleFile")e
            opts['output_file'] = self._parcels['ParticleSet'].ParticleFile(name=output_path, outputdt=record)
            # log.info("Parcels temporary files will be saved in: %s" % opts['output_file'].tempwritedir_base)
        log.debug(opts)

        log.info("starting ParticleSet execution")
        execution_start, process_start = time.time(), time.process_time()
        P = self._parcels['ParticleSet']
        P.execute(self._parcels['kernels'], **opts)
        log.info("ending ParticleSet execution")

        if output:
            # Close the ParticleFile object (used to exporting and then deleting the temporary npy files in older versions)
            log.info("starting ParticleFile export/close/clean from %s" % opts['output_file'].fname)
            opts['output_file'].close(delete_tempfiles=True)
            log.info("ending ParticleFile export/close/clean to %s" % opts['output_file'].fname)

        # Internal recording of the simulation:
        execution_end, process_end = time.time(), time.process_time()
        self.simulated = True
        self.simulation_parameters = {'duration': duration,
                                      'step': step,
                                      'record': record,
                                      'output_path': output_path,
                                      'opts': opts,
                                      'execution_wall_time': pd.Timedelta(execution_end - execution_start, 's'),
                                      'execution_cpu_time': pd.Timedelta(process_end - process_start, 's'),
                                      'execution_date': pd.to_datetime("now", utc=True).strftime("%Y%m%d-%H%M%S"),
                                      'execution_system': getSystemInfo()}


    def to_index(self, file_name=None):
        """Return simulated profile index dataframe

        Return a pandas.Dataframe index of profiles.
        If the ``file_name`` option is provided, an Argo profile index csv file is writen.

        Parameters
        ----------
        file_name: str, default: None
            Name of the index file to write
        """
        if not self.simulated or self.simulation_parameters['output_path'] is None:
            raise ValueError("You must execute a simulation with trajectory recording to get a virtual profile index")
        else:
            simu_path = self.simulation_parameters['output_path']
        engine = 'zarr' if '.zarr' in simu_path else 'netcdf4'

        if file_name:
            return simu2csv(simu_path, index_file=file_name, df=None, engine=engine)
        else:
            # engine = 'netcdf4' if "zarr" not in simu_path else 'zarr'
            # ds = xr.open_dataset(simu_path, engine=engine)
            ds = xr.open_dataset(simu_path, engine=engine)  # Let xarray guess how to open this simulation (nc or zarr)
            return simu2index(ds)

