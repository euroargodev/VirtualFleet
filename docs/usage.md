# Installation

Clone or download the code of **virtualfleet** and with a working conda/jupyter installation, you can create a dedicated environment :
```python
conda env create -f environment.yml
```
Then it should be available in your kernel list.

# API Usage

Import the usual suspects:
```python
from virtualargofleet import VelocityField, VirtualFleet, FloatConfiguration
import numpy as np
from datetime import timedelta
```

Define velocity field to use:
```python
src = "~/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"
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
# cfg = FloatConfiguration([6902919, 98])  # or extract a specific Argo float cycle configuration   
# cfg.update('parking_depth', 500)  # You can update default parameters for your own experiment
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

Simulation data will be saved into the ``output.nc`` file in this example.

You can extract the position of virtual profiles with the following utility function:
```python
from virtualargofleet.utilities import simu2csv
simu2csv(VFleet.run_params['output_file'])
```
this will create an Argo index file with all virtual profiles.

***
This work is part of the following projects:
<div>
<img src="https://github.com/euroargodev/euroargodev.github.io/raw/master/img/logo/logo-Euro-Argo-Rise_CMYK.png" width="70"/>
</div>
and is developed by:
<div>
<img src="https://github.com/euroargodev/euroargodev.github.io/raw/master/img/logo/ArgoFrance-logo_banner-color.png" width="200"/>
<img src="https://www.umr-lops.fr/var/storage/images/_aliases/logo_main/medias-ifremer/medias-lops/logos/logo-lops-2/1459683-4-fre-FR/Logo-LOPS-2.png" width="70"/>
</div>




