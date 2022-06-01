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

[![Binder](https://img.shields.io/static/v1.svg?logo=Jupyter&label=Binder&message=Click+here+to+try+VirtualFleet+online+!&color=blue&style=for-the-badge)](https://mybinder.org/v2/gh/euroargodev/binder-sandbox/main?urlpath=git-pull%3Frepo%3Dhttps%253A%252F%252Fgithub.com%252Feuroargodev%252FVirtualFleet%26urlpath%3Dlab%252Ftree%252FVirtualFleet%252Fexamples%252Ftry_it-CustomPlans.ipynb%26branch%3Dpackaging)

Import the usual suspects:
```python
from virtualargofleet import VelocityField, VirtualFleet, FloatConfiguration
import numpy as np
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
cfg = FloatConfiguration('default')
# cfg.update('parking_depth', 500)
cfg
```

Define and simulate the virtual fleet:
```python
VFleet = virtualfleet(lat=lat, lon=lon, time=tim, vfield=VELfield, mission=cfg.mission)
VFleet.simulate(duration=365, step=5, record=1, output_file='output.nc')
```


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
