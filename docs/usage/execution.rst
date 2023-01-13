.. currentmodule:: virtualargofleet

Run the virtual fleet simulation
================================

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
