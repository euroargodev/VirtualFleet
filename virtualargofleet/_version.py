from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("virtualfleet")
except PackageNotFoundError:
    # package is not installed
    __version__ = '999'
    pass