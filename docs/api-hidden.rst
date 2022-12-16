.. Generate API reference pages, but don't display these in tables.
.. This extra page is a work around for sphinx not having any support for
.. hiding an autosummary table.

.. autosummary::
    :toctree: generated/

    virtualargofleet

    virtualargofleet.velocity_helpers.VelocityFieldFacade

    virtualargofleet.virtualargofleet.VirtualFleet
    virtualargofleet.virtualargofleet.VirtualFleet.simulate
    virtualargofleet.virtualargofleet.VirtualFleet.plot_positions
    virtualargofleet.virtualargofleet.VirtualFleet.to_index

    virtualargofleet.utilities.simu2index
    virtualargofleet.utilities.simu2csv
    virtualargofleet.utilities.set_WMO
    virtualargofleet.utilities.get_float_config

    virtualargofleet.utilities.FloatConfiguration
    virtualargofleet.utilities.FloatConfiguration.update
    virtualargofleet.utilities.FloatConfiguration.to_json
