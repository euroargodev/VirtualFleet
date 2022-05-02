#!/usr/bin/env python

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

def local_scheme(version):
    """Skip the local version (eg. +xyz of 0.6.1.dev4+gdf99fe2)
    to be able to upload to Test PyPI"""
    return ""

if __name__ == "__main__":
    setuptools.setup(
        # use_scm_version={'write_to': 'virtualargofleet/_version_setup.py'}
        use_scm_version={"local_scheme": local_scheme},
        long_description = long_description,
        long_description_content_type = "text/markdown",
    )