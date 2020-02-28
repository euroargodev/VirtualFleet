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

class ArgoParticle(JITParticle):
        # Phase of cycle: init_descend=0, drift=1, profile_descend=2, profile_ascend=3, transmit=4
        cycle_phase = Variable('cycle_phase', dtype=np.int32, initial=0.)
        cycle_age = Variable('cycle_age', dtype=np.float32, initial=0.)
        drift_age = Variable('drift_age', dtype=np.float32, initial=0.)       
        
# Define the new Kernel that mimics Argo vertical movement
def ArgoVerticalMovement(particle, fieldset, time):               
        driftdepth = 1000
        maxdepth = 2000
        mindepth = 20
        vertical_speed = 0.09  # in m/s
        cycletime = 10 * 86400  # in s
        drifttime = 10 * 86400 - 3600 # in s (taking ~1h to go down at 2000)

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
            if particle.cycle_age > cycletime:
                particle.cycle_phase = 0
                particle.cycle_age = 0         
               
        particle.cycle_age += particle.dt  # update cycle_age    
                
# define recovery for OutOfBounds Error
def DeleteParticle(particle, fieldset, time):  # delete particles who run out of bounds.    
    print("Particle deleted on boundary")
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
    def __init__(self,**kwargs):    
        #props
        self.field=kwargs['ds']
        self.var=kwargs['var']
        self.dim=kwargs['dim']
        self.isglobal=kwargs['isglobal']
        #define parcels fieldset
        self.fieldset = FieldSet.from_netcdf(self.field, self.var, self.dim, allow_time_extrapolation=True)
        if self.isglobal :
            self.fieldset.add_constant('halo_west', fieldset.U.grid.lon[0])
            self.fieldset.add_constant('halo_east', fieldset.U.grid.lon[-1])
            self.fieldset.add_constant('halo_south', fieldset.U.grid.lat[0])
            self.fieldset.add_constant('halo_north', fieldset.U.grid.lat[-1])
            self.fieldset.add_periodic_halo(zonal=True,meridional=True)
          
    def plot(self):
        temp_pset = ParticleSet(fieldset=self.fieldset, pclass=ArgoParticle, lon=0,lat=0,depth=0)
        temp_pset.show(field=self.fieldset.U,with_particles=False)
        #temp_pset.show(field=self.fieldset.V,with_particles=False)
        
class virtualfleet:
    """
    USAGE:
    lat,lon,depth,time : numpy arrays describing initial set of floats
    vfield : velocityfield object
    """    
    def __init__(self,**kwargs):    
        #props
        self.lat=kwargs['lat']
        self.lon=kwargs['lon']
        self.depth=kwargs['depth']        
        self.time=kwargs['time']
        vfield=kwargs['vfield']
        #define parcels particleset
        self.pset = ParticleSet(fieldset=vfield.fieldset, 
                                pclass=ArgoParticle,
                                lon=self.lon,
                                lat=self.lat,
                                depth=self.depth,
                                time=self.time)        
        if vfield.isglobal:
            # combine Argo vertical movement kernel with Advection kernel + boundaries
            self.kernels = ArgoVerticalMovement + self.pset.Kernel(AdvectionRK4) + self.pset.Kernel(periodicBC) 
        else:
            self.kernels = ArgoVerticalMovement + self.pset.Kernel(AdvectionRK4)
    
    def plotfloat(self):
        #using parcels psel builtin show function for now
        self.pset.show()
            
    def simulate(self,**kwargs):
        """
        USAGE:
        duration : number of days (365)
        dt_run : time step in hours for the computation (1/12)        
        dt_out : time step in hours for writing the output (24)
        output_file
        """        
        duration=kwargs['duration']
        dt_run=kwargs['dt_run']
        dt_out=kwargs['dt_out']
        output_file=kwargs['output_file']
        
        # Now execute the kernels for X days, saving data every Y minutes
        self.pset.execute(self.kernels, 
                          runtime=timedelta(days=duration), 
                          dt=timedelta(hours=dt_run), 
                          output_file=self.pset.ParticleFile(name=output_file,outputdt=timedelta(hours=dt_out)),
                          recovery={ErrorCode.ErrorOutOfBounds: DeleteParticle})                        
    
        