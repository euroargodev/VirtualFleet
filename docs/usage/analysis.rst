.. currentmodule:: virtualargofleet

Simulation analysis
===================

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
