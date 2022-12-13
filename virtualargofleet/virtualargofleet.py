import warnings
from parcels import ParticleSet, FieldSet, AdvectionRK4, ErrorCode
import datetime
from datetime import timedelta
import os
import tempfile
import pandas as pd
import numpy as np
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


log = logging.getLogger("virtualfleet")


class VirtualFleet:
    """Argo Virtual Fleet simulator helper.

    This class should make it easier to process and analyse a simulation.

    """

    def __init__(self, isglobal=False, **kwargs):
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
        # Deployment plan:
        self.lat = kwargs["lat"]
        self.lon = kwargs["lon"]
        if "depth" not in kwargs:
            self.depth = np.full(self.lat.shape, 1.0)
        else:
            self.depth = kwargs["depth"]
        self.time = kwargs["time"]

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

        # Define parcels :class:`parcels.particleset.particlesetsoa.ParticleSetSOA`
        self.pset = ParticleSet(
            fieldset=fieldset,
            pclass=Particle,
            lon=self.lon,
            lat=self.lat,
            depth=self.depth,
            time=self.time,
        )

        if isglobal:
            # combine Argo vertical movement kernel with Advection kernel + boundaries
            self.kernels = (
                FloatKernel
                + self.pset.Kernel(AdvectionRK4)
                + self.pset.Kernel(PeriodicBoundaryConditionKernel)
            )
        else:
            self.kernels = FloatKernel + self.pset.Kernel(AdvectionRK4)

        self.simulated = False  # Will be set to True if self.simulate() is used
        self.simulation_parameters = None

    def __repr__(self):
        summary = ["<VirtualFleet>"]
        summary.append("%i floats in the deployment plan" % self.pset.size)
        if self.simulated:
            summary.append("A simulation of %i days, with data recording every %f hours has been performed"
                           % (self.simulation_parameters["duration"].days,
                              self.simulation_parameters["record"].seconds/3600))
            if self.simulation_parameters['output_path'] is not None:
                summary.append("Simulation trajectories saved in: %s" % self.simulation_parameters['output_path'])
            else:
                summary.append("Simulation trajectories not saved on disk. Last positions available with the `ParticleSet` property of this instance")
        else:
            summary.append("No simulation performed")

        # self.simulation_parameters = {'duration': duration, 'step': step, 'record': record, 'output_path': output_path}


        return "\n".join(summary)

    @property
    def ParticleSet(self):
        """Container class for storing particle and executing kernel over them.

        Returns
        -------
        :class:`parcels.particleset.particlesetsoa.ParticleSetSOA`
        """
        return self.pset

    @property
    def fieldset(self):
        """Container class for storing velocity FieldSet

        Returns
        -------
        :class:`parcels.fieldset.FieldSet`
        """
        return self.pset.fieldset

    def show_deployment(self):
        """Method to show where Argo Floats have been deployed

        Using parcels psel builtin show function for now
        """
        self.pset.show()

    def plotfloat(self):
        warnings.warn(
            "'plotfloat' has been replaced by 'show_deployment'",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.show_deployment()

    def simulate(self, step=timedelta(minutes=5), record=timedelta(hours=1), output=False, verbose_progress=True, **kwargs):
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
            temp_name = next(tempfile._get_candidate_names()) + ".zarr"
            while os.path.exists(os.path.join(output_folder, temp_name)):
                temp_name = next(tempfile._get_candidate_names()) + ".zarr"
            return temp_name

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
        log.debug(output_msg)

        # Now execute kernels
        log.debug(
            "Starting Virtual Fleet simulation of %i days, with data recording every %f hours"
            % (duration.days, record.seconds/3600)
        )
        opts = {'runtime': duration,
                'dt': step,
                'verbose_progress': verbose_progress,
                'recovery': {ErrorCode.ErrorOutOfBounds: DeleteParticleKernel,
                             ErrorCode.ErrorThroughSurface: DeleteParticleKernel}
                }
        if output:
            opts['output_file'] = self.pset.ParticleFile(name=output_path, outputdt=record)

        log.debug("starting pset.execute")
        self.pset.execute(
            self.kernels,
            **opts
        )
        log.debug("ending pset.execute")

        # Internal recording of the simulation:
        self.simulated = True
        self.simulation_parameters = {'duration': duration, 'step': step, 'record': record, 'output_path': output_path}

        # Add more variables to the output file:
        # ncout = self.run_params["output_file"]
        # ds = xr.open_dataset(ncout)
