import collections
import warnings
import numpy as np
import xarray as xr
from tqdm import tqdm
import concurrent.futures
import multiprocessing
import os
import pandas as pd
import logging
import json
import urllib.request
import pkg_resources
from string import Formatter
import platform
import socket
import psutil
from packaging import version
from typing import List, Dict, Union


log = logging.getLogger("virtualfleet.utils")
path2data = pkg_resources.resource_filename("virtualargofleet", "assets/")


class VFschema:

    def __init__(self, **kwargs):
        for key in self.required:
            if key not in kwargs:
                raise ValueError("Missing '%s' property" % key)
        for key in kwargs:
            if key in self.properties:
                setattr(self, key, kwargs[key])

    def __repr__(self):
        name = self.__class__.__name__
        summary = []
        for p in self.properties:
            if p != 'description':
                summary.append("%s=%s" % (p, getattr(self, p)))
        if hasattr(self, 'description'):
            summary.append("%s='%s'" % ('description', getattr(self, 'description')))

        return "%s(%s)" % (name, ", ".join(summary))

    def _repr_html_(self):
        return self.__repr__()

    class JSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, pd._libs.tslibs.nattype.NaTType):
                return None
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            if isinstance(obj, pd.Timedelta):
                return obj.isoformat()
            if isinstance(obj, (VFschema_meta, VFschema_parameter, VFschema_configuration)):
                return obj.__dict__
            # 👇️ otherwise use the default behavior
            return json.JSONEncoder.default(self, obj)

    @property
    def __dict__(self):
        d = {}
        for key in self.properties:
            value = getattr(self, key)
            d.update({key: value})
        return d

    def to_json(self, fp=None):
        jsdata = self.__dict__
        if hasattr(self, 'schema'):
            jsdata.update({"$schema": "https://raw.githubusercontent.com/euroargodev/json-schemas-FloatConfiguration/schemas/%s.json" % getattr(
                self, 'schema')})
        if fp is None:
            return json.dumps(jsdata, indent=4, cls=self.JSONEncoder)
        else:
            return json.dump(jsdata, fp, indent=4, cls=self.JSONEncoder)


class VFschema_meta(VFschema):
    unit: str
    dtype: str
    techkey: str

    description: str = "Meta-data of a configuration parameter"
    properties: List = ["unit", "dtype", "techkey"]
    required: List = []

    @staticmethod
    def from_dict(obj: Dict) -> 'VFschema_meta':
        return VFschema_meta(**obj)


class VFschema_parameter(VFschema):
    name: str
    value: Union[str, float]
    meta: VFschema_meta
    description: str = "One configuration parameter"

    properties: List = ["name", "value", "description", "meta"]
    required: List = ["name", "value"]

    def __init__(self, **kwargs):
        if 'meta' in kwargs and isinstance(kwargs['meta'], dict):
            kwargs['meta'] = VFschema_meta.from_dict(kwargs['meta'])
        super().__init__(**kwargs)

    @staticmethod
    def from_dict(obj: Dict) -> 'VFschema_parameter':
        return VFschema_parameter(**obj)


class VFschema_configuration(VFschema):
    version: str
    name: str
    parameters: List[VFschema_parameter]
    created: pd.Timestamp = None

    schema: str = "VF-ArgoFloat-Configuration"
    description: str = "VirtualFleet Argo Float configuration"
    properties: List = ["created", "version", "name", "parameters"]
    required: List = ["created", "version", "name", "parameters"]

    def __init__(self, **kwargs):
        if 'created' not in kwargs or kwargs['created'] is None:
            kwargs['created'] = pd.to_datetime('now', utc=True)
        if 'parameters' in kwargs:
            parameters = []
            for param in kwargs['parameters']:
                if isinstance(param, dict):
                    parameters.append(VFschema_parameter.from_dict(param))
                else:
                    parameters.append(param)
            kwargs['parameters'] = parameters
        super().__init__(**kwargs)

    @staticmethod
    def from_dict(obj: Dict) -> 'VFschema_configuration':
        return VFschema_configuration(**obj)


class ConfigParam:
    """Configuration parameter manager

    Create a key/value pair object with metadata description, unit and dtype.

    Examples
    --------
    >>> p = ConfigParam(key='profile_depth', value=2000.)
    >>> p = ConfigParam(key='profile_depth', value=2000., unit='m', description='Maximum profile depth', dtype=float)
    >>> p.value

    """
    str_val = lambda s, v: ("%s" % v).split("'")[1] if isinstance(v, type) else str(v)

    def __init__(self, key, value, **kwargs):
        self.key = key
        default_meta = {'description': '', 'unit': '', 'dtype': '', 'techkey': ''}
        self.meta = {**default_meta, **kwargs}
        self.set_value(value)

    def __repr__(self):
        desc = "" if self.meta['description'] == '' else "(%s)" % self.meta['description']
        unit = "" if self.meta['unit'] == '' else "[%s]" % self.meta['unit']
        return "%s %s: %s %s" % (self.key, desc, self.value, unit)

    def get_value(self):
        return self._value

    def set_value(self, value):
        if self.meta['dtype'] != '':
            try:
                value = self.meta['dtype'](value)
            except ValueError:
                raise ValueError("Cannot cast '%s' value as expected %s" % (self.key, self.str_val(self.meta['dtype'])))
        self._value = value

    @property
    def json_schema(self):
        return VFschema_parameter.from_dict({
            'name': self.key,
            'value': self.value,
            'description': self.meta['description'],
            'meta': {
                    'unit': self.meta['unit'],
                    'dtype': self.str_val(self.meta['dtype']),
                    'techkey': self.meta['techkey']}
        })

    def to_json(self):
        """Return a dictionary serialisable in json"""
        return self.json_schema.to_json()

    value = property(get_value, set_value)


class FloatConfiguration:
    """Float mission configuration manager

    Create a default configuration and then possibly update parameter values

    Can be used to create a virtual fleet, to save or load float configurations

    Examples
    --------
    >>> cfg = FloatConfiguration('default')  # Internally defined
    >>> cfg = FloatConfiguration('local-change')  # Internally defined
    >>> cfg = FloatConfiguration('cfg_file.json')  # From any json file
    >>> cfg = FloatConfiguration([6902919, 132])  # From Euro-Argo Fleet API
    >>> cfg.update('parking_depth', 500)  # Update one parameter value
    >>> cfg.params  # Return the list of parameters
    >>> cfg.mission # Return the configuration as a dictionary
    >>> cfg.tech # Return the configuration as a dictionary using Argo technical keys
    >>> cfg.to_json("cfg_file.json") # Save to file for later re-use
    >>> cfg

    """

    def __init__(self, name: Union[str, list] = 'default', *args, **kwargs):
        """

        Parameters
        ----------
        name: str
            Name of the configuration to load
        """
        self._params_dict = {}

        def load_from_json(name):
            # Load configuration from file
            with open(name, "r") as f:
                js = json.load(f)
            if js['version'] != "1.0":
                raise ValueError("Unsupported file format version '%s'" % js['version'])
            data = js['data']
            for key in data.keys():
                value = data[key]['value']
                meta = data[key]['meta']
                meta['dtype'] = eval(meta['dtype'])
                self.params = ConfigParam(key=key, value=value, **meta)
            name = js['name']
            return name, data

        if name == 'default':
            name, data = load_from_json(os.path.join(path2data, 'FloatConfiguration_default.json'))

        elif name == 'local-change':
            name, data = load_from_json(os.path.join(path2data, 'FloatConfiguration_local_change.json'))

        elif name == 'gse-experiment' or name == "gulf-stream":
            name, data = load_from_json(os.path.join(path2data, 'FloatConfiguration_gulf_stream.json'))

        elif isinstance(name, str) and os.path.splitext(name)[-1] == ".json":
            name, data = load_from_json(name)

        elif isinstance(name, list):
            # Load default configuration:
            load_from_json(os.path.join(path2data, 'FloatConfiguration_default.json'))

            # Load configuration of one float cycle from EA API
            wmo = name[0]
            cyc = name[1]
            name = "Float %i - Cycle %i" % (wmo, cyc)
            df = get_float_config(wmo, cyc)

            di = {'CONFIG_ProfilePressure_dbar': 'profile_depth',
                  'CONFIG_ParkPressure_dbar': 'parking_depth',
                  'CONFIG_CycleTime_hours': 'cycle_duration',
                  'CONFIG_MaxCycles_NUMBER': 'life_expectancy',
                  'CONFIG_AscentSpeed_mm/s': 'vertical_speed',
                  }
            # Over-write known parameters:
            for code in di.keys():
                if code in df:
                    self.update(di[code], df[code])
                    if code == 'CONFIG_AscentSpeed_mm/s':
                        self.update(di[code], df[code]/1000)  # Convert mm/s to m/s
                else:
                    msg = "%s not found for this profile, fall back on default value: %s" % \
                          (code, self._params_dict[di[code]])
                    # log.warning(msg)
                    warnings.warn(msg)

        else:
            raise ValueError("Please give me a known configuration name ('default', 'local-change', 'gulf-stream') or a json file to load from !")

        self.name = name

    def __repr__(self):
        summary = ["<FloatConfiguration><%s>" % self.name]
        for p in self._params_dict.keys():
            summary.append("- %s" % str(self._params_dict[p]))
        return "\n".join(summary)

    @property
    def params(self):
        """List of parameter keys"""
        return sorted([self._params_dict[p].key for p in self._params_dict.keys()])

    @params.setter
    def params(self, param):
        if not isinstance(param, ConfigParam):
            raise ValueError("param must be a 'ConfigParam' instance")
        if param.key not in self.params:
            self._params_dict[param.key] = param
            self._params_dict = collections.OrderedDict(sorted(self._params_dict.items()))

    def update(self, key: str, new_value):
        """Update value to an existing parameter

        Parameters
        ----------
        key: str
            Name of the parameter to update
        new_value:
            New value to attribute to this parameter
        """
        if key not in self.params:
            raise ValueError("Invalid parameter '%s' for configuration '%s'" % (key, self.name))
        self._params_dict[key].value = new_value
        return self

    @property
    def mission(self):
        """Return the float configuration as a dictionary to be used by a :class:`VirtualFleet`"""
        mission = {}
        for key in self._params_dict.keys():
            mission[key] = self._params_dict[key].value
        return mission

    @property
    def tech(self):
        """Float configuration as a dictionary using Argo technical keys"""
        mission = {}
        for key in self._params_dict.keys():
            if self._params_dict[key].meta['techkey'] != '':
                techkey = self._params_dict[key].meta['techkey']
                mission[techkey] = self._params_dict[key].value
        return mission

    @property
    def json_schema(self):
        parameters = [self._params_dict[key].json_schema for key in self._params_dict]
        return VFschema_configuration.from_dict({
            'name': self.name,
            'version': '2.0',
            'parameters': parameters
        })

    def to_json(self):
        """Return a dictionary serialisable in json"""
        return self.json_schema.to_json()


class SimulationSet:
    """Convenient class to manage a collection of simulations meta-data

    This class is used by VirtualFleet instances to keep track of all calls to the 'simulate' method.

    In the future, this could be used to computed aggregated statistics from several simulations.

    Examples
    --------
    >>> s = SimulationSet()
    >>> s.add({'execution_time': 1.8, 'platform': 'Darwin', 'output_path': 'trajectories_part1.zarr'})
    >>> s.add({'execution_time': 2.4, 'platform': 'Darwin', 'output_path': 'trajectories_part2.zarr'})
    >>> s.N
    >>> s.last
    """

    def __init__(self):
        self.simulated = False
        self.runs = []

    def __repr__(self):
        summary = ["<VirtualFleet.SimulationSet>"]
        summary.append("Executed: %s" % self.simulated)
        summary.append("Number of simulation(s): %i" % self.N)
        return "\n".join(summary)

    def add(self, params):
        """Add a new set of parameters to the simulation set"""
        self.simulated = True
        self.runs.append(params)
        return self

    @property
    def N(self):
        """Return the number of simulations in the set"""
        return len(self.runs)

    @property
    def last(self):
        """Return meta-data from the last simulation in the set"""
        return self.runs[-1]


def get_splitdates(t, N = 1):
    """Given a list of dates, return index of dates before a date change larger than N days"""
    dt = np.diff(t).astype('timedelta64[D]')
    # print(dt)
    return np.argwhere(dt > np.timedelta64(N, 'D'))[:, 0]


def splitonprofiles(ds, N = 1):
    sub_grp = ds.isel(obs=get_splitdates(ds['time'], N=N))
    # plt.plot(ds['time'], -ds['z'], 'k.')
    # plt.plot(sub_grp['time'], -sub_grp['z'], 'r.')
    return sub_grp


def simu2index(ds: xr.Dataset, N: int = 1):
    """Convert a trajectory simulation :class:`xarray.Dataset` to an Argo index of profiles

    Profiles are identified using the ``cycle_number`` dataset variable. A profile is identified if the last
    observation of a cycle_number sequence is in cycle_phase 3 or 4.

    This function remains compatible with older versions of trajectory netcdf files without the ``cycle_number``
    variable. In this case, a profile is identified if the last observation of a cycle_phase==3 sequence is separated
    by N days from the next sequence.

    Parameters
    ----------
    ds: :class:`xarray.Dataset`
        The simulation trajectories dataset
    N: int, optional
        The minimal time lag between cycle_phase sequences to be identified as a new profile. This will be removed in
        the future when we'll drop support for old netcdf outputs.
    Returns
    -------
    df: :class:`pandas.DataFrame`
        The profiles index
    """
    trajdim = 'trajectory' if version.parse(ds.attrs['parcels_version']) >= version.parse("2.4.0") else 'traj'

    ds_list = []
    if 'cycle_number' in ds.data_vars:
        for traj in tqdm(ds[trajdim], total=len(ds[trajdim])):
            for cyc, grp in ds.loc[{trajdim: traj}].groupby(group='cycle_number'):
                ds_cyc = grp.isel(obs=-1)
                if ds_cyc['cycle_phase'] in [3, 4]:
                    ds_cyc['traj_id'] = xr.DataArray(np.full_like((1,), fill_value=traj.data))
                    ds_list.append(ds_cyc)

    else:
        warnings.warn("This is an old trajectory file, results not guaranteed !")
        for traj in tqdm(ds[trajdim], total=len(ds[trajdim])):
            for iphase, grp in ds.loc[{trajdim: traj}].groupby(group='cycle_phase'):
                if iphase == 3:
                    sub_grp = splitonprofiles(grp, N=N)
                    sub_grp['cycle_number'] = xr.DataArray(np.arange(1, len(sub_grp['obs']) + 1), dims='obs')
                    sub_grp['traj_id'] = xr.DataArray(np.full_like(sub_grp['obs'], fill_value=traj.data), dims='obs')
                    ds_list.append(sub_grp)

    if len(ds_list) > 0:
        ds_profiles = xr.concat(ds_list, dim='obs')
        if 'wmo' not in ds_profiles.data_vars:
            ds_profiles['wmo'] = ds_profiles['traj_id'] + 9000000
        df = ds_profiles.to_dataframe()
        df = df.rename({'time': 'date', 'lat': 'latitude', 'lon': 'longitude', 'z': 'min_depth'}, axis='columns')
        df = df[['date', 'latitude', 'longitude', 'wmo', 'cycle_number', 'traj_id']]
        df['wmo'] = df['wmo'].astype('int')
        df['cycle_number'] = df['cycle_number'].astype('int')
        df['traj_id'] = df['traj_id'].astype('int')
        df['latitude'] = np.fix(df['latitude'] * 1000).astype('int') / 1000
        df['longitude'] = np.fix(df['longitude'] * 1000).astype('int') / 1000
        df = df.reset_index(drop=True)
        return df
    else:
        raise ValueError('No virtual floats reaches the final cycling phase, hence no profiles to index')


def simu2index_par(ds):
    def reducerA(sub_ds):
        sub_grp = None
        traj_id = np.unique(sub_ds['trajectory'])[0]
        for iphase, grp in sub_ds.groupby(group='cycle_phase'):
            if iphase == 3:
                sub_grp = splitonprofiles(grp, N=1)
                sub_grp['cycle_number'] = xr.DataArray(np.arange(1, len(sub_grp['obs']) + 1), dims='obs')
                sub_grp['traj_id'] = xr.DataArray(
                    np.full_like(sub_grp['obs'], fill_value=traj_id), dims='obs')
                return sub_grp

    def reducerB(sub_ds):
        ds_list = []
        traj_id = np.unique(sub_ds['trajectory'])[0]
        for cyc, grp in sub_ds.groupby(group='cycle_number'):
            ds_cyc = grp.isel(obs=-1)
            if ds_cyc['cycle_phase'] in [3, 4]:
                ds_cyc['traj_id'] = xr.DataArray(np.full_like((1,), fill_value=traj_id), dims='obs')
                ds_list.append(ds_cyc)
        try:
            ds = xr.concat(ds_list, dim='obs')
        except Exception:
            log.debug("Error on concat with traj_id: %i" % traj_id)
            ds = None
            pass
        return ds

    reducer = reducerB if 'cycle_number' in ds.data_vars else reducerA

    ConcurrentExecutor = concurrent.futures.ThreadPoolExecutor(max_workers=multiprocessing.cpu_count())
    with ConcurrentExecutor as executor:
        future_to_url = {executor.submit(reducer, ds.sel(traj=traj)): ds.sel(traj=traj) for traj in ds['traj']}
        futures = concurrent.futures.as_completed(future_to_url)
        futures = tqdm(futures, total=len(ds['traj']))

        ds_list, failed = [], []
        for future in futures:
            data = None
            try:
                data = future.result()
            except Exception:
                failed.append(future_to_url[future])
                raise
            finally:
                ds_list.append(data)

    ds_list = [r for r in ds_list if r is not None]  # Only keep non-empty results
    ds_profiles = xr.concat(ds_list, dim='obs')
    if 'wmo' not in ds_profiles.data_vars:
        ds_profiles['wmo'] = ds_profiles['traj_id'] + 9000000
    df = ds_profiles.to_dataframe()
    df = df.rename({'time': 'date', 'lat': 'latitude', 'lon': 'longitude', 'z': 'min_depth'}, axis='columns')
    df = df[['date', 'latitude', 'longitude', 'wmo', 'cycle_number', 'traj_id']]
    df['wmo'] = df['wmo'].astype('int')
    df['traj_id'] = df['traj_id'].astype('int')
    df['latitude'] = np.fix(df['latitude'] * 1000).astype('int') / 1000
    df['longitude'] = np.fix(df['longitude'] * 1000).astype('int') / 1000
    df = df.reset_index(drop=True)
    return df


def simu2csv(simu_file: str, index_file: str=None, df: pd.DataFrame=None):
    """Save simulation results profile index to file, as Argo index

    Argo profile index can be loaded with argopy.

    Parameters
    ----------
    simu_file: str
        Path to netcdf file of simulation results, to load profiles from
    index_file: str, optional
        Path to csv file to write index to. By default, it is set using the ``simu_file`` value.
    df: :class:`pandas.DataFrame`, optional
        If provided, will be used as the profile index, otherwise, compute index from ``simu_file``

    Returns
    -------
    index_file: str
        Path to the Argo profile index created
    """
    if index_file is None:
        file_name, file_extension = os.path.splitext(index_file)
        index_file = simu_file.replace(file_extension, "_ar_index_prof.txt")

    txt_header = """# Title : Profile directory file of a VirtualFleet simulation
# Description : Profiles from simulation result file: {}
# Project : ARGO, EARISE
# Format version : 2.0
# Date of update : {}
# FTP root number 1 : ftp://ftp.ifremer.fr/ifremer/argo/dac
# FTP root number 2 : ftp://usgodae.org/pub/outgoing/argo/dac
# GDAC node : -
""".format(os.path.abspath(simu_file), pd.to_datetime('now', utc=True).strftime('%Y%m%d%H%M%S'))
    with open(index_file, 'w') as f:
        f.write(txt_header)

    if df is None:
        log.debug("Computing profile index from simulation file: %s" % simu_file)
        engine = 'zarr' if '.zarr' in simu_file else 'netcdf4'
        ds = xr.open_dataset(simu_file, engine=engine)
        ardf = simu2index(ds)
        # try:
        #     ardf = simu2index_par(xr.open_dataset(simu_file))
        # except ValueError:
        #     ardf = simu2index(xr.open_dataset(simu_file))
    else:
        ardf = df.copy()

    if len(ardf) > 0:
        log.debug("Writing profile index file: %s" % index_file)
        with open(index_file, 'a+') as f:
            ardf['institution'] = 'VF'  # VirtualFleet
            ardf['profiler_type'] = 999  # Reserved
            ardf['ocean'] = 'A'  # Atlantic ocean area
            ardf['date_update'] = pd.to_datetime('now', utc=True)
            ardf['file'] = ardf.apply(
                lambda row: "vf/%i/profiles/R%i_%0.2d.nc" % (row['wmo'], row['wmo'], row['cycle_number']), axis=1)
            ardf = ardf[['file', 'date', 'latitude', 'longitude', 'ocean', 'profiler_type', 'institution', 'date_update']]
            ardf.to_csv(f, index=False, date_format='%Y%m%d%H%M%S')

    return index_file


def set_WMO(ds: xr.Dataset, argo_index: pd.DataFrame):
    """Identify virtual floats with their real WMO

    This function will try to identify WMO from ``argo_index`` in the ``ds`` trajectories.

    The Argo index must have at least the ``longitude`` and ``latitude`` variables.
    It's assumed to be the deployment plan.

    Real WMO numbers are identified as the closest floats from ``argo_index`` to the initial positions
    of virtual floats from ``ds``.

    Parameters
    ----------
    ds: :class:`xarray.Dataset`
        The simulation trajectories dataset
    argo_index: :class:`pandas.DataFrame`
        The deployment plan profiles index

    Returns
    -------
    ds: :class:`xarray.Dataset`
        The simulation trajectories dataset with a new variable ``wmo``

    """
    ds['wmo'] = xr.DataArray(np.full((len(ds['traj']),), 0), dims='traj')
    wmos = []

    x_real = np.round(argo_index['longitude'], 5).values
    y_real = np.round(argo_index['latitude'], 5).values
    for i in ds['traj']:
        this = ds.isel(traj=i).sortby('time')
        x_virt = np.round(this.sel(obs=0)['lon'], 3).values
        y_virt = np.round(this.sel(obs=0)['lat'], 3).values
        ii = np.argmin(np.sqrt(np.power(x_real - x_virt, 2) + np.power(y_real - y_virt, 2)))
        wmo = np.array((argo_index.iloc[ii]['wmo'],))[0]
        wmos.append(wmo)
    ds['wmo'].values = wmos

    return ds


def get_float_config(wmo: int, cyc: int = None):
    """Download float configuration using the Euro-Argo meta-data API

    Parameters
    ----------
    wmo: int
        The float WMO number
    cyc: int, default: None
        The specific cycle number to retrieve data from. If set to None, all cycles meta-data are fetched.

    Returns
    -------
    :class:`pandas.DataFrame`
        A dataframe with relevant float configuration parameters for 1 or more cycle numbers.
    """

    def id_mission(missionCycles, a_cyc):
        this_mission = None
        for im, mission in enumerate(missionCycles):
            cycles = missionCycles[mission]
            if str(a_cyc) in cycles:
                this_mission = mission
        return this_mission

    # Download float meta-data from EA API:
    URI = "https://fleetmonitoring.euro-argo.eu/floats/%s" % wmo
    with urllib.request.urlopen(URI) as url:
        data = json.load(url)

    # data['configurations']['cycles'] -> dict
    #    keys (str): comma separated list of cycle numbers
    #                Eg: '14,15,22'
    #    values (list of dict): items of the list are one parameter description and value as a dict.
    #                Eg: {'argoCode': 'CONFIG_AscentSpeedMin_mm/s', 'dimLevel': 7, 'value': 83.0, 'description': None}

    # data['configurations']['missionCycles'] -> dict
    #    keys (str): configuration ID
    #                Eg: '24'
    #    values (list of str): items of the list are cycle numbers, as str, with this configuration
    #                Eg: ['105', '78', '80', '83', '99', '108', '74', '93']

    # Get the list of cycles covered:
    all_cycles = []
    for mission in data['configurations']['missionCycles']:
        cycles = data['configurations']['missionCycles'][mission]
        cycles = np.sort([int(cyc) for cyc in cycles])
        [all_cycles.append(cyc) for cyc in cycles]
    all_cycles = np.sort(all_cycles)
    if cyc is not None:
        all_cycles = [cyc]

    # Create a dictionary with 'CONFIG_*' as keys
    # the CONFIG_MissionID is set manually, then we add all possible config keys by scanning all argoCode
    CONFIG = {'CONFIG_MissionID': []}
    for cyles_with_this_config in list(data['configurations']['cycles'].keys()):
        for item in data['configurations']['cycles'][cyles_with_this_config]:
            if cyc is not None:
                if cyc in [int(c) for c in cyles_with_this_config.split(',')]:
                    CONFIG[item['argoCode']] = []
            else:
                CONFIG[item['argoCode']] = []
    CONFIG = dict(sorted(CONFIG.items()))

    # Loop through all cycle numbers
    # for each cycle we identify the associated entry
    for icyc, a_cyc in enumerate(all_cycles):
        mission_id = id_mission(data['configurations']['missionCycles'], a_cyc)
        for im, cyles_with_this_config in enumerate(data['configurations']['cycles']):
            if a_cyc in [int(c) for c in cyles_with_this_config.split(',')]:
                this_config = data['configurations']['cycles'][cyles_with_this_config]
                for key in CONFIG:
                    if key in [item['argoCode'] for item in this_config]:
                        for item in this_config:
                            if item['argoCode'] == key:
                                if len(CONFIG[item[
                                    'argoCode']]) == icyc:  # issue: https://github.com/euroargodev/VirtualFleet/issues/26
                                    CONFIG[item['argoCode']].append(item['value'])
                    elif key == 'CONFIG_MissionID':
                        CONFIG['CONFIG_MissionID'].append(mission_id)
                    else:
                        CONFIG[key].append('')

    df = pd.DataFrame(CONFIG, index=all_cycles)
    df.index.name = 'CYCLE_NUMBER'

    return df


def strfdelta(tdelta, fmt='{D:02}d {H:02}h {M:02}m {S:02}s', inputtype='timedelta'):
    """Convert a datetime.timedelta object or a regular number to a custom-
    formatted string, just like the stftime() method does for datetime.datetime
    objects.

    The fmt argument allows custom formatting to be specified.  Fields can
    include seconds, minutes, hours, days, and weeks.  Each field is optional.

    Some examples:
        '{D:02}d {H:02}h {M:02}m {S:02}s' --> '05d 08h 04m 02s' (default)
        '{W}w {D}d {H}:{M:02}:{S:02}'     --> '4w 5d 8:04:02'
        '{D:2}d {H:2}:{M:02}:{S:02}'      --> ' 5d  8:04:02'
        '{H}h {S}s'                       --> '72h 800s'

    The inputtype argument allows tdelta to be a regular number instead of the
    default, which is a datetime.timedelta object.  Valid inputtype strings:
        's', 'seconds',
        'm', 'minutes',
        'h', 'hours',
        'd', 'days',
        'w', 'weeks'
    """

    # Convert tdelta to integer seconds.
    if inputtype == 'timedelta':
        remainder = int(tdelta.total_seconds())
    elif inputtype in ['s', 'seconds']:
        remainder = int(tdelta)
    elif inputtype in ['m', 'minutes']:
        remainder = int(tdelta)*60
    elif inputtype in ['h', 'hours']:
        remainder = int(tdelta)*3600
    elif inputtype in ['d', 'days']:
        remainder = int(tdelta)*86400
    elif inputtype in ['w', 'weeks']:
        remainder = int(tdelta)*604800

    f = Formatter()
    desired_fields = [field_tuple[1] for field_tuple in f.parse(fmt)]
    possible_fields = ('W', 'D', 'H', 'M', 'S')
    constants = {'W': 604800, 'D': 86400, 'H': 3600, 'M': 60, 'S': 1}
    values = {}
    for field in possible_fields:
        if field in desired_fields and field in constants:
            values[field], remainder = divmod(remainder, constants[field])
    return f.format(fmt, **values)


def getSystemInfo():
    """Return system information as a dict"""
    try:
        info = {}
        info['platform']=platform.system()
        info['platform-release']=platform.release()
        info['platform-version']=platform.version()
        info['architecture']=platform.machine()
        info['hostname']=socket.gethostname()
        info['ip-address']=socket.gethostbyname(socket.gethostname())
        # info['mac-address']=':'.join(re.findall('..', '%012x' % uuid.getnode()))
        info['processor']=platform.processor()
        info['ram']=str(round(psutil.virtual_memory().total / (1024.0 **3)))+" GB"
        return info
    except Exception as e:
        logging.exception(e)
