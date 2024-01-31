Installation
============

Instructions
------------

Install the last release with pip:

.. code-block:: bash

    pip install VirtualFleet

you can also try to work with the latest dev. version:

.. code-block:: bash

    pip install git+http://github.com/euroargodev/VirtualFleet.git@master


Required dependencies
---------------------

- numpy >= 1.18
- pandas >= 1.1
- xarray >= 2022.12
- parcels >= 3.0.0
- zarr >= 2.13.3
- tqdm >= 4.64.1


Conda environnement
-------------------

Clean up previous environment:

.. code-block:: bash

    mamba remove --quiet --name virtualfleet --all --yes

Install environment dedicated to VirtualFleet:

.. code-block:: bash

    mamba env create --file environment.yml

This will create a new conda environment named 'virtualfleet'.
