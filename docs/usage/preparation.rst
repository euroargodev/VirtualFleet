.. currentmodule:: virtualargofleet
.. _preparation:

Preparation of a simulation
===========================

In order to create a simulation of virtual Argo floats, you need to provide the following:

-  a float deployment plan, as a dictionary with ``lat/lon/time`` arrays,
-  a velocity field, as a :class:`parcels.fieldset.FieldSet` instance,
-  and a virtual float mission configuration, as a dictionary.

These requirements are explained below, together with VirtualFleet helpers to do it.

But first, let's import the usual suspects:

.. code:: python

   import numpy as np
   from datetime import timedelta
   from virtualargofleet import Velocity, FloatConfiguration


Deployment plan
---------------

You need to define a deployment plan for your virtual fleet. **The VirtualFleet simulator expects a dictionary with arrays for the latitude, longitude and time of virtual floats to deploy**. Depth is set by default to the surface, but this can be provided if necessary.

Example:

.. code:: python

   # Number of floats we want to simulate:
   nfloats = 10

   # Define space/time locations of deployments:
   lat = np.linspace(30, 38, nfloats)
   lon = np.full_like(lat, -60)
   tim = np.array(['2019-01-01' for i in range(nfloats)], dtype='datetime64')

   # Define the deployment plan as a dictionary:
   my_plan = {'lat': lat, 'lon': lon, 'time': tim}


Velocity field
--------------

Then, you need to define the velocity field to be used by the virtual fleet.

.. note::

    The VirtualFleet simulator can take any Parcels :class:`parcels.fieldset.FieldSet` as input.

However, to make things easier, we provide a convenient utility function :meth:`Velocity` to be used for some standard pre-defined velocity fields. It allows to easily create a :class:`VelocityField` instance that will be used as input to the VirtualFleet simulator.

The 2 main ways to get a :class:`VelocityField` instance with the :meth:`Velocity` function are:

1/ Using a :class:`xarray.Dataset`:

.. code:: python

   root = "~/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"
   ds = xr.open_mfdataset(glob.glob("%s/20201210*.nc" % root))
   VELfield = Velocity(model='GLOBAL_ANALYSIS_FORECAST_PHY_001_024', src=ds)


2/ Using a ``custom`` definition of the required arguments:

.. code:: python

   root = "~/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"
   filenames = {'U': root + "/20201210*.nc",
                 'V': root + "/20201210*.nc"}
   variables = {'U':'uo', 'V':'vo'}
   dimensions = {'time': 'time', 'depth':'depth', 'lat': 'latitude', 'lon': 'longitude'}
   VELfield = Velocity(model='custom',
                       src=filenames,
                       variables=variables,
                       dimensions=dimensions)

In this later case, the function :meth:`Velocity` will take care of creating a :class:`parcels.fieldset.FieldSet` with the appropriate land/sea mask and circular wrapper if the field is global.

Currently, VirtualFleet supports the following values for the ``model`` options of :meth:`Velocity`:

-  ``GLORYS12V1``, ``PSY4QV3R1``, ``GLOBAL_ANALYSIS_FORECAST_PHY_001_024``
-  ``MEDSEA_ANALYSISFORECAST_PHY_006_013``
-  ``ARMOR3D``, ``MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012``
-  ``custom`` if you want to set your own model definition


Argo floats mission parameters
------------------------------

You also need to define what are the float's mission configuration parameters. **The VirtualFleet simulator takes a simple dictionary with parameters as input**. But, again, VirtualFleet provides the convenient utility class :class:`FloatConfiguration` to make things easier.

You can start with a *default* configuration like this:

.. code:: python

   cfg = FloatConfiguration('default')

.. code-block::

   <FloatConfiguration><default>
   - cycle_duration (Maximum length of float complete cycle): 240.0 [hours]
   - life_expectancy (Maximum number of completed cycle): 200 [cycle]
   - parking_depth (Drifting depth): 1000.0 [m]
   - profile_depth (Maximum profile depth): 2000.0 [m]
   - vertical_speed (Vertical profiling speed): 0.09 [m/s]

or you can use a specific float cycle mission (data are retrieved from the `Euro-Argo meta-data API <https://fleetmonitoring.euro-argo.eu/swagger-ui.html>`__):

.. code:: python

   cfg = FloatConfiguration([6902920, 98])

.. code-block::

   <FloatConfiguration><Float 6902920 - Cycle 98>
   - cycle_duration (Maximum length of float complete cycle): 240.0 [hours]
   - life_expectancy (Maximum number of completed cycle): 500 [cycle]
   - parking_depth (Drifting depth): 1000.0 [m]
   - profile_depth (Maximum profile depth): 2000.0 [m]
   - vertical_speed (Vertical profiling speed): 0.09 [m/s]

Float configurations can be saved in json files:

.. code:: python

   cfg.to_json("myconfig.json")

This can be useful for later re-use:

.. code:: python

   cfg = FloatConfiguration("myconfig.json")

`Examples of such json files can be found in here <https://github.com/euroargodev/VirtualFleet/tree/master/virtualargofleet/assets>`__.
