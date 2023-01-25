"""
Kernels are inspired from: https://nbviewer.org/github/OceanParcels/parcels/blob/master/parcels/examples/tutorial_Argofloats.ipynb
"""
import numpy as np
from parcels import JITParticle, Variable
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


def ArgoFloatKernel(particle, fieldset, time):
    """Default kernel to simulate an Argo float cycle

    It only takes (particle, fieldset, time) as arguments.

    Virtual float missions parameters are passed as attributes to the fieldset (see below).

    This function will be compiled as a :class:`parcels.kernel.kernelsoa.KernelSOA` at run time.

    Parameters
    ----------
    particle: :class:`ArgoParticle`
        An instance of virtual Argo float
    fieldset: :class:`parcels.fieldset.FieldSet`
        A FieldSet class instance that holds hydrodynamic data needed to transport virtual floats. This instance must
        also have the following attributes:

        - ``parking_depth``, ``profile_depth``, ``vertical_speed``, ``cycle_duration``, ``life_expectancy``
    time
    """
    driftdepth = fieldset.parking_depth
    maxdepth = fieldset.profile_depth
    mindepth = 1  # not too close to the surface so that particle doesn't go above it
    v_speed = fieldset.vertical_speed  # in m/s
    cycletime = fieldset.cycle_duration * 3600  # has to be in seconds
    particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
    max_cycle_number = fieldset.life_expectancy
    verbose_print = False
    if fieldset.verbose_events == 1:
        verbose_print = True

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
            # if verbose_print:
            #     print(
            #         "Grouding during descent to parking or during parking, rising up 50m and try drifting here.")
            particle.depth = particle.depth - 50
            particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
            particle.cycle_phase = 1
        # if we're in phase 2:
        #-> start profiling (phase 3)
        elif particle.cycle_phase == 2:
            # if verbose_print:
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
        # if verbose_print:
        #     print("%i > %i" % (particle.cycle_number, max_cycle_number))
        #     print("Field Warning : This float is killed because it exceeds its life expectancy")
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
    driftdepth = fieldset.parking_depth
    maxdepth = fieldset.profile_depth
    mindepth = 1  # not too close to the surface so that particle doesn't go above it
    v_speed = fieldset.vertical_speed  # in m/s
    cycletime = fieldset.cycle_duration * 3600  # has to be in seconds
    particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
    max_cycle_number = fieldset.life_expectancy
    verbose_print = False
    if fieldset.verbose_events == 1:
        verbose_print = True

    # Adjust mission parameters if float enters in the experiment area:
    xmin, xmax = fieldset.area_xmin, fieldset.area_xmax
    ymin, ymax = fieldset.area_ymin, fieldset.area_ymax
    if particle.lat >= ymin and particle.lat <= ymax and particle.lon >= xmin and particle.lon <= xmax:
        if not particle.in_area:
            # if verbose_print:
            #     print("Field Warning : This float is entering the experiment area")
            particle.in_area = 1
        cycletime = fieldset.area_cycle_duration * 3600  # has to be in seconds
        driftdepth = fieldset.area_parking_depth
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
            # if verbose_print:
            #     print("Grouding during descent to parking or during parking, rising up 50m and try drifting here.")
            particle.depth = particle.depth - 50
            particle.in_water = fieldset.mask[time, particle.depth, particle.lat,
                                      particle.lon]
            particle.cycle_phase = 1
        # if we're in phase 2:
        #-> start profiling (phase 3)
        elif particle.cycle_phase == 2:
            # if verbose_print:
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
        # if verbose_print:
        #     print("%i > %i" % (particle.cycle_number, max_cycle_number))
        #     print("Field Warning : This float is killed because it exceeds its life expectancy")
        particle.delete()
    else:  # otherwise continue to cycle
        particle.cycle_age += particle.dt  # update cycle_age


def DeleteParticleKernel(particle, fieldset, time):
    """Define recovery for OutOfBounds Error."""

    # Get velocity field bounds
    lat_min, lat_max = fieldset.gridset.dimrange(dim='lat')
    lon_min, lon_max = fieldset.gridset.dimrange(dim='lon')
    # Get the center of the cellgrid for depth
    dgrid = fieldset.gridset.grids[0].depth
    depth_min = dgrid[0] + (dgrid[1]-dgrid[0])/2
    depth_max = dgrid[-2]+(dgrid[-1]-dgrid[-2])/2

    #
    verbose_print = False
    if fieldset.verbose_events == 1:
        verbose_print = True

    # out of geographical area : here we can delete the particle
    if ((particle.lat < lat_min) | (particle.lat > lat_max) | (particle.lon < lon_min) | (particle.lon > lon_max)):
        # if verbose_print:
        #     print("Field warning : Particle out of the geographical domain --> deleted")
        particle.delete()
    # in the air, calm down float !
    elif (particle.depth < depth_min):
        # if verbose_print:
        #     print("Field Warning : Particle above surface, depth set to product min_depth.")
        particle.depth = depth_min
        particle.cycle_phase = 4
    # below fieldset
    elif (particle.depth > depth_max):
        # if we're in phase 0 or 1 :
        #-> set particle depth to max non null depth, ascent 50 db and start drifting (phase 1)
        if particle.cycle_phase <= 1:
            # if verbose_print:
            #     print("Field warning : Particle below the fieldset, your dataset is probably not deep enough for what you're trying to do. It will drift here")
            particle.depth = depth_max - 50
            particle.cycle_phase = 1
        # if we're in phase 2 :
        #-> set particle depth to max non null depth, and start profiling (phase 3)
        elif particle.cycle_phase == 2:
            # if verbose_print:
            #     print("Field warning : Particle below the fieldset, your dataset is not deep enough for what you're trying to do. It will start profiling here")
            particle.depth = depth_max
            particle.cycle_phase = 3
    else:
        # I don't know why yet but in some cases, during ascent, I get an outOfBounds error, even with a depth > depth_min...
        if particle.cycle_phase == 3:
            particle.depth = depth_min
            particle.cycle_phase = 4
        else:
            # if verbose_print:
            #     print("%i: %f" % (particle.cycle_phase, particle.depth))
            #     print("Field Warning : Unknown OutOfBounds --> deleted")
            particle.delete()


def PeriodicBoundaryConditionKernel(particle, fieldset, time):
    """Define periodic Boundary Conditions."""
    if particle.lon < fieldset.halo_west:
        particle.lon += fieldset.halo_east - fieldset.halo_west
    elif particle.lon > fieldset.halo_east:
        particle.lon -= fieldset.halo_east - fieldset.halo_west

    if particle.lat < fieldset.halo_south:
        particle.lat += fieldset.halo_north - fieldset.halo_south
    elif particle.lat > fieldset.halo_north:
        particle.lat -= fieldset.halo_north - fieldset.halo_south

