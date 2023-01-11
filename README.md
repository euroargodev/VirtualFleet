|<img src="https://raw.githubusercontent.com/euroargodev/virtualfleet/master/docs/img/repo_picture_tight.png" alt="VirtualFleet logo" width="400"><br>``Virtual Fleet`` is a Python package to make and analyse simulations of virtual Argo float trajectories.|
|:---------:|
|[![Gitter](https://badges.gitter.im/Argo-floats/virtual-fleet.svg)](https://gitter.im/Argo-floats/virtual-fleet?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)
![parcels](https://img.shields.io/static/v1?labelColor=000&label=Parcels&message=ParticleSet&color=11aed5&logo=) ![parcels](https://img.shields.io/static/v1?labelColor=000&label=Parcels&message=kernels&color=aa11d5&logo=)|

Using a 3D velocity fields, program your own Argo floats behaviour, set-up a
deployment plan and simulate trajectories (and sampling) of your virtual
fleet of Argo floats.

**Virtual Fleet** uses [Parcels](http://oceanparcels.org/) to simulate Argo floats and to compute trajectories.
**Virtual Fleet** provides methods to easily set up a deployment plan, float parameters and to analyse trajectories.

# Documentation

* [Why Virtual Fleet?](#why-virtual-fleet-)
* [Usage](#usage)
  + [Velocity field](#velocity-field)
  + [Deployment plan](#deployment-plan)
  + [Argo floats mission parameters](#argo-floats-mission-parameters)
  + [Simulate a virtual fleet](#simulate-a-virtual-fleet)
  + [Analyse simulation](#analyse-simulation)
* [What's new ?](#what-s-new--)
    - [New features](#new-features)
    - [Breaking changes](#breaking-changes)
  
## Why Virtual Fleet?

The optimisation of the Argo array is quite complex to determine in specific regions, where the local ocean dynamic shifts away from *standard* large scale open ocean. These regions are typically the Boundary Currents where turbulence is more significant than anywhere else, and Polar regions where floats can temporarily evolve under sea-ice. **Virtual Fleet** aims to help the Argo program to optimise floats deployment and programming in such regions.
 
## Usage

Import the usual suspects:
```python
from virtualargofleet import VelocityField, VirtualFleet, FloatConfiguration
import numpy as np
from datetime import timedelta
```

### Velocity field
First, you need to define the velocity field to be used by the virtual fleet. **The VirtualFleet simulator can take any Parcels ``fieldset`` as input**.

However, to make things easier, we provide a convenient utility class ``VelocityField`` to be used for some standard pre-defined velocity fields. Create a ``VelocityField`` instance and then use it as input to the VirtualFleet simulator.

You can provide the path to velocity netcdf files, like this: 
```python
root = "/home/datawork-lops-oh/somovar/WP1/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"
VELfield = VelocityField(model='GLORYS12V1', src="%s/2019*.nc" % root)
```
or you can use your own velocity fields definition for Parcels:
```python
root = "/home/datawork-lops-oh/somovar/WP1/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"
filenames = {'U': root + "/20201210*.nc",
              'V': root + "/20201210*.nc"}
variables = {'U':'uo','V':'vo'}
dimensions = {'time': 'time', 'depth':'depth', 'lat': 'latitude', 'lon': 'longitude'}
VELfield = VelocityField(model='custom', src=filenames, variables=variables, dimensions=dimensions)
```
In this later case, the ``VelocityField`` class will take care of creating a Parcels ``fieldset`` with the appropriate land/sea mask and circular wrapper if the field is global. 

Currently, VirtualFleet supports the following ``model`` options to the ``VelocityField`` helper: 
- GLORYS12V1, PSY4QV3R1, GLOBAL_ANALYSIS_FORECAST_PHY_001_024 
- MEDSEA_ANALYSISFORECAST_PHY_006_013
- ARMOR3D, MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012
- custom if you want to set your own model definition

### Deployment plan

Then, you need to define a deployment plan for your virtual fleet. **The VirtualFleet simulator expects a dictionary with arrays for the latitude, longitude and time of virtual floats to deploy**. Depth is set by default to the surface, but this can be provided if necessary.

Example:
```python
# Number of floats we want to simulate:
nfloats = 10

# Define space/time locations of deployments:
lat = np.linspace(30, 38, nfloats)
lon = np.full_like(lat, -60)
tim = np.array(['2019-01-01' for i in range(nfloats)], dtype='datetime64')

# Define the deployment plan as a dictionary:
my_plan = {'lat': lat, 'lon': lon, 'time': tim}
```

### Argo floats mission parameters

You also need to define what are the float's mission configuration parameters. **The VirtualFleet simulator takes a simple dictionary with parameters as input**. But, again, VirtualFleet provides the convenient utility class ``FloatConfiguration`` to make things easier.

You can start with the *default* configuration like this:
```python
cfg = FloatConfiguration('default')  # Standard Argo float mission
```
```
<FloatConfiguration><default>
- cycle_duration (Maximum length of float complete cycle): 240.0 [hours]
- life_expectancy (Maximum number of completed cycle): 200 [cycle]
- parking_depth (Drifting depth): 1000.0 [m]
- profile_depth (Maximum profile depth): 2000.0 [m]
- vertical_speed (Vertical profiling speed): 0.09 [m/s]
```
or you can use a specific float cycle mission (data are retrieved from the [Euro-Argo meta-data API](https://fleetmonitoring.euro-argo.eu/swagger-ui.html)):
```python
cfg = FloatConfiguration([6902920, 98])  # or extract a specific Argo float cycle configuration
```
```
<FloatConfiguration><Float 6902920 - Cycle 98>
- cycle_duration (Maximum length of float complete cycle): 240.0 [hours]
- life_expectancy (Maximum number of completed cycle): 500 [cycle]
- parking_depth (Drifting depth): 1000.0 [m]
- profile_depth (Maximum profile depth): 2000.0 [m]
- vertical_speed (Vertical profiling speed): 0.09 [m/s]
```

Float configurations can be saved in json files:
```python
cfg.to_json("myconfig.json")
```
This can be useful for later re-use:
```python
cfg = FloatConfiguration("myconfig.json")
```

[Examples of such json files can be found in here](./virtualargofleet/assets).

### Simulate a virtual fleet

You now have all the requirements:
- [x] A velocity fieldset, from a ``VelocityField`` instance
- [x] A deployment plan, from the dictionary with ``lat/lon/time`` arrays
- [x] A float mission configuration, from the ``FloatConfiguration`` instance

So, let's create a virtual fleet:
```python
VFleet = virtualfleet(plan=my_plan, fieldset=VELfield.fieldset, mission=cfg.mission)
```
```<VirtualFleet>
- 10 floats in the deployment plan
- No simulation performed
```

To execute the simulation, we use the ``simulate`` method by providing at least the total simulation duration time as a timedelta (or number of days):
```python
VFleet.simulate(duration=timedelta(days=2))
```
```<VirtualFleet>
- 10 floats in the deployment plan
- Number of simulation(s): 1
- Last simulation meta-data:
	- Duration: 02d 00h 00m 00s
	- Data recording every: 01h 00m
	- Trajectory file: ./v24co0jc.zarr
	- Execution time: 00d 00h 00m 04s
	- Executed on: laptop_guillaume_boulot.lan
```
By default, virtual floats positions are saved hourly along their trajectories.

The simulated floats trajectories will be saved in the current directory as a [zarr file](https://zarr.readthedocs.io/). You can control where to save trajectories with the ``output_folder`` and ``output_file`` options, or set the ``output`` option to `False` to not save results at all.

Note that you can continue the simulation where it was using the ``restart`` option:
```python
VFleet.simulate(duration=timedelta(days=3), restart=True)
```
```<VirtualFleet>
- 10 floats in the deployment plan
- Number of simulation(s): 2
- Last simulation meta-data:
	- Duration: 03d 00h 00m 00s
	- Data recording every: 01h 00m
	- Trajectory file: ./ns6hj1__.zarr
	- Execution time: 00d 00h 00m 06s
	- Executed on: laptop_guillaume_boulot.lan
```
In this scenario, a new output file is created and trajectories start from where the previous simulation left virtual floats. 


### Analyse simulation

In order to look at the virtual floats trajectories you can read data directly from the output file:
```python
ds = xr.open_zarr(VFleet.output)
```

You can quickly plot the last position of the floats:
```python
VFleet.plot_positions()
```

You can extract a profile index from the trajectory file, after the VFleet simulation:
```python
VFleet.to_index()
# VFleet.to_index("simulation_profile_index.txt")  # Create an Argo-like profile index
```
or from any trajectory file:
```python
from virtualargofleet.utilities import simu2index, simu2csv
df = simu2index(xr.open_zarr("trajectory_output.zarr"))
# or to create the index file:
simu2csv("trajectory_output.zarr", index_file="output_ar_index_prof.txt")
```


## What's new ?
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
    >>> <FloatConfiguration><local-change>
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
  - instantiation option ``vfield`` has been replaced by ``fieldset`` and now must take a Parcels fieldset or a ``VelocityField`` instance.
  - simulate method have been renamed to be more explicit and now takes timedelta as values, instead of mixed integer units. 


***
"Virtual Fleet" was created by the Euro-ArgoRISE project. This project has received funding from the European Union’s Horizon 2020 research and innovation programme under grant agreement no 824131. Call INFRADEV-03-2018-2019: Individual support to ESFRI and other world-class research infrastructures.
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
</div>_
