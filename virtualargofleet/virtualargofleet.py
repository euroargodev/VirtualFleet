#!/bin/env python
# -*coding: UTF-8 -*-
"""

Created by K. Balem on 02/28/2020
"""
__author__ = 'kbalem@ifremer.fr'


from parcels import FieldSet, ParticleSet, JITParticle, AdvectionRK4, ErrorCode, Variable, plotTrajectoriesFile
from datetime import timedelta
import numpy as np
import xarray as xr
import os, tempfile

class ArgoParticle(JITParticle):
    """ Internal class used by parcels to add variables to particle kernel    
    """
    # Phase of cycle: init_descend = 0, drift = 1, profile_descend = 2, profile_ascend = 3, transmit = 4
    cycle_phase = Variable('cycle_phase', dtype=np.int32, initial=0.)
    cycle_age = Variable('cycle_age', dtype=np.float32, initial=0.)
    drift_age = Variable('drift_age', dtype=np.float32, initial=0.)

def ArgoVerticalMovement(particle, fieldset, time):
    """ This is the kernel definition that mimics the argo float behaviour.
        It can only have (particle, fieldset, time) as arguments. So missions parameters are passed as constants through the fieldset.         
    """
    driftdepth = fieldset.parking_depth
    maxdepth = fieldset.profile_depth
    mindepth = 20 #not too close to the surface so that particle doesn't go above it
    vertical_speed = fieldset.v_speed  # in m/s
    cycletime = fieldset.cycle_duration * 86400  # in s

    # Compute drifting time so that the cycletime is respected:
    # Time to descent to parking (mindepth to driftdepth at vertical_speed)
    transit = (driftdepth - mindepth) / vertical_speed
    # Time to descent to profile depth (driftdepth to maxdepth at vertical_speed)
    transit += (maxdepth - driftdepth) / vertical_speed
    # Time to ascent (maxdepth to mindepth at vertical_speed)
    transit += (maxdepth - mindepth) / vertical_speed
    drifttime = cycletime - transit

    if particle.cycle_phase == 0:
       # Phase 0: Sinking with vertical_speed until depth is driftdepth
       particle.depth += vertical_speed * particle.dt
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
        if particle.depth >= maxdepth:
            particle.cycle_phase = 3

    elif particle.cycle_phase == 3:
        # Phase 3: Rising with vertical_speed until at surface
        particle.depth -= vertical_speed * particle.dt
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
    if ((particle.lat < lat_min)|(particle.lat > lat_max)|(particle.lon < lon_min)|(particle.lon > lon_max)): 
        print("Particle out of the geographical domain --> deleted")
        particle.delete()
    # in the air, calm down float !    
    elif (particle.depth < depth_min) : 
        print("Particle is flying above surface, depth set to product min_depth. Carefull with your dtime")
        particle.depth = depth_min 
    # below fieldset   
    elif (particle.depth > depth_max) :   
        # if we're in phase 0 or 1 :
        # -> set particle depth to max non null depth, ascent 50 db and start drifting (phase 1)     
        if particle.cycle_phase <= 1 :
            print("Your float went below the fieldset, your dataset is probably not deep enough for what you're trying to do. It will drift here")
            particle.depth = depth_max - 50
            particle.cycle_phase = 1
        # if we're in phase 2 :
        # -> set particle depth to max non null depth, and start profiling (phase 3)  
        elif particle.cycle_phase == 2 :
            print("Your float went below the fieldset, your dataset is not deep enough for what you're trying to do. It will start profiling here")
            particle.depth = depth_max
            particle.cycle_phase = 3        
        else :
            pass                
    else :
        print("Particle deleted on unknown OutOfBoundsError")
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
    """
    USAGE :    
    ds : filenames for U & V
    var : dictionnary for variables 
    dim : dictionnary for dimensions lat,lon,depth,time
    isglobal : 1 if field is global, 0 otherwise
    """

    def __init__(self, **kwargs):
        #props
        self.field = kwargs['ds']
        self.var = kwargs['var']
        self.dim = kwargs['dim']
        self.isglobal = kwargs['isglobal']
        #define parcels fieldset
        self.fieldset = FieldSet.from_netcdf(
            self.field, self.var, self.dim, allow_time_extrapolation=True, time_periodic=False)

        if self.isglobal:
            self.fieldset.add_constant('halo_west', self.fieldset.U.grid.lon[0])
            self.fieldset.add_constant('halo_east', self.fieldset.U.grid.lon[-1])
            self.fieldset.add_constant('halo_south', self.fieldset.U.grid.lat[0])
            self.fieldset.add_constant('halo_north', self.fieldset.U.grid.lat[-1])
            self.fieldset.add_periodic_halo(zonal=True, meridional=True)

    def plot(self):
        temp_pset = ParticleSet(fieldset=self.fieldset, pclass=ArgoParticle, lon=0, lat=0, depth=0)
        temp_pset.show(field=self.fieldset.U, with_particles=False)
        #temp_pset.show(field = self.fieldset.V,with_particles = False)


class virtualfleet:
    """
    USAGE:
    lat,lon,depth,time : numpy arrays describing initial set of floats
    vfield : velocityfield object
    mission : dictionnary {'parking_depth':parking_depth, 'profile_depth':profile_depth, 'vertical_speed':vertical_speed, 'cycle_duration':cycle_duration}
    """

    def __init__(self, **kwargs):
        #props
        self.lat = kwargs['lat']
        self.lon = kwargs['lon']
        self.depth = kwargs['depth']
        self.time = kwargs['time']
        vfield = kwargs['vfield']
        mission = kwargs['mission']
        #Pass mission parameters to simulation through fieldset
        vfield.fieldset.add_constant('parking_depth', mission['parking_depth'])
        vfield.fieldset.add_constant('profile_depth', mission['profile_depth'])
        vfield.fieldset.add_constant('v_speed', mission['vertical_speed'])
        vfield.fieldset.add_constant(
            'cycle_duration', mission['cycle_duration'])

        #define parcels particleset
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

    def plotfloat(self):
        #using parcels psel builtin show function for now
        self.pset.show()

    def simulate(self, **kwargs):
        """
        USAGE:
        duration : number of days (365)
        dt_run : time step in hours for the computation (1/12)        
        dt_out : time step in hours for writing the output (24)
        output_file
        """
        duration = kwargs['duration']
        dt_run = kwargs['dt_run']
        dt_out = kwargs['dt_out']
        output_path = kwargs['output_file']
        if ((os.path.exists(output_path)) | (output_path=='')) :    
            temp_name = next(tempfile._get_candidate_names())+'.nc'
            while os.path.exists(temp_name):
                temp_name = next(tempfile._get_candidate_names())+'.nc'                
            output_path = temp_name        
            print("Filename empty of file already exists, simulation will be saved in : " + output_path)
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
