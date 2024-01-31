"""
Kernels are inspired from: https://nbviewer.org/github/OceanParcels/parcels/blob/master/parcels/examples/tutorial_Argofloats.ipynb
"""
import numpy as np
from parcels import JITParticle, Variable, StatusCode
import logging
import math


log = logging.getLogger("virtualfleet.parcels")


class ArgoParticle(JITParticle):
    """ Default class to represent an Argo float

    :class:`ArgoParticle` inherits from :class:`parcels.particle.JITParticle`.

    A :class:`.VirtualFleet` will create and work with a :class:`parcels.particleset.particlesetsoa.ParticleSetSOA`
    of this class.

    Returns
    -------
    :class:`parcels.particle.JITParticle`
    """
    cycle_phase = Variable('cycle_phase', dtype=np.int32, initial=0, to_write=True)
    """Cycle phase (init_descend = 0, drift = 1, profile_descend = 2, profile_ascend = 3, transmit = 4)"""

    cycle_number = Variable('cycle_number', dtype=np.int32, initial=1, to_write=True)  # 1-based
    """Cycle number (starts at 1)"""

    cycle_age = Variable('cycle_age', dtype=np.float32, initial=0., to_write=True)
    """Elapsed time since the beginning of the current cycle"""

    drift_age = Variable('drift_age', dtype=np.float32, initial=0., to_write=False)
    """Elapsed time since the beginning of the drifting phase"""

    in_water = Variable('in_water', dtype=np.float32, initial=1., to_write=False)
    """Boolean indicating if the virtual float is in land (0) or water (1), used to detect grounding, based on fieldset.mask"""    
    # mission parameters, in this particle class, they remain unchanged

    parking_depth = Variable('parking_depth', dtype=np.int32, initial=1000, to_write=False)
    """Float mission parameter parking depth in m"""

    profile_depth = Variable('profile_depth', dtype=np.int32, initial=2000, to_write=False)
    """Float mission parameter profile depth in m"""

    vertical_speed = Variable('vertical_speed', dtype=np.float32, initial=0.09, to_write=False)
    """Float mission parameter vertical speed in m/s"""

    cycle_duration = Variable('cycle_duration', dtype=np.int32, initial=240, to_write=False)
    """Float mission parameter cycle duration in hours"""

    life_expectancy = Variable('life_expectancy', dtype=np.int32, initial=200, to_write=False)
    """Float mission parameter life expectancy in cycle"""


def ArgoFloatKernel(particle, fieldset, time):
    """Default kernel to simulate an Argo float

    It only takes (particle, fieldset, time) as arguments.

    Virtual float missions parameters are passed as Variables to the particles.

    This function will be compiled at run time.

    Parameters
    ----------
    particle: :class:`ArgoParticle`
        An instance of virtual Argo float. 
        This instance must also have the following attributes:
        ``parking_depth``, ``profile_depth``, ``vertical_speed``, ``cycle_duration``, ``life_expectancy``
    fieldset: :class:`parcels.fieldset.FieldSet`
        A FieldSet class instance that holds hydrodynamic data needed to transport virtual floats.
        This instance must also have the following attributes:
        - ``verbose_events``, ``mask``
    time
    """
    drift_depth = particle.parking_depth
    profile_depth = particle.profile_depth

    v_speed = particle.vertical_speed  # in m/s
    cycletime = particle.cycle_duration * 3600  # has to be in seconds

    particle.in_water = fieldset.mask[time, particle.depth, particle.lat, particle.lon]
    max_cycle_number = particle.life_expectancy

    ########################
    # GROUNDING MANAGEMENT #
    ########################
    # (This is not in a kernel because it involves change in cycle phase)
    if not particle.in_water:
        grounded = False
        # if we're in phase 0 or 1 :
        #-> rising 50 db and start drifting (phase 1)
        if particle.cycle_phase <= 1:
            if fieldset.verbose_events and particle.cycle_phase == 0:
                print(
                    "Grounding during descent to parking, rising up 50m and start drifting there.")
            elif fieldset.verbose_events and particle.cycle_phase == 1:
                print(
                    "Grounding during drift at parking, rising up 50m and continue drifting there.")
            particle_ddepth = - 50
            particle.cycle_phase = 1
            grounded = True

        # if we're in phase 2:
        #-> start profiling (phase 3)
        elif particle.cycle_phase == 2:
            if fieldset.verbose_events:
                print("Phase 2: Grounding during descent to profile, starting profile here")
            particle.cycle_phase = 3
            grounded = True
        else:
            pass

    #################
    # DRIFTING TIME #
    #################
    # Compute drifting time so that the cycletime is respected

    # We need to take into account the fact that the float may try to reach inaccessible depths:
    if drift_depth < fieldset.vf_bottom:
        effective_drift_depth = drift_depth
    else:
        effective_drift_depth = fieldset.vf_bottom
    if profile_depth < fieldset.vf_bottom:
        effective_profile_depth = profile_depth
    else:
        effective_profile_depth = fieldset.vf_bottom

    if grounded:
        if particle.cycle_phase <= 1:
            effective_drift_depth = particle.depth + particle_ddepth
        if particle.cycle_phase == 2:
            effective_profile_depth = particle.depth

    # Compute all transit times:
    transit = (effective_drift_depth - fieldset.vf_surface) / v_speed  # Time to descent to parking
    transit += (effective_profile_depth - effective_drift_depth) / v_speed  # Time to descent to profile depth
    transit += (effective_profile_depth - fieldset.vf_surface) / v_speed  # Time to ascent to surface

    # And then adjust drifting time to respect cycletime:
    drift_time = cycletime - transit - 15 * 60  # Remove 15 minutes for surface transmission
    drift_time = math.floor(drift_time / particle.dt) * particle.dt  # Should be a multiple of dt

    ##########################
    # CYCLE PHASE MANAGEMENT #
    ##########################
    if particle.cycle_phase == 0:
        # Phase 0: Sinking with v_speed until depth is driftdepth
        particle_ddepth += v_speed * particle.dt

        # if particle.depth + particle_ddepth >= drift_depth:
        #     print("End of Phase 0: Reached drift_depth")
        #     particle.cycle_phase = 1
        #     particle_ddepth = 0
        #     particle_ddepth = drift_depth - particle.depth  # Make sure we're going exactly at drift_depth
        #     print("Phase 1: Drifting at depth for drift_time seconds")

        # We have 2 ifs in order to make sure that the first sample with cycle_phase=1 is exactly at the drift depth
        if particle.depth == drift_depth:
            if fieldset.verbose_events == 1:
                print("End of Phase 0: Reached drift_depth")
            particle.cycle_phase = 1
            particle_ddepth = 0
            if fieldset.verbose_events == 1:
                print("Phase 1: Drifting at depth for drift_time seconds")
        if particle.depth + particle_ddepth > drift_depth:
            if fieldset.verbose_events == 1:
                print("Phase 0 warning: Overshoot drift_depth, re-adjust depth to target")
            particle_ddepth = drift_depth - particle.depth  # Make sure we're going exactly at drift_depth

    if particle.cycle_phase == 1:
        # Phase 1: Drifting at depth for drift_time seconds
        particle.drift_age += particle.dt

        if particle.drift_age >= drift_time:
            if fieldset.verbose_events == 1:
                print("End of Phase 1: Drifted drift_time seconds")
            particle.drift_age = 0  # reset drift_age for next cycle
            particle.cycle_phase = 2
            if fieldset.verbose_events == 1:
                print("Phase 2: Sinking further to profile_depth")

    if particle.cycle_phase == 2:
        # Phase 2: Sinking further to profile_depth
        particle_ddepth += v_speed * particle.dt

        if particle.depth + particle_ddepth >= profile_depth:
            particle_ddepth = profile_depth - particle.depth  # Make sure we're not going deeper than profile_depth

        if particle.depth >= profile_depth:
            if fieldset.verbose_events == 1:
                print("End of Phase 2: Reached profile_depth")
            particle.cycle_phase = 3
            if fieldset.verbose_events == 1:
                print("Phase 3: Rising with v_speed until at surface")

    if particle.cycle_phase == 3:
        # Phase 3: Rising with v_speed until at surface
        particle_ddepth -= v_speed * particle.dt

        if particle.depth + particle_ddepth <= fieldset.vf_surface:
            # Now that we reached the surface, we update the cycle phase
            # Note that the float depth is managed by the KeepInWater kernel
            if fieldset.verbose_events == 1:
                print("End of Phase 3: Reached surface")
            particle.depth = fieldset.vf_surface
            particle_ddepth = 0  # Reset change in depth
            particle.cycle_phase = 4
            if fieldset.verbose_events == 1:
                print("Phase 4: Transmitting at surface until cycletime is reached")

    if particle.cycle_phase == 4:
        # Phase 4: Transmitting at surface until cycletime is reached

        if particle.cycle_age >= cycletime:
            if fieldset.verbose_events == 1:
                print("End of cycle number %i" % particle.cycle_number)
            particle.cycle_phase = 0
            particle.cycle_age = 0
            particle.cycle_number += 1
            particle_ddepth += v_speed * particle.dt  # Start descent toward profile_depth
            if fieldset.verbose_events == 1:
                print("Phase 0: Sinking with v_speed until depth is drift_depth")

    ###################
    # Life expectancy #
    ###################
    if particle.cycle_number > max_cycle_number:  # Kill this float before moving on to a new cycle
        if fieldset.verbose_events:
            print("Field Warning : This float is killed because it exceeds its life expectancy")
        particle.delete()
    else:  # otherwise continue to cycle
        particle.cycle_age += particle.dt  # update cycle_age


class ArgoParticle_exp(ArgoParticle):
    """ Class used to represent an Argo float that can temporarily change its mission parameters

    This class extends :class:`ArgoParticle`.

    To be used by the :class:`ArgoFloatKernel_exp` kernel.

    Returns
    -------
    :class:`parcels.particle.JITParticle`
    """
    in_area = Variable('in_area', dtype=np.float32, initial=0., to_write=False)
    """Boolean indicating if the virtual float in the experiment area (1) or not (0)"""


def ArgoFloatKernel_exp(particle, fieldset, time):
    """Argo float kernel to simulate an Argo float cycle with change of mission parameters in a specific geographical area

    Parameters
    ----------
    particle: :class:`ArgoParticle_exp`
        A virtual Argo float of 'local-change' type
    fieldset: :class:`parcels.fieldset.FieldSet`
        A FieldSet class instance that holds hydrodynamic data needed to transport virtual floats. This instance must
        also have the following attributes:

        - parking_depth, profile_depth, vertical_speed, cycle_duration, life_expectancy, mask
        - area_xmin, area_xmax, area_ymin, area_ymax, area_cycle_duration, area_parking_depth
    time
    """
    driftdepth = particle.parking_depth
    maxdepth = particle.profile_depth
    mindepth = 1  # not too close to the surface so that particle doesn't go above it
    v_speed = particle.vertical_speed  # in m/s
    cycletime = particle.cycle_duration * 3600  # has to be in seconds
    particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
    max_cycle_number = particle.life_expectancy
    fieldset.verbose_events = False
    if fieldset.verbose_events == 1:
        fieldset.verbose_events = True

    # Adjust mission parameters if float enters in the experiment area:
    xmin, xmax = particle.area_xmin, particle.area_xmax
    ymin, ymax = particle.area_ymin, particle.area_ymax
    if particle.lat >= ymin and particle.lat <= ymax and particle.lon >= xmin and particle.lon <= xmax:
        if not particle.in_area:
            # if fieldset.verbose_events:
            #     print("Field Warning : This float is entering the experiment area")
            particle.in_area = 1
        cycletime = particle.area_cycle_duration * 3600  # has to be in seconds
        driftdepth = particle.area_parking_depth
    else:
        particle.in_area = 0

    # Compute drifting time so that the cycletime is respected:
    # Time to descent to parking (mindepth to driftdepth at v_speed)
    transit = (driftdepth - mindepth) / v_speed
    # Time to descent to profile depth (driftdepth to maxdepth at v_speed)
    transit += (maxdepth - driftdepth) / v_speed
    # Time to ascent (maxdepth to mindepth at v_speed)
    transit += (maxdepth - mindepth) / v_speed
    drift_time = cycletime - transit - 15*60  # Remove 15 minutes for surface transmission
    drift_time = math.floor(drift_time / particle.dt) * particle.dt  # Should be a multiple of dt

    # Grounding management : Since parcels turns NaN to Zero within our domain, we have to manage
    # groundings in another way that the recovery of deleted particles (below)
    if not particle.in_water:
        # if we're in phase 0 or 1 :
        #-> rising 50 db and start drifting (phase 1)
        if particle.cycle_phase <= 1:
            # if fieldset.verbose_events:
            #     print("Grouding during descent to parking or during parking, rising up 50m and try drifting here.")
            particle.depth = particle.depth - 50
            particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
            particle.cycle_phase = 1
        # if we're in phase 2:
        #-> start profiling (phase 3)
        elif particle.cycle_phase == 2:
            # if fieldset.verbose_events:
            #     print("Grounding during descent to profile, starting profile here")
            particle.cycle_phase = 3
        else:
            pass

    # CYCLE MANAGEMENT
    if particle.cycle_phase == 0:
        # Phase 0: Sinking with v_speed until depth is driftdepth
        particle.depth += v_speed * particle.dt
        particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
        if particle.depth >= driftdepth:
            particle.cycle_phase = 1

    elif particle.cycle_phase == 1:
        # Phase 1: Drifting at depth for drift_time seconds
        particle.drift_age += particle.dt
        if particle.drift_age >= drift_time:
            particle.drift_age = 0  # reset drift_age for next cycle
            particle.cycle_phase = 2

    elif particle.cycle_phase == 2:
        # Phase 2: Sinking further to maxdepth
        particle.depth += v_speed * particle.dt
        particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
        if particle.depth >= maxdepth:
            particle.cycle_phase = 3

    elif particle.cycle_phase == 3:
        # Phase 3: Rising with v_speed until at surface
        particle.depth -= v_speed * particle.dt
        particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
        if particle.depth <= mindepth:
            particle.depth = mindepth
            particle.cycle_phase = 4

    elif particle.cycle_phase == 4:
        # Phase 4: Transmitting at surface until cycletime is reached
        if particle.cycle_age >= cycletime:
            # print("End of cycle number %i" % particle.cycle_number)
            particle.cycle_phase = 0
            particle.cycle_age = 0
            particle.cycle_number += 1

    # Life expectancy management:
    if particle.cycle_number > max_cycle_number:  # Kill this float before moving on to a new cycle
        # if fieldset.verbose_events:
        #     print("%i > %i" % (particle.cycle_number, max_cycle_number))
        #     print("Field Warning : This float is killed because it exceeds its life expectancy")
        particle.delete()
    else:  # otherwise continue to cycle
        particle.cycle_age += particle.dt  # update cycle_age


def PeriodicBoundaryConditionKernel(particle, fieldset, time):
    """Define periodic Boundary Conditions."""
    if particle.lon < fieldset.halo_west:
        particle_dlon += fieldset.halo_east - fieldset.halo_west
    elif particle.lon > fieldset.halo_east:
        particle_dlon -= fieldset.halo_east - fieldset.halo_west
    if particle.lat < fieldset.halo_south:
        particle_dlat += fieldset.halo_north - fieldset.halo_south
    elif particle.lat > fieldset.halo_north:
        particle_dlast -= fieldset.halo_north - fieldset.halo_south



def KeepInDomain(particle, fieldset, time):
    # out of geographical area : here we can delete the particle
    if particle.state == StatusCode.ErrorOutOfBounds:
        if fieldset.verbose_events == 1:
            print("Field warning : Float out of the horizontal geographical domain --> deleted")
        particle.delete()


def KeepInWater(particle, fieldset, time):
    if particle.state == StatusCode.ErrorThroughSurface:
        # Make the float sticks to the surface level
        # Rq: change in cycle phase is managed by the FloatKernel
        if fieldset.verbose_events == 1:
            print("Field Warning : Float above surface, depth set to fieldset surface level")
        particle.depth = fieldset.vf_surface
        particle_ddepth = 0  # Reset change in depth
        particle.state = StatusCode.Success


def KeepInColumn(particle, fieldset, time):
    if particle.state == StatusCode.ErrorOutOfBounds:
        # Make the float sticks to the bottom level
        # Rq: change in cycle phase is managed by the FloatKernel
        # Here, we don't let the float going deeper, and change in particle_ddepth are managed by FloatKernel
        # depending on the cycle phase
        if fieldset.verbose_events == 1:
            print(
                "Field warning : Float reached fieldset bottom ! Your fieldset is not deep enough compared to float drift or profiling depths.")
        particle.depth = fieldset.vf_bottom
        particle.state = StatusCode.Success
