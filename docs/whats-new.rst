.. currentmodule:: virtualargofleet

What's New
==========

|release date| |PyPI|

|pypi dwn|

v0.3.0 (XX Jan. 2023)
----------------------
By `G. Maze <http://www.github.com/gmaze>`_ and `K. Balem <http://www.github.com/quai20>`_.

This last release is a major one. It introduces new features and breaking changes in the API.

**New features**

- New **Argo float configuration manager**. It was designed to make easier the access, management and backup of the virtual floats mission configuration parameters. All details are available on the API page :class:`FloatConfiguration` and the documentation page ":ref:`preparation_cfg`".

.. code-block:: python

    cfg = FloatConfiguration('default')  # Internally defined
    cfg = FloatConfiguration('cfg_file.json')  # From json file
    cfg = FloatConfiguration([6902919, 132])  # From Euro-Argo Fleet API
    cfg.update('parking_depth', 500)  # Update one parameter value
    cfg.params  # Return the list of parameters
    cfg.mission # Return the configuration as a dictionary, to be pass on a VirtualFleet instance
    cfg.to_json("cfg_file.json") # Save to file for later re-use

- New **Argo virtual floats type**: this new float type can change their mission parameters when they enter a specific geographic area (a rectangular domain). In order to use these floats, you can load a :class:`FloatConfiguration` instance with the ``local-change`` name, like this:

.. code-block:: python

    cfg = FloatConfiguration('local-change')
    cfg.update('area_cycle_duration', 120)  # Update default parameters for your own experiment

where you will note the added properties ``area_*``:

.. code-block:: none

    <FloatConfiguration><local-change>
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

Passing this specific :class:`FloatConfiguration` instance to a :class:`VirtualFleet` will automatically select the appropriate Argo float parcel kernels (:class:`app_parcels.ArgoFloatKernel_exp`). This new float type was developed for the `EA-RISE WP2.3 Gulf-Stream experiment <https://github.com/euroargodev/VirtualFleet_GulfStream>`__.

- All Argo float types (``default`` and ``local-change``) now come with a proper cycle number property. This makes much easier the tracking of the float profiles.

**Utilities**:

- :class:`utilities.simu2index`, :class:`utilities.simu2csv`: An Argo **profile index extractor** from the simulation netcdf output. It is not trivial to extract the position of virtual float profiles from the trajectory file of the simulation output. We made this easier with these functions. It also comes bundled with the :class:`VirtualFleet.to_index` method.
- :class:`utilities.set_WMO`: A function to **identify virtual floats with their real WMO** from the deployment plan. This could be handful if the deployment plan is actually based on real floats with WMO.
- :class:`utilities.get_float_config`: A function to **retrieve Argo float cycle configuration** using the `Euro-Argo meta-data API <https://fleetmonitoring.euro-argo.eu/swagger-ui.html>`__: .

**Breaking changes**

- Huge internal refactoring, with proper submodule assignment !
- ``VelocityField`` now refers to :class:`VelocityField`, while the high-level function to work with known velocity fields is :meth:`Velocity`.
- Options in :class:`VirtualFleet`:

  - instantiation option named ``vfield`` has been replaced by ``fieldset`` and now must take a :class:`parcels.fieldset.FieldSet` or a :class:`VelocityField` instance.
  - the simulate method have been renamed to be more explicit and now takes timedelta as values, instead of mixed/confusing integer units.


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
   
