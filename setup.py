#!/usr/bin/env python

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name="VirtualFleet",    
    author="VirtualFleet Developers",
    author_email="kevin.balem@ifremer.fr",
    description="A python library to simulate a fleet of argo floats.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/euroargodev/VirtualFleet",
    packages=setuptools.find_packages(),
    package_dir={"virtualargofleet": "virtualargofleet"},
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
        "Intended Audience :: Science/Research",
        "Operating System :: OS Independent",
        "Operating System :: POSIX",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Development Status :: 3 - Alpha",
    ]
)