# Argo Virtual Fleet Simulator

This repository hosts a python library to perform and analyse numerical simulation of virtual Argo floats.

The numerical simulator backend is [oceanparcels](http://oceanparcels.org/).

**Software status**: in active development

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




