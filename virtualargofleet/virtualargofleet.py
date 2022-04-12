#!/bin/env python
# -*coding: UTF-8 -*-
"""

Created by K. Balem on 02/28/2020
"""
__author__ = 'kbalem@ifremer.fr'

import warnings

from parcels import FieldSet, ParticleSet, JITParticle, AdvectionRK4, ErrorCode, Variable, plotTrajectoriesFile, Field
from datetime import timedelta
import numpy as np
import xarray as xr
import os
import glob
import tempfile


class ArgoParticle(JITParticle):
    """ Internal class used by parcels to add variables to particle kernel

    Inherit from :class:`parcels.JITParticle`

    Returns
    -------
    :class:`parcels.particle.JITParticle``
    """
    # Phase of cycle: init_descend = 0, drift = 1, profile_descend = 2, profile_ascend = 3, transmit = 4
    cycle_phase = Variable('cycle_phase', dtype=np.int32, initial=0.)
    cycle_age = Variable('cycle_age', dtype=np.float32, initial=0.)
    drift_age = Variable('drift_age', dtype=np.float32, initial=0.)
    in_water = Variable('in_water', dtype=np.float32, initial=1.)


def ArgoVerticalMovement(particle, fieldset, time):
    """This is the kernel definition that mimics an Argo float.

    It can only have (particle, fieldset, time) as arguments. So missions parameters are passed as constants through the fieldset.

    Parameters
    ----------
    particle:
    fieldset: :class:`parcels.fieldset.FieldSet`
        FieldSet class instance that holds hydrodynamic data needed to execute particles

    time

    Returns
    -------
    :class:`parcels.kernels`
    """
    driftdepth = fieldset.parking_depth
    maxdepth = fieldset.profile_depth
    mindepth = 1  # not too close to the surface so that particle doesn't go above it
    vertical_speed = fieldset.v_speed  # in m/s
    cycletime = fieldset.cycle_duration * 86400  # in s
    particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]

    # Compute drifting time so that the cycletime is respected:
    # Time to descent to parking (mindepth to driftdepth at vertical_speed)
    transit = (driftdepth - mindepth) / vertical_speed
    # Time to descent to profile depth (driftdepth to maxdepth at vertical_speed)
    transit += (maxdepth - driftdepth) / vertical_speed
    # Time to ascent (maxdepth to mindepth at vertical_speed)
    transit += (maxdepth - mindepth) / vertical_speed
    drifttime = cycletime - transit

    # Grounding management : Since parcels turns NaN to Zero within our domain, we have to manage
    # groundings in another way that the recovery of deleted particles (below)
    if not particle.in_water:
        # if we're in phase 0 or 1 :
        # -> rising 50 db and start drifting (phase 1)
        if particle.cycle_phase <= 1:
            print(
                "Grouding during descent to parking or during parking, rising up 50m and try drifting here.")
            particle.depth = particle.depth - 50
            particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
            particle.cycle_phase = 1
        # if we're in phase 2:
        # -> start profiling (phase 3)
        elif particle.cycle_phase == 2:
            print("Grounding during descent to profile, starting profile here")
            particle.cycle_phase = 3
        else:
            pass    

    # CYCLE MANAGEMENT
    if particle.cycle_phase == 0:
        # Phase 0: Sinking with vertical_speed until depth is driftdepth
        particle.depth += vertical_speed * particle.dt
        particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
        if particle.depth >= driftdepth:
            particle.cycle_phase = 1

    elif particle.cycle_phase == 1:
        # Phase 1: Drifting at depth for drifttime seconds
        particle.drift_age += particle.dt
        if particle.drift_age >= drifttime:
            particle.drift_age = 0  # reset drift_age for next cycle
            particle.cycle_phase = 2

    elif particle.cycle_phase == 2:
        # Phase 2: Sinking further to maxdepth
        particle.depth += vertical_speed * particle.dt
        particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
        if particle.depth >= maxdepth:
            particle.cycle_phase = 3

    elif particle.cycle_phase == 3:
        # Phase 3: Rising with vertical_speed until at surface
        particle.depth -= vertical_speed * particle.dt
        particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
        if particle.depth <= mindepth:
            particle.depth = mindepth
            particle.cycle_phase = 4

    elif particle.cycle_phase == 4:
        # Phase 4: Transmitting at surface until cycletime is reached
        if particle.cycle_age >= cycletime:
            particle.cycle_phase = 0
            particle.cycle_age = 0

    particle.cycle_age += particle.dt  # update cycle_age

# define recovery for OutOfBounds Error


def DeleteParticle(particle, fieldset, time):

    # Get velocity field bounds
    lat_min, lat_max = fieldset.gridset.dimrange(dim='lat')
    lon_min, lon_max = fieldset.gridset.dimrange(dim='lon')
    # Get the center of the cellgrid for depth
    dgrid = fieldset.gridset.grids[0].depth
    depth_min = dgrid[0] + (dgrid[1]-dgrid[0])/2
    depth_max = dgrid[-2]+(dgrid[-1]-dgrid[-2])/2

    # out of geographical area : here we can delete the particle
    if ((particle.lat < lat_min) | (particle.lat > lat_max) | (particle.lon < lon_min) | (particle.lon > lon_max)):
        print("Field warning : Particle out of the geographical domain --> deleted")
        particle.delete()
    # in the air, calm down float !
    elif (particle.depth < depth_min):
        print("Field Warning : Particle above surface, depth set to product min_depth.")
        particle.depth = depth_min
        particle.cycle_phase = 4
    # below fieldset
    elif (particle.depth > depth_max):
        # if we're in phase 0 or 1 :
        # -> set particle depth to max non null depth, ascent 50 db and start drifting (phase 1)
        if particle.cycle_phase <= 1:
            print("Field warning : Particle below the fieldset, your dataset is probably not deep enough for what you're trying to do. It will drift here")
            particle.depth = depth_max - 50
            particle.cycle_phase = 1
        # if we're in phase 2 :
        # -> set particle depth to max non null depth, and start profiling (phase 3)
        elif particle.cycle_phase == 2:
            print("Field warning : Particle below the fieldset, your dataset is not deep enough for what you're trying to do. It will start profiling here")
            particle.depth = depth_max
            particle.cycle_phase = 3
    else:
        # I don't know why yet but in some cases, during ascent,  I get an outOfBounds error, even with a depth > depth_min...
        if particle.cycle_phase == 3:
            particle.depth = depth_min
            particle.cycle_phase = 4
        else :
            print(particle.cycle_phase, particle.depth)
            print("Field Warning : Unknown OutOfBounds --> deleted")
            particle.delete()


def periodicBC(particle, fieldset, time):
    if particle.lon < fieldset.halo_west:
        particle.lon += fieldset.halo_east - fieldset.halo_west
    elif particle.lon > fieldset.halo_east:
        particle.lon -= fieldset.halo_east - fieldset.halo_west

    if particle.lat < fieldset.halo_south:
        particle.lat += fieldset.halo_north - fieldset.halo_south
    elif particle.lat > fieldset.halo_north:
        particle.lat -= fieldset.halo_north - fieldset.halo_south


class velocityfield:
    """Velocity Field Helper"""

    def __init__(self, **kwargs):
        """
        Parameters
        ----------
        ds : filenames for U & V
        var : dictionnary for variables
        dim : dictionnary for dimensions lat,lon,depth,time
        isglobal : 1 if field is global, 0 otherwise
        """
        # props
        self.field = kwargs['ds']
        self.var = kwargs['var']
        self.dim = kwargs['dim']
        self.isglobal = kwargs['isglobal']
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


class virtualfleet:
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
