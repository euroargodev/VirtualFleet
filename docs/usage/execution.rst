.. currentmodule:: virtualargofleet
.. _execution:

Running a virtual fleet simulation
==================================

You now have all the requirements fulfilled:

-  a deployment plan, from a dictionary with ``lat/lon/time`` arrays,
-  a velocity fieldset (of class :class:`parcels.fieldset.FieldSet`), possibly from a :class:`VelocityField` instance,
-  and a float mission configuration, possibly from a :class:`FloatConfiguration` instance.

So let's import the usual suspects:

.. code:: python

   from datetime import timedelta
   from virtualargofleet import VirtualFleet

and create a virtual fleet:

.. code:: python

   VFleet = VirtualFleet(plan=my_plan, fieldset=VELfield.fieldset, mission=cfg.mission)

.. code-block::

    <VirtualFleet>
    - 10 floats in the deployment plan
    - No simulation performed

.. note::

    This code assumes you named the deployment plan dictionary ``my_plan``, the velocity field instance ``VELfield`` and the float mission configuration instance ``cfg`` like in ":ref:`preparation`".


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
