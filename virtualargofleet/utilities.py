import collections
import numpy as np
import xarray as xr
from tqdm import tqdm
import concurrent.futures
import multiprocessing
import os
import pandas as pd
import logging
import json

log = logging.getLogger("virtualfleet.utils")


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

    def to_json(self):
        """Return a dictionary serialisable in json"""

        def meta_to_json(d):
            [d.update({key: self.str_val(val)}) for key, val in self.meta.items()]
            return d

        js = {self.key: {'value': self.value, 'meta': meta_to_json(self.meta.copy())}}
        return js

    value = property(get_value, set_value)


class FloatConfiguration:
    """Float mission configuration manager

    Create a default configuration and then possibly update parameter values or add new parameters

    Can be used to create a virtual fleet, to save or load float configurations

    Examples
    --------
    >>> cfg = FloatConfiguration('default')
    >>> cfg.update('parking_depth', 500)  # Update one parameter value
    >>> cfg.params  # Return the list of parameters
    >>> cfg.mission # Return the configuration as a dictionary
    >>> cfg

    """

    def __init__(self, name='default', *args, **kwargs):
        """

        Parameters
        ----------
        name: str
            Name of a known configuration to load
        """
        self._params_dict = {}
        def set_default():
            self.params = ConfigParam(key='profile_depth',
                                      value=2000.,
                                      unit='m',
                                      description='Maximum profile depth',
                                      techkey='CONFIG_ProfilePressure_dbar',
                                      dtype=float)

            self.params = ConfigParam(key='parking_depth',
                                      value=1000.,
                                      unit='m',
                                      description='Drifting depth',
                                      techkey='CONFIG_ParkPressure_dbar',
                                      dtype=float)

            self.params = ConfigParam(key='vertical_speed',
                                      value=0.09,
                                      unit='m/s',
                                      description='Vertical profiling speed',
                                      dtype=float)

            self.params = ConfigParam(key='cycle_duration',
                                      value=10 * 24.,
                                      unit='hours',
                                      description='Maximum length of float complete cycle',
                                      techkey='CONFIG_CycleTime_hours',
                                      dtype=float)

            self.params = ConfigParam(key='life_expectancy',
                                      value=200,
                                      unit='cycle',
                                      description='Maximum number of completed cycle',
                                      techkey='CONFIG_MaxCycles_NUMBER',
                                      dtype=int)

        if name == 'default':
            set_default()

        elif name == 'gse-experiment':
            set_default()

            self.params = ConfigParam(key='area_cycle_duration',
                                      value=5 * 24,
                                      unit='hours',
                                      description='Maximum length of float complete cycle in AREA',
                                      techkey='CONFIG_CycleTime_hours',
                                      dtype=float)

            self.params = ConfigParam(key='area_parking_depth',
                                      value=1000.,
                                      unit='m',
                                      description='Drifting depth in AREA',
                                      techkey='CONFIG_ParkPressure_dbar',
                                      dtype=float)

            self.params = ConfigParam(key='area_xmin',
                                      value=-75,
                                      unit='deg_longitude',
                                      description='AREA Western bound',
                                      techkey='',
                                      dtype=float)

            self.params = ConfigParam(key='area_xmax',
                                      value=-48,
                                      unit='deg_longitude',
                                      description='AREA Eastern bound',
                                      techkey='',
                                      dtype=float)

            self.params = ConfigParam(key='area_ymin',
                                      value=33.,
                                      unit='deg_latitude',
                                      description='AREA Southern bound',
                                      techkey='',
                                      dtype=float)

            self.params = ConfigParam(key='area_ymax',
                                      value=45.5,
                                      unit='deg_latitude',
                                      description='AREA Northern bound',
                                      techkey='',
                                      dtype=float)

        elif os.path.splitext(name)[-1] == ".json":
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

        else:
            raise ValueError("Please give me a known configuration name ('default', 'gse-experiment') or a json file to load from !")

        self.name = name

    def __repr__(self):
        summary = ["<FloatConfiguration><%s>" % self.name]
        for p in self._params_dict.keys():
            summary.append("- %s" % str(self._params_dict[p]))
        return "\n".join(summary)

    @property
    def params(self):
        return sorted([self._params_dict[p].key for p in self._params_dict.keys()])

    @params.setter
    def params(self, param):
        if not isinstance(param, ConfigParam):
            raise ValueError("param must a 'ConfigParam' instance")
        if param.key not in self.params:
            self._params_dict[param.key] = param
            self._params_dict = collections.OrderedDict(sorted(self._params_dict.items()))

    def update(self, key, new_value):
        if key not in self.params:
            raise ValueError("Invalid parameter '%s' for configuration '%s'" % (key, self.name))
        self._params_dict[key].value = new_value
        return self

    @property
    def mission(self):
        """Return a dictionary with key/value of all parameters"""
        mission = {}
        for key in self._params_dict.keys():
            mission[key] = self._params_dict[key].value
        return mission

    def load_from_float(self):
        """Should be able to read simple parameters from a real float file"""
        pass

    def to_netcdf(self):
        """Should be able to save on file a float configuration"""
        pass

    def to_json(self, file_name=None):
        """Return or save json dump of configuration"""
        data = {}
        for p in self._params_dict.keys():
            data = {**data, **self._params_dict[p].to_json()}
        js = {}
        js['name'] = self.name
        js['version'] = "1.0"
        js['created'] = pd.to_datetime('now', utc=True).strftime('%Y%m%d%H%M%S')
        js['data'] = data
        if file_name is not None:
            with open(file_name, "w") as f:
                json.dump(js, f, indent=4)
        else:
            return js

    def from_netcdf(self):
        """Should be able to read from file a float configuration"""
        pass

    @property
    def tech(self):
        summary = ["<FloatConfiguration.Technical><%s>" % self.name]
        for p in self._params_dict.keys():
            if self._params_dict[p].meta['techkey'] != '':
                summary.append("- %s: %s" % (self._params_dict[p].meta['techkey'], self._params_dict[p].value))
        return "\n".join(summary)


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


def simu2index(ds, N = 1):
    """Convert a simulation dataset obs/traj to an Argo index of profiles

    Profiles are identified using the 'cycle_number' variable if available or 'cycle_phase' otherwise.

    A profile is identified if the last obs of a cycle_number sequence is in cycle_phase 3 or 4.
    A profile is identified if the last obs of a cycle_phase==3 sequence is separated by N days from the next sequence.
    """
    ds_list = []

    if 'cycle_number' in ds.data_vars:
        for traj in tqdm(ds['traj'], total=len(ds['traj'])):
            for cyc, grp in ds.sel(traj=traj).groupby(group='cycle_number'):
                ds_cyc = grp.isel(obs=-1)
                if ds_cyc['cycle_phase'] in [3, 4]:
                    ds_cyc['traj_id'] = xr.DataArray(np.full_like((1,), fill_value=traj.data), dims='obs')
                    ds_list.append(ds_cyc)
    else:
        for traj in tqdm(ds['traj'], total=len(ds['traj'])):
            for iphase, grp in ds.sel(traj=traj).groupby(group='cycle_phase'):
                if iphase == 3:
                    sub_grp = splitonprofiles(grp, N=N)
                    sub_grp['cycle_number'] = xr.DataArray(np.arange(1, len(sub_grp['obs']) + 1), dims='obs')
                    sub_grp['traj_id'] = xr.DataArray(np.full_like(sub_grp['obs'], fill_value=traj.data), dims='obs')
                    ds_list.append(sub_grp)

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


def simu2csv(simu_file, index_file=None, df=None):
    """Save simulation results profile index to file, as Argo index

    Argo profile index can be loaded with argopy.

    Parameters
    ----------
    simu_file: str
        Path to netcdf file of simulation results, to load profiles from
    index_file: str, optional
        Path to csf file to write index
    df: :class:Pandas.Dataframe, optional
        If provided, will use as profile index, otherwise, compute index from simu_file

    Returns
    -------
    str
        Path to Argo profile index
    """
    if index_file is None:
        index_file = simu_file.replace(".nc", "_ar_index_prof.txt")

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
        ardf = simu2index(xr.open_dataset(simu_file))
        # try:
        #     ardf = simu2index_par(xr.open_dataset(simu_file))
        # except ValueError:
        #     ardf = simu2index(xr.open_dataset(simu_file))
    else:
        ardf = df.copy()

    if len(ardf) > 0:
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


def set_WMO(ds, argo_index):
    """Identify virtual floats with their real WMO

    Parameters
    ----------
    ds
    argo_index
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

