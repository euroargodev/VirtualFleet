# Argo Virtual Fleet Simulator

This repository hosts a python library to perform and analyse numerical simulation of virtual Argo floats.

The numerical simulator backend is [oceanparcels](http://oceanparcels.org/), the version used here is : 2.1.4

**Software status**: in active development

## Expected API usage:

The ``virtualargofleet`` provides a convenient wrapper around the [oceanparcels](http://oceanparcels.org/) machinary.

```python
    import virtualargofleet as vaf
    [...] 
    tfield = vaf.velocityfield(ds=filenames, var=variables, dim=dimensions, isglobal=0)
    [...]
    myfleet = vaf.virtualfleet(lat=lat, lon=lon, depth=depth, time=ti, vfield=tfield)
    [...]
    myfleet.simulate(duration=365*2, dt_run=1./12, dt_out=24, output_file='test.nc')
```

### Example 1
10 floats advected for 1 years, dt= 5 minutes  
Using GulfStream subset of the Operational Mercator daily ocean analysis and forecast system at 1/12 degree.  
--> 2 cores in use  
--> 36 Gb of memory in use   
--> Runtime = 00:05:30 
  
![GS_10floats_1y](https://user-images.githubusercontent.com/17851004/76072356-21812180-5f98-11ea-94e4-c7f8cb574fd3.png)  


### Example 2
100 floats advected for 1 year, dt= 5 minutes  
Using GulfStream subset of the Operational Mercator daily ocean analysis and forecast system at 1/12 degree.  
--> 12 cores in use  
--> 38 Gb of memory in use     
--> Runtime = 00:05:42   
  
![GS_100floats_1y](https://user-images.githubusercontent.com/17851004/76072419-38277880-5f98-11ea-85c7-d7c87a121b27.png)


### Example 3
10 floats advected for 1 year, dt= 5 minutes  
Using Daily Mediterranean MFS - EAS4 of CMCC, at 1/24 degree.  
-->  3 cores in use  
-->  186 Gb of memory in use     
--> Runtime = 00:41:29
  
![MED_10floats_1y](https://user-images.githubusercontent.com/17851004/76072471-52f9ed00-5f98-11ea-9ed3-01322b41e46f.png)

### Float cycle representation in the simulation can be tweaked
![Basic_argo_cycle](https://user-images.githubusercontent.com/17851004/76072496-5f7e4580-5f98-11ea-9a92-9701657a1d6b.png)


***
This work is part and was supported by the following projects:
<div>
<img src="https://avatars1.githubusercontent.com/u/58258213?s=460&v=4" width="70"/>
<img src="https://user-images.githubusercontent.com/17851004/83142990-8fe60380-a0f1-11ea-85c1-f7b1d343be88.jpg" width="200"/>
<img src="https://www.umr-lops.fr/var/storage/images/_aliases/logo_main/medias-ifremer/medias-lops/logos/logo-lops-2/1459683-4-fre-FR/Logo-LOPS-2.png" width="70"/>
</div>



