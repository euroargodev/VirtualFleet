.. currentmodule:: virtualfleet

What's New
==========

|release date| |PyPI|

|pypi dwn|

v0.3.0 (xx)
----------------------


v0.2.0 (30 Aug. 2021)
---------------------

By `K. Balem <http://www.github.com/quai20>`_

.. code-block:: python

    # Mission parameters
    parking_depth = 1000. #in m
    profile_depth = 2000.
    vertical_speed = 0.09 #in m/s
    cycle_duration = 10. # in days

    mission = {'parking_depth':parking_depth, 'profile_depth':profile_depth, 'vertical_speed':vertical_speed, 'cycle_duration':cycle_duration}
    VFleet = vaf.virtualfleet(lat=lat, lon=lon, depth=dpt, time=tim, vfield=VELfield, mission=mission)

v0.1.0 (29 Jun. 2020)
---------------------

By `K. Balem <http://www.github.com/quai20>`_

This is the first release of Virtual Fleet with a single kernel (type of virtual Argo float) available and all its parameters are set internally.

.. |pypi dwn| image:: https://img.shields.io/pypi/dm/virtualfleet?label=Pypi%20downloads
   :target: //pypi.org/project/virtualfleet/
.. |conda dwn| image:: https://img.shields.io/conda/dn/conda-forge/virtualfleet?label=Conda%20downloads
   :target: //anaconda.org/conda-forge/virtualfleet
.. |PyPI| image:: https://img.shields.io/pypi/v/virtualfleet
   :target: //pypi.org/project/virtualfleet/
.. |Conda| image:: https://anaconda.org/conda-forge/virtualfleet/badges/version.svg
   :target: //anaconda.org/conda-forge/virtualfleet
.. |release date| image:: https://img.shields.io/github/release-date/euroargodev/VirtualFleet
   :target: //github.com/euroargodev/VirtualFleet/releases
   
