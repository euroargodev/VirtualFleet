.. currentmodule:: virtualargofleet

Usage
=====

In order to create a simulation of virtual Argo floats, you need to provide

-  A velocity field, as a :class:`parcels.fieldset.FieldSet` instance
-  A float deployment plan, as a dictionary with ``lat/lon/time`` arrays
-  Virtual floats mission configurations, as a dictionary

These requirements are explained below, together with VirtualFleet helpers to do it.

.. toctree::
    :maxdepth: 2

    preparation
    execution
    analysis
