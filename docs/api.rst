.. currentmodule:: virtualargofleet

#############
API reference
#############

This page provides an auto-generated summary of VirtualFleet's API. For more details and examples, refer to the relevant chapters in the main part of the documentation.

Top-levels classes
==================

VirtualFleet
------------

.. autosummary::
    :toctree: generated/

    VirtualFleet

**Methods**

.. autosummary::
    :toctree: generated/

    VirtualFleet.simulate
    VirtualFleet.to_index
    VirtualFleet.plot_positions

**Attributes**

.. autosummary::
    :toctree: generated/

    VirtualFleet.ParticleSet
    VirtualFleet.fieldset
    VirtualFleet.output


FloatConfiguration
------------------

.. autosummary::
    :toctree: generated/

    FloatConfiguration
    FloatConfiguration.to_json
    FloatConfiguration.update
    FloatConfiguration.mission
    FloatConfiguration.tech
    FloatConfiguration.params

Velocity/Field
--------------

.. autosummary::
    :toctree: generated/

    Velocity
    VelocityField
    VelocityField.add_mask
    VelocityField.set_global
    VelocityField.plot
    VelocityField.fieldset

Utilities
=========

.. autosummary::
    :toctree: generated/

    utilities.simu2index
    utilities.simu2csv
    utilities.set_WMO
    utilities.get_float_config


Parcels Particles and kernels
=============================

.. autosummary::
    :toctree: generated/

    app_parcels.ArgoFloatKernel
    app_parcels.ArgoParticle
    app_parcels.ArgoFloatKernel_exp
    app_parcels.ArgoParticle_exp

