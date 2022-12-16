.. currentmodule:: virtualargofleet

Usage
=====

In order to create a simulation of virtual Argo floats, you need to provide

-  A velocity field, as a :class:`parcels.fieldset.FieldSet` instance
-  A float deployment plan, as a dictionary with ``lat/lon/time`` arrays
-  Virtual floats mission configurations, as a dictionary

These requirements are explained below, together with VirtualFleet helpers to do it.

.. contents::
   :local:

Prepare the simulation
----------------------

First, let's import the usual suspects:

.. code:: python

   import numpy as np
   from datetime import timedelta
   from virtualargofleet import VelocityField, VirtualFleet, FloatConfiguration


Velocity field
~~~~~~~~~~~~~~

First, you need to define the velocity field to be used by the virtual fleet. The VirtualFleet simulator can take any Parcels :class:`parcels.fieldset.FieldSet` as input.

However, to make things easier, we provide a convenient utility class :class:`VelocityField` to be used for some standard pre-defined velocity fields. Create a :class:`VelocityField` instance and then use it as input to the VirtualFleet simulator.

You can provide the path to velocity netcdf files, like this:

.. code:: python

   root = "~/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"
   VELfield = VelocityField(model='GLORYS12V1', src="%s/2019*.nc" % root)

or you can use your own velocity fields definition:

.. code:: python

   root = "~/data/GLOBAL-ANALYSIS-FORECAST-PHY-001-024"
   filenames = {'U': root + "/20201210*.nc",
                 'V': root + "/20201210*.nc"}
   variables = {'U':'uo','V':'vo'}
   dimensions = {'time': 'time', 'depth':'depth', 'lat': 'latitude', 'lon': 'longitude'}
   VELfield = VelocityField(model='custom', src=filenames, variables=variables, dimensions=dimensions)

In this later case, the :class:`VelocityField` class will take care of creating a Parcels :class:`parcels.fieldset.FieldSet` with the appropriate land/sea mask and circular wrapper if the field is global.

Currently, VirtualFleet supports the following ``model`` options to the :class:`VelocityField` helper:

-  GLORYS12V1, PSY4QV3R1, GLOBAL_ANALYSIS_FORECAST_PHY_001_024
-  MEDSEA_ANALYSISFORECAST_PHY_006_013
-  ARMOR3D, MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012
-  custom if you want to set your own model definition


Deployment plan
~~~~~~~~~~~~~~~

Then, you need to define a deployment plan for your virtual fleet. **The VirtualFleet simulator expects a dictionary with arrays for the latitude, longitude and time of virtual floats to deploy**. Depth is set by default to the surface, but this can be provided if necessary.

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


Argo floats mission parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

`Examples of such json files can be found in here <./virtualargofleet/assets>`__.



Run the virtual fleet simulation
--------------------------------

You now have all the requirements fulfilled:

-  A velocity fieldset, from a :class:`VelocityField` instance
-  A deployment plan, from a dictionary with ``lat/lon/time`` arrays
-  A float mission configuration, from the :class:`FloatConfiguration` instance

So, let's create a virtual fleet:

.. code:: python

   VFleet = virtualfleet(plan=my_plan, fieldset=VELfield.fieldset, mission=cfg.mission)

.. code-block::

    <VirtualFleet>
    - 10 floats in the deployment plan
    - No simulation performed

To execute the simulation, we use the :meth:`VirtualFleet.simulate` method by providing at least the total simulation duration time as a timedelta (or number of days):

.. code:: python

   VFleet.simulate(duration=timedelta(days=2))

.. code-block::

    <VirtualFleet>
    - 10 floats in the deployment plan
    - Number of simulation(s): 1
    - Last simulation meta-data:
        - Duration: 02d 00h 00m 00s
        - Data recording every: 01h 00m
        - Trajectory file: ./v24co0jc.zarr
        - Execution time: 00d 00h 00m 04s
        - Executed on: laptop_guillaume_boulot.lan

By default, virtual floats positions are saved hourly along their trajectories.

The simulated floats trajectories will be saved in the current directory as a `zarr file <https://zarr.readthedocs.io/>`__. You can control where to save trajectories with the ``output_folder`` and ``output_file`` options, or set the ``output`` option to ``False`` to not save results at all.

Note that you can continue the simulation where it was using the ``restart`` option:

.. code:: python

   VFleet.simulate(duration=timedelta(days=3), restart=True)

.. code::

    <VirtualFleet>
    - 10 floats in the deployment plan
    - Number of simulation(s): 2
    - Last simulation meta-data:
        - Duration: 03d 00h 00m 00s
        - Data recording every: 01h 00m
        - Trajectory file: ./ns6hj1__.zarr
        - Execution time: 00d 00h 00m 06s
        - Executed on: laptop_guillaume_boulot.lan

In this scenario, a new output file is created and trajectories start from where the previous simulation left virtual floats.


Simulation analysis
-------------------

In order to look at the virtual floats trajectories you can read data directly from the output file:

.. code:: python

   ds = xr.open_zarr(VFleet.output)

You can quickly plot the last position of the floats:

.. code:: python

   VFleet.plot_positions()

You can extract a profile index from the trajectory file, after the VFleet simulation:

.. code:: python

   VFleet.to_index()

or create an Argo-like profile index:

.. code:: python

   VFleet.to_index("simulation_profile_index.txt")

or from any trajectory file using the utility function :meth:`utilities.simu2index`:

.. code:: python

   from virtualargofleet.utilities import simu2index, simu2csv
   df = simu2index(xr.open_zarr("trajectory_output.zarr"))
   # or to create the index file:
   simu2csv("trajectory_output.zarr", index_file="output_ar_index_prof.txt")
