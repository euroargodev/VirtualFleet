|<img src="https://raw.githubusercontent.com/euroargodev/virtualfleet/master/docs/img/repo_picture_tight.png" alt="VirtualFleet logo" width="400"><br>``Virtual Fleet`` is a Python package to make and analyse simulations of virtual Argo float trajectories.|
|:---------:|
|[![Gitter](https://badges.gitter.im/Argo-floats/virtual-fleet.svg)](https://gitter.im/Argo-floats/virtual-fleet?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge) ![Documentation](https://img.shields.io/static/v1?label=Doc&message=github.io&color=<COLOR>&logo=readthedocs) <br> 
![parcels](https://img.shields.io/static/v1?labelColor=000&label=Parcels&message=ParticleSet&color=11aed5&logo=) ![parcels](https://img.shields.io/static/v1?labelColor=000&label=Parcels&message=kernels&color=aa11d5&logo=)|

Using a 3D velocity fields, program your own Argo floats behaviour, set-up a
deployment plan and simulate trajectories (and sampling) of your virtual
fleet of Argo floats.

**Virtual Fleet** uses [Parcels](http://oceanparcels.org/) to simulate Argo floats and to compute trajectories.
**Virtual Fleet** provides methods to easily set up a deployment plan, float parameters and to analyse trajectories.

### Documentation

Checkout the documentation at: https://euroargodev.github.io/VirtualFleet
 
### Usage

Import the usual suspects:
```python
from virtualargofleet import VelocityField, VirtualFleet, FloatConfiguration
import numpy as np
from datetime import timedelta
```

Define velocity field to use:
```python
src = "/home/datawork-lops-oh/somovar/WP1/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"
VELfield = VelocityField(model='GLOBAL_ANALYSIS_FORECAST_PHY_001_024', src="%s/2019*.nc" % src)
```

Define a deployment plan:
```python
# Number of floats we want to simulate:
nfloats = 10

# Define space/time locations of deployments:
lat = np.linspace(30, 38, nfloats)
lon = np.full_like(lat, -60)
tim = np.array(['2019-01-01' for i in range(nfloats)], dtype='datetime64')
```

Define Argo floats mission parameters:
```python
cfg = FloatConfiguration('default')  # Standard Argo  
cfg = FloatConfiguration([6902919, 98])  # or extract a specific Argo float cycle configuration   
# cfg.update('parking_depth', 500)
cfg
```

Define the virtual fleet:
```python
VFleet = virtualfleet(lat=lat, lon=lon, time=tim, fieldset=VELfield.fieldset, mission=cfg.mission)
```
and execute a simulation: 
```python
VFleet.simulate(duration=timedelta(days=365), 
                step=timedelta(minutes=5), 
                record=timedelta(hours=1), 
                output_file='output.nc')
```

### What's new ?
The last release 0.3 introduces a couple of new features but also breaking changes in the API.

#### New features
- An **Argo float configuration manager**. This was designed to make easier the access, management and backup of the virtual floats mission configuration parameters.
```python
    cfg = FloatConfiguration('default')  # Internally defined
    cfg = FloatConfiguration('cfg_file.json')  # From json file
    cfg = FloatConfiguration([6902919, 132])  # From Euro-Argo Fleet API
    cfg.update('parking_depth', 500)  # Update one parameter value
    cfg.params  # Return the list of parameters
    cfg.mission # Return the configuration as a dictionary, to be pass on a VirtualFleet instance 
    cfg.to_json("cfg_file.json") # Save to file for later re-use
```      
- **New Argo virtual floats type**: this new float type can change their mission parameters when they enter a specific geographic area (a rectangular domain). In order to select these floats, you have to add to load the specific FloatConfiguration instance ``local-change``, like this:
```python
    cfg = FloatConfiguration('local-change')  # Internally define new float parameters area_*
    >> <FloatConfiguration><local-change>
          - area_cycle_duration (Maximum length of float complete cycle in AREA): 120.0 [hours]
          - area_parking_depth (Drifting depth in AREA): 1000.0 [m]
          - area_xmax (AREA Eastern bound): -48.0 [deg_longitude]
          - area_xmin (AREA Western bound): -75.0 [deg_longitude]
          - area_ymax (AREA Northern bound): 45.5 [deg_latitude]
          - area_ymin (AREA Southern bound): 33.0 [deg_latitude]
          - cycle_duration (Maximum length of float complete cycle): 240.0 [hours]
          - life_expectancy (Maximum number of completed cycle): 200 [cycle]
          - parking_depth (Drifting depth): 1000.0 [m]
          - profile_depth (Maximum profile depth): 2000.0 [m]
          - vertical_speed (Vertical profiling speed): 0.09 [m/s]
    cfg.update('cycle_duration', 120)  # Update default parameters for your own experiment
```
  Passing this specific ``FloatConfiguration`` to a new VirtualFleet instance will automatically select the appropriate Argo float parcel kernels. This new float type was developed for the [EA-RISE WP2.3 Gulf-Stream experiment](https://github.com/euroargodev/VirtualFleet_GulfStream).

- All Argo float types (_default_ and _local-change_) now come with a proper cycle number property. This makes much easier the tracking of the float profiles.

- **Post-processing utilities**:
  - An Argo profile index extractor from the simulation netcdf output. It is not trivial to extract the position of virtual float profiles from the trajectory file of the simulation output. We made this easier with the ``simu2index`` and ``simu2csv`` functions.
  - A function to identify virtual floats with their real WMO from the deployment plan. This could be handful if the deployment plan is actually based on real floats with WMO. 

#### Breaking changes

- Internal refactoring, with proper submodule assignment.
- Options in the VirtualFleet
  - instantiation option ``vfield`` has been replaced by ``fieldset`` and now must take a Parcels fieldset instance.
  - simulate method have been renamed to be more explicit and now takes timedelta as values, instead of mixed integer units. 

### Why Virtual Fleet?

The optimisation of the Argo array is quite complex to determine in specific regions, where the local ocean dynamic shifts away from *standard* large scale open ocean. These regions are typically the Western Boundary Currents where turbulence is more significant than anywhere else, and Polar regions where floats can temporarily evolve under sea-ice. **Virtual Fleet** aims to help the Argo program to optimise floats deployment and programming in such regions.

***
"Virtual Fleet" is part of the Euro-ArgoRISE project. This project has received funding from the European Union’s Horizon 2020 research and innovation programme under grant agreement no 824131. Call INFRADEV-03-2018-2019: Individual support to ESFRI and other world-class research infrastructures.
<div>
<a href="https://www.euro-argo.eu/EU-Projects/Euro-Argo-RISE-2019-2022">
<img src="https://user-images.githubusercontent.com/59824937/146353317-56b3e70e-aed9-40e0-9212-3393d2e0ddd9.png" height="100">
</a>
</div>  
This software is developed by:
<div>
<img src="https://www.umr-lops.fr/var/storage/images/_aliases/logo_main/medias-ifremer/medias-lops/logos/logo-lops-2/1459683-4-fre-FR/Logo-LOPS-2.png" height="75">
<a href="https://wwz.ifremer.fr"><img src="https://user-images.githubusercontent.com/59824937/146353099-bcd2bd4e-d310-4807-aee2-9cf24075f0c3.jpg" height="75"></a>
<img src="https://github.com/euroargodev/euroargodev.github.io/raw/master/img/logo/ArgoFrance-logo_banner-color.png" height="75">
</div>
