# Argo Virtual Fleet Simulator

This repository hosts a python library to perform and analyse numerical simulation of virtual Argo floats.

The numerical simulator backend is [oceanparcels](http://oceanparcels.org/).

**Software status**: in active development

Click here to [![badge](https://img.shields.io/badge/launch-Pangeo%20binder-579ACA.svg?logo=data:image/png;base64,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)](https://binder.pangeo.io/v2/gh/euroargodev/VirtualFleet/master?urlpath=lab/tree/examples/tryit.ipynb) and play with ``VirtualFleet`` before you even install it (thanks [Pangeo](pangeo.io)).

## API usage:

The ``virtualargofleet`` provides convenient wrappers around the [oceanparcels](http://oceanparcels.org/) machinary. 
Fully dedicated to virtual Argo floats.

First, import the library and define the velocity fields properties (file, variable names, etc...):

```python
    import virtualargofleet as vaf
    VELfield = vaf.velocityfield(ds=filenames, var=variables, dim=dimensions, isglobal=0)
```

Then define a virtual Argo float deployment plan:
```python
    VFleet = vaf.virtualfleet(lat=lat, lon=lon, depth=depth, time=ti, vfield=tfield)
```

And finally run the simulation:
```python
    VFleet.simulate(duration=365*2, dt_run=1./12, dt_out=24, output_file='test.nc')
```

## Examples

### Gulf Stream, Example 1

10 floats advected (initial positions in yellow dots) for 1 years, dt = 5 minutes.  

**Dataset** : 
- GulfStream subset of the Operational Mercator daily ocean analysis and forecast system at 1/12 degree.  
  
**Run** : 
- 2 cores in use  
- 36 Gb of memory in use   
- Runtime = 00:05:30 
  
![](https://user-images.githubusercontent.com/17851004/76072356-21812180-5f98-11ea-94e4-c7f8cb574fd3.png)  

### Gulf Stream, Example 2
100 floats advected for 1 year, dt = 5 minutes  

**Dataset**  : GulfStream subset of the Operational Mercator daily ocean analysis and forecast system at 1/12 degree.  

**Run** :
- 12 cores in use  
- 38 Gb of memory in use     
- Runtime = 00:05:42   

![](https://user-images.githubusercontent.com/17851004/76072419-38277880-5f98-11ea-85c7-d7c87a121b27.png)

### Mediterranean Sea
10 floats advected for 1 year, dt = 5 minutes  

**Dataset** : Daily Mediterranean MFS - EAS4 of CMCC, at 1/24 degree.  

**Run** :
- 3 cores in use  
- 186 Gb of memory in use     
- Runtime = 00:41:29
  
![](https://user-images.githubusercontent.com/17851004/76072471-52f9ed00-5f98-11ea-9ed3-01322b41e46f.png)

### Float cycle representation in the simulation can be tweaked

![](https://user-images.githubusercontent.com/17851004/76072496-5f7e4580-5f98-11ea-9a92-9701657a1d6b.png)

***
This work is part of the following projects:
<div>
<img src="https://avatars1.githubusercontent.com/u/58258213?s=460&v=4" width="70"/>
</div>
and is developped by:
<div>
<img src="http://www.argo-france.fr/wp-content/uploads/2019/10/Argo-logo_banner-color.png" width="200"/>
<img src="https://www.umr-lops.fr/var/storage/images/_aliases/logo_main/medias-ifremer/medias-lops/logos/logo-lops-2/1459683-4-fre-FR/Logo-LOPS-2.png" width="70"/>
</div>




