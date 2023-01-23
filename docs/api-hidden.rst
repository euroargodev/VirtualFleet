.. Generate API reference pages, but don't display these in tables.
.. This extra page is a work around for sphinx not having any support for
.. hiding an autosummary table.

.. autosummary::
    :toctree: generated/

    virtualargofleet

    virtualargofleet.velocity_helpers.VelocityFieldFacade

    virtualargofleet.velocity_helpers.VelocityField
    virtualargofleet.velocity_helpers.VelocityField.add_mask
    virtualargofleet.velocity_helpers.VelocityField.set_global
    virtualargofleet.velocity_helpers.VelocityField.plot
    virtualargofleet.velocity_helpers.VelocityField.fieldset

    virtualargofleet.virtualargofleet.VirtualFleet
    virtualargofleet.virtualargofleet.VirtualFleet.simulate
    virtualargofleet.virtualargofleet.VirtualFleet.plot_positions
    virtualargofleet.virtualargofleet.VirtualFleet.to_index
    virtualargofleet.virtualargofleet.VirtualFleet.ParticleSet
    virtualargofleet.virtualargofleet.VirtualFleet.fieldset
    virtualargofleet.virtualargofleet.VirtualFleet.output

    virtualargofleet.utilities.simu2index
    virtualargofleet.utilities.simu2csv
    virtualargofleet.utilities.set_WMO
    virtualargofleet.utilities.get_float_config

    virtualargofleet.utilities.FloatConfiguration
    virtualargofleet.utilities.FloatConfiguration.update
    virtualargofleet.utilities.FloatConfiguration.to_json

    virtualargofleet.app_parcels.ArgoFloatKernel
    virtualargofleet.app_parcels.ArgoFloatKernel_exp
    virtualargofleet.app_parcels.ArgoParticle
    virtualargofleet.app_parcels.ArgoParticle_exp
