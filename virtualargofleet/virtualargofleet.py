import warnings
from parcels import ParticleSet, AdvectionRK4, ErrorCode
import datetime
from datetime import timedelta
import os
import tempfile
import pandas as pd
import numpy as np
from .app_parcels import (
    ArgoParticle,
    ArgoParticle_exp,
    DeleteParticleKernel,
    ArgoFloatKernel,
    ArgoFloatKernel_exp,
    PeriodicBoundaryConditionKernel,
)
import logging

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
            Numpy arrays describing where Argo floats are deployed. Depth is optional, if not provided it will be set to 1m.
        fieldset: :class:`parcels.fieldset`
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
        # if isinstance(self.time, pd.core.series.Series):
        #     self.time = self.time.array
            # self.time = np.array([np.datetime64(t) for t in self.time.dt.strftime('%Y-%m-%d').array])
        # print(self.time[0], type(self.time[0]))

        if 'vfield' in kwargs:
            raise ValueError("The 'vfield' option is deprecated. You can use the 'fieldset' option to pass on the Ocean Parcels fieldset.")

        # Velocity/Hydrodynamic field:
        fieldset = kwargs["fieldset"]

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

        self.run_params = None  # Will be set by .simulate() method

    def __repr__(self):
        summary = ["<VirtualFleet>"]
        summary.append("%i floats in the deployment plan" % self.pset.size)
        if self.run_params:
            summary.append("A simulation of %i days, with data recording every %f hours has been performed"
                           % (self.run_params["duration"].days, self.run_params["record"].seconds/3600))
            summary.append("Simluation results in: %s" % self.run_params['output_file'])
        else:
            summary.append("No simulation performed")
        return "\n".join(summary)

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
        warnings.warn(
            "'plotfloat' has been replaced by 'show_deployment'",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.show_deployment()

    def simulate(self, **kwargs):
        """Execute a Virtual Fleet simulation

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
        duration = (
            kwargs["duration"]
            if isinstance(kwargs["duration"], datetime.timedelta)
            else timedelta(hours=kwargs["duration"])
        )
        dt_run = (
            kwargs["step"]
            if isinstance(kwargs["step"], datetime.timedelta)
            else timedelta(hours=kwargs["step"])
        )
        # dt_out = (
        #     kwargs["record"]
        #     if isinstance(kwargs["record"], datetime.timedelta)
        #     else timedelta(hours=kwargs["record"])
        # )
        dt_out = kwargs["record"]

        verbose_progress = (
            kwargs["verbose_progress"]
            if "verbose_progress" in kwargs
            else True
        )

        output_file = kwargs["output_file"] if "output_file" in kwargs else ""
        output_folder = kwargs["output_folder"] if "output_folder" in kwargs else "."
        if output_folder is not None:
            output_path = os.path.join(output_folder, output_file)

            if os.path.exists(output_path) or output_path[0] == ".":
                temp_name = next(tempfile._get_candidate_names()) + ".nc"
                while os.path.exists(temp_name):
                    temp_name = next(tempfile._get_candidate_names()) + ".nc"
                output_path = os.path.join(output_folder, temp_name)
                log.debug(
                    "Empty 'output_file' or file already exists, simulation will be saved in : "
                    + output_path
                )
            else:
                log.debug("Simulation will be saved in : " + output_path)
        else:
            log.debug("Simulation will NOT be saved on file !")
            output_path = None

        self.run_params = {
            "duration": duration,
            "step": dt_run,
            "record": dt_out,
            "output_file": output_path,
        }

        # Now execute the kernels for X days, saving data every Y minutes
        log.debug(
            "Starting Virtual Fleet simulation of %i days, with data recording every %f hours"
            % (self.run_params["duration"].days, self.run_params["record"].seconds/3600)
        )
        output_file = self.pset.ParticleFile(
            name=self.run_params["output_file"], outputdt=self.run_params["record"]
        )

        log.debug("starting pset.execute")
        self.pset.execute(
            self.kernels,
            runtime=self.run_params["duration"],
            dt=self.run_params["step"],
            output_file=output_file,
            verbose_progress=verbose_progress,
            recovery={ErrorCode.ErrorOutOfBounds: DeleteParticleKernel,
                      ErrorCode.ErrorThroughSurface: DeleteParticleKernel},
        )
        log.debug("ending pset.execute")

        # if output_folder is not None:
        #     log.debug("starting export")
        #     output_file.export()
        #     log.debug("ending export")
        #     output_file.close()

        # Add more variables to the output file:
        # ncout = self.run_params["output_file"]
        # ds = xr.open_dataset(ncout)

