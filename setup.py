#!/usr/bin/env python

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

# def local_scheme(version):
#     """Skip the local version (eg. +xyz of 0.6.1.dev4+gdf99fe2) to be able to upload to Test PyPI"""
#     return ""

setuptools.setup(
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    # use_scm_version={'write_to': 'virtualargofleet/_version_setup.py'}
    # use_scm_version={"local_scheme": local_scheme},
)