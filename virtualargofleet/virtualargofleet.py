import numbers
import warnings
from packaging import version

import parcels
from parcels import ParticleSet, FieldSet, AdvectionRK4, StatusCode

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
    ArgoFloatKernel,
    ArgoFloatKernel_exp,
    PeriodicBoundaryConditionKernel,
    KeepInDomain, KeepInWater, KeepInColumn,
)
from .velocity_helpers import VelocityField
from .utilities import SimulationSet, FloatConfiguration
from .utilities import simu2csv, simu2index, strfdelta, getSystemInfo
import time
from typing import Union, Iterable


log = logging.getLogger("virtualfleet.virtualfleet")


DEFAULT_DEPLOYMENT_DEPTH = 1.0
"""Default deployment depth when not set in the plan"""


class VirtualFleet:
    """Argo Virtual Fleet simulator.

    This class makes it easy to process and analyse a simulation.

    """
    def __init__(self,
                 plan: dict,
                 fieldset: Union[FieldSet, VelocityField],
                 mission: Union[dict, FloatConfiguration, Iterable[dict], Iterable[FloatConfiguration]],
                 isglobal: bool = False,
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
        mission: dict or :class:`FloatConfiguration` or an iterable of those
            A dictionary with the following Argo float mission parameters: ``parking_depth``, ``profile_depth``,
            ``vertical_speed`` and ``cycle_duration``. A :class:`FloatConfiguration` instance can also be passed.

            An iterable of dictionaries or :class:`FloatConfiguration` can be passed to specified mission parameters for each
            virtual floats. In this case, the length of the iterable must match the length of the deployment plan.
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
            self.deployment_plan['depth'] = np.full(self.deployment_plan['lat'].shape, DEFAULT_DEPLOYMENT_DEPTH)

        # Mission parameters:
        if not isinstance(mission,(list,tuple,np.ndarray)):
            mission = list([mission])
            
        if len(mission)!=len(self.deployment_plan['lat']):
            if(len(mission)==1): #if mission's len is 1, apply to all floats
                mission = np.repeat(mission,len(self.deployment_plan['lat']))
            else:
                raise TypeError("When providing a `mission` array, it should be the same lenght as your `plan`")
        
        #
        for i in range(len(mission)):
            if isinstance(mission[i], FloatConfiguration):  # be nice when we forget to set the correct input
                mission[i] = mission[i].mission
                
            if not isinstance(mission[i], dict):
                raise TypeError("The `mission` argument must be a dictionary or a `FloatConfiguration` instance")
            
            # standard parameters
            for key in ['parking_depth', 'profile_depth', 'cycle_duration', 'vertical_speed', 'life_expectancy']:
                if key not in mission[i]:
                    raise ValueError("The 'mission' argument must have a '%s' key" % key)
                
            # Depending on the specific kernel used, we should check keys here

            if mission[i]['parking_depth'] < 0 or mission[i]['parking_depth'] > 6000:
                raise ValueError('Parking depth must be in [0-6000] db')

            if mission[i]['profile_depth'] < 0 or mission[i]['profile_depth'] > 6000:
                raise ValueError('Profile depth must be in [0-6000] db')

            if mission[i]['cycle_duration'] < 0:
                raise ValueError('Cycle duration must be positive')

            if mission[i]['vertical_speed'] < 0:
                raise ValueError('Vertical speed must be positive')
            if mission[i]['vertical_speed'] > 1:
                warnings.warn("%f m/s is pretty fast for an Argo float ! Typical speed is 0.09 m/s" % mission[i]['vertical_speed'])
        
        self.mission = mission        

        if 'vfield' in kwargs:
            raise ValueError("The 'vfield' option is deprecated. You can use the 'fieldset' "
                             "option to pass on the Ocean Parcels fieldset.")

        # Velocity/Hydrodynamic field:
        if isinstance(fieldset, VelocityField):  # be nice when we forget to set the correct input
            fieldset = fieldset.fieldset
        if not isinstance(fieldset, FieldSet):
            raise TypeError("The `fieldset` argument must be a `FieldSet` Parcels or `VelocityField` instance")
       
        Particle = ArgoParticle
        FloatKernel = ArgoFloatKernel

        # kernels should not be managed by key present in the mission configuration
        #todo Update behavior to work with ArgoParticle_exp kernel

        #if "area_cycle_duration" in mission:
        #    fieldset.add_constant("area_cycle_duration", mission["area_cycle_duration"])
        #    fieldset.add_constant("area_parking_depth", mission["area_parking_depth"])
        #    fieldset.add_constant("area_xmin", mission["area_xmin"])
        #    fieldset.add_constant("area_xmax", mission["area_xmax"])
        #    fieldset.add_constant("area_ymin", mission["area_ymin"])
        #    fieldset.add_constant("area_ymax", mission["area_ymax"])
        #    Particle = ArgoParticle_exp
        #    FloatKernel = ArgoFloatKernel_exp

        # More useful parameters to be sent to floats:
        verbose_events = (
            kwargs["verbose_events"]
            if "verbose_events" in kwargs
            else 1
        )
        fieldset.add_constant("verbose_events", verbose_events)

        # Maximum depth of the velocity field (used by the KeepInColumn kernel)
        # fieldset.add_constant("max_fieldset_depth", np.max(fieldset.gridset.grids[0].depth))
        # Get the center depth of the first cell:
        dgrid = fieldset.gridset.grids[0].depth
        # depth_min = dgrid[0] + (dgrid[1]-dgrid[0])/2
        # depth_max = dgrid[-2]+(dgrid[-1]-dgrid[-2])/2
        depth_min = dgrid[0] + (dgrid[1]-dgrid[0])/2
        depth_max = dgrid[-1]
        fieldset.add_constant("vf_surface", depth_min)
        fieldset.add_constant("vf_bottom", depth_max)

        # fieldset.add_constant("vf_west", -180)

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
        # set mission per particles
        for i in range(len(P)):
            P[i].parking_depth = self.mission[i]['parking_depth']
            P[i].profile_depth = self.mission[i]['profile_depth']
            P[i].vertical_speed = self.mission[i]['vertical_speed']
            P[i].cycle_duration = self.mission[i]['cycle_duration']
            P[i].life_expectancy = self.mission[i]['life_expectancy']           

        self._parcels['ParticleSet'] = P
        return self

    def __init_kernels(self):
        """Add kernels, attention: Order matters !"""
        K = self._parcels['FloatKernel']
        # K += self._parcels['ParticleSet'].Kernel(KeepInWater)
        # K += self._parcels['ParticleSet'].Kernel(KeepInColumn)
        K += self._parcels['ParticleSet'].Kernel(AdvectionRK4)
        if self._isglobal:
            K += self._parcels['ParticleSet'].Kernel(PeriodicBoundaryConditionKernel)
        K += self._parcels['ParticleSet'].Kernel(KeepInWater)
        K += self._parcels['ParticleSet'].Kernel(KeepInColumn)
        K += self._parcels['ParticleSet'].Kernel(KeepInDomain)

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
            self.__init_ParticleSet()
        else:
            log.debug('restart simulation where it was')

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
                'output_file': None,
                }

        if output:
            # log.info("Creating ParticleFile")
            opts['output_file'] = self._parcels['ParticleSet'].ParticleFile(name=output_path, outputdt=record)
            # log.info("Parcels temporary files will be saved in: %s" % opts['output_file'].tempwritedir_base)
        log.debug(opts)

        log.info("starting ParticleSet execution")
        execution_start, process_start = time.time(), time.process_time()
        P = self._parcels['ParticleSet']
        P.execute(self._parcels['kernels'], **opts)
        log.info("ending ParticleSet execution")

        if output and version.parse(parcels.__version__) < version.parse("3.0.0"):
            # Close the ParticleFile object (used to export and then delete the temporary npy files in older versions)
            # fname not available in older versions of parcels
            log.info("starting ParticleFile export/close/clean")
            opts['output_file'].close(delete_tempfiles=True)
            log.info("ending ParticleFile export/close/clean")

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

        if file_name:
            return simu2csv(output_path, index_file=file_name, df=None)
        else:
            engine = 'zarr' if '.zarr' in output_path else 'netcdf4'
            ds = xr.open_dataset(output_path, engine=engine)
            return simu2index(ds)

