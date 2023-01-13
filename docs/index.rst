VirtualFleet python library
===========================

**virtualargofleet** is a python library dedicated to compute and analyse trajectory simulations of virtual Argo floats.

|lifecycle| |License|  |Gitter|


Documentation
-------------

**Getting Started**

* :doc:`install`
* :doc:`Usage <usage/index>`
* :doc:`Examples <examples/index>`

**Help & reference**

* :doc:`whats-new`
* :doc:`api`


.. _why:

Why VirtualFleet ?
==================

The optimisation of the Argo array is quite complex to determine in specific regions, where the local ocean dynamic shifts away from *standard* large scale open ocean. These regions are typically the Boundary Currents where turbulence is more significant than anywhere else, and Polar regions where floats can temporarily evolve under sea-ice. **Virtual Fleet** aims to help the Argo program to optimise floats deployment and programming in such regions.


.. toctree::
    :maxdepth: 2
    :hidden:
    :caption: Getting Started

    install
    usage/index
    examples/index

.. toctree::
    :maxdepth: 2
    :hidden:
    :caption: Help & reference

    whats-new
    api


.. |Documentation| image:: https://img.shields.io/static/v1?label=&message=Read%20the%20documentation&color=blue&logo=read-the-docs&logoColor=white
   :target: https://virtualfleet.readthedocs.io

.. |Documentation Status| image:: https://img.shields.io/readthedocs/virtualfleet?logo=readthedocs
   :target: https://virtualfleet.readthedocs.io/en/latest/?badge=latest

.. |Gitter| image:: https://badges.gitter.im/Argo-floats/virtual-fleet.svg
   :target: https://gitter.im/Argo-floats/virtual-fleet?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge

.. |License| image:: https://img.shields.io/github/license/euroargodev/VirtualFleet

.. |lifecycle| image:: https://img.shields.io/badge/lifecycle-experimental-orange.svg
   :target: https://www.tidyverse.org/lifecycle/#experimental
