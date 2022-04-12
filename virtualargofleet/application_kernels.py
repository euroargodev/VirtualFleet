import numpy as np
from parcels import JITParticle, Variable


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


def DeleteParticle(particle, fieldset, time):
    # define recovery for OutOfBounds Error

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

