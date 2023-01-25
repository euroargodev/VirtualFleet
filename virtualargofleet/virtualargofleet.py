import numbers
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
from .velocity_helpers import VelocityField
from .utilities import SimulationSet, FloatConfiguration
from .utilities import simu2csv, simu2index, strfdelta, getSystemInfo
from packaging import version
import time
from typing import Union


log = logging.getLogger("virtualfleet.virtualfleet")


class VirtualFleet:
    """Argo Virtual Fleet simulator.

    This class makes it easy to process and analyse a simulation.

    """
    def __init__(self,
                 plan: dict,
                 fieldset: Union[FieldSet, VelocityField],
                 mission: Union[dict, FloatConfiguration],
                 isglobal: bool=False,
                 **kwargs):
        """Create an Argo Virtual Fleet simulator

        Parameters
        ----------
        plan: dict
            A dictionary with the deployment plan coordinates as keys: ``lat``, ``lon``, ``time``, [``depth``]
            Each value are Numpy arrays describing where Argo floats are deployed.
            Depth is optional, if not provided it will be set to 1m.
        fieldset: :class:`parcels.fieldset.FieldSet` or :class:`VelocityField`
            A velocity field
        mission: dict or :class:`FloatConfiguration`
            A dictionary with at least the following Argo float mission parameters: ``parking_depth``, ``profile_depth``, ``vertical_speed`` and ``cycle_duration``
        isglobal: bool, optional, default=False
            A boolean indicating weather the velocity field is global or not

        """
        self._isglobal = bool(isglobal)

        # Deployment plan:
        for key in ['lat', 'lon', 'time']:
            if key not in plan:
                raise ValueError("The 'plan' argument must have a '%s' key" % key)
        default_plan = {'lat': None, 'lon': None, 'depth': None, 'time': None}
        self.deployment_plan = {**default_plan, **plan}
        if self.deployment_plan['depth'] is None:
            self.deployment_plan['depth'] = np.full(self.deployment_plan['lat'].shape, 1.0)

        # Mission parameters:
        if isinstance(mission, FloatConfiguration):  # be nice when we forget to set the correct input
            mission = mission.mission
        if not isinstance(mission, dict):
            raise TypeError("The `mission` argument must be a dictionary or a `FloatConfiguration` instance")

        for key in ['parking_depth', 'profile_depth', 'cycle_duration', 'vertical_speed']:
            if key not in mission:
                raise ValueError("The 'mission' argument must have a '%s' key" % key)

        if mission['parking_depth'] < 0 or mission['parking_depth'] > 6000:
            raise ValueError('Parking depth must be in [0-6000] db')

        if mission['profile_depth'] < 0 or mission['profile_depth'] > 6000:
            raise ValueError('Profile depth must be in [0-6000] db')

        if mission['cycle_duration'] < 0:
            raise ValueError('Cycle duration must be positive')

        if mission['vertical_speed'] < 0:
            raise ValueError('Vertical speed must be positive')
        if mission['vertical_speed'] > 1:
            warnings.warn("%f m/s is pretty fast for an Argo float ! Typical speed is 0.09 m/s" % mission['vertical_speed'])

        if 'vfield' in kwargs:
            raise ValueError("The 'vfield' option is deprecated. You can use the 'fieldset' "
                             "option to pass on the Ocean Parcels fieldset.")

        # Velocity/Hydrodynamic field:
        if isinstance(fieldset, VelocityField):  # be nice when we forget to set the correct input
            fieldset = fieldset.fieldset
        if not isinstance(fieldset, FieldSet):
            raise TypeError("The `fieldset` argument must be a `FieldSet` Parcels or `VelocityField` instance")

        # Forward mission parameters to the simulation through fieldset
        fieldset.add_constant("parking_depth", mission["parking_depth"])
        fieldset.add_constant("profile_depth", mission["profile_depth"])
        fieldset.add_constant("vertical_speed", mission["vertical_speed"])
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

        # Init the internal class to hold all simulation metadata:
        self.simulations_set = SimulationSet()

    def __init_ParticleSet(self):
        pid_orig = np.arange(self.deployment_plan['lon'].size)
        # print(pid_orig)
        P = ParticleSet(
            fieldset=self._parcels['fieldset'],
            pclass=self._parcels['Particle'],
            lon=self.deployment_plan['lon'],
            lat=self.deployment_plan['lat'],
            depth=self.deployment_plan['depth'],
            time=self.deployment_plan['time'],
            pid_orig=pid_orig,
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
        if self.simulations_set.simulated:
            # summary.append("A simulation has been performed:")
            summary.append("- Number of simulation(s): %i" % self.simulations_set.N)
            last_sim = self.simulations_set.last
            summary.append("- Last simulation meta-data:")
            summary.append("\t- Duration: %s" % strfdelta(last_sim["duration"].total_seconds(), inputtype='s'))
            summary.append("\t- Data recording every: %s"
                           % strfdelta(last_sim["record"].total_seconds(), fmt='{H:02}h {M:02}m', inputtype='s')
                           )
            if last_sim['output_path'] is not None:
                summary.append("\t- Trajectory file: %s" % last_sim['output_path'])
            else:
                summary.append("\t- Simulation trajectories were not saved on file")
            summary.append("\t- Execution time: %s" % strfdelta(last_sim['execution_wall_time']))
            summary.append("\t- Executed on: %s" % last_sim['execution_system']['hostname'])
            # summary.append(self.simulations_set.__repr__())
        else:
            summary.append("- No simulation performed")
        return "\n".join(summary)

    @property
    def ParticleSet(self):
        """Return ParticleSet

        Returns
        -------
        :class:`parcels.particleset.particlesetsoa.ParticleSetSOA`
        """
        return self._parcels['ParticleSet']

    @property
    def fieldset(self):
        """Return FieldSet

        Returns
        -------
        :class:`parcels.fieldset.FieldSet`
        """
        return self._parcels['ParticleSet'].fieldset
        # return self._parcels['fieldset']

    def plot_positions(self):
        """Plot the last position of virtual Argo Floats

        Use :meth:`parcels.particleset.baseparticleset.BaseParticleSet.show`
        """
        self._parcels['ParticleSet'].show()

    def simulate(self,
                 duration,
                 step=timedelta(minutes=5),
                 record=timedelta(hours=1),
                 output=True,
                 verbose_progress=True,
                 restart=False,
                 **kwargs):
        """Execute a Virtual Fleet simulation

        Parameters
        ----------
        duration: :class:`datetime.timedelta`,
            Length of the simulation

        step: :class:`datetime.timedelta`, default=5 minutes
            Time step for the computation

        record: :class:`datetime.timedelta`, default=1 hours
            Time step for writing the output

        output: bool, default=False
            Should the simulation trajectories be saved on file or not

        output_file: str
            Name of the zarr file where to store simulation results

        output_folder: str
            Name of folder where to store the 'output_file' zarr archive

        Returns
        -------
        self
        """
        def _validate(td, name='?', fallback='hours'):
            if not isinstance(td, datetime.timedelta):
                if isinstance(td, numbers.Number):
                    if fallback == 'hours':
                        td = timedelta(hours=float(td))
                    elif fallback == 'days':
                        td = timedelta(days=float(td))
                    elif fallback == 'minutes':
                        td = timedelta(minutes=float(td))
                else:
                    raise ValueError("'%s' must be a datetime.timedelta or a numeric value for %s" % (name, fallback))
            return td

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

        if self.simulations_set.simulated:
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

        duration = _validate(duration, name='duration', fallback='days')
        step = _validate(step, name='duration', fallback='minutes')
        record = _validate(record, name='duration', fallback='hours')

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
        this_run_params = {'duration': duration,
                                      'step': step,
                                      'record': record,
                                      'output_path': output_path,
                                      'opts': opts,
                                      'execution_wall_time': pd.Timedelta(execution_end - execution_start, 's'),
                                      'execution_cpu_time': pd.Timedelta(process_end - process_start, 's'),
                                      'execution_date': pd.to_datetime("now", utc=True).strftime("%Y%m%d-%H%M%S"),
                                      'execution_system': getSystemInfo()
                           }
        self.simulations_set.add(this_run_params)
        return self

    @property
    def output(self):
        """Return absolute path to the last simulation trajectory output file"""
        if self.simulations_set.N > 0:
            output_path = self.simulations_set.last['output_path']
        else:
            output_path = None
        return os.path.abspath(output_path)

    def to_index(self, file_name=None):
        """Return last simulated profile index dataframe

        Return a pandas.Dataframe index of profiles.
        If the ``file_name`` option is provided, an Argo profile index csv file is writen.

        Parameters
        ----------
        file_name: str, default: None
            Name of the index file to write
        """
        if self.simulations_set.N > 0:
            output_path = self.simulations_set.last['output_path']
        else:
            output_path = None
        if not self.simulations_set.simulated or output_path is None:
            raise ValueError("You must execute a simulation with trajectory recording to get a virtual profile index")

        # How to open the trajectory file:
        engine = 'zarr' if '.zarr' in output_path else 'netcdf4'

        if file_name:
            return simu2csv(output_path, index_file=file_name, df=None, engine=engine)
        else:
            ds = xr.open_dataset(output_path, engine=engine)
            return simu2index(ds)

