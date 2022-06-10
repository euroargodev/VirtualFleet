import collections
import numpy as np
import xarray as xr


class ConfigParam:
    """Configuration parameter manager

    Create a key/value pair object with metadata description, unit and dtype.

    Examples
    --------
    >>> ConfigParam(key='profile_depth', value=2000.)
    >>> ConfigParam(key='profile_depth', value=2000., unit='m', description='Maximum profile depth', dtype=float)

    """
    def __init__(self, key, value, **kwargs):
        self.key = key
        self._value = value
        default_meta = {'description': '', 'unit': '', 'dtype': ''}
        self.meta = {**default_meta, **kwargs}
        if self.meta['dtype'] != '':
            self._value = self.meta['dtype'](self.value)

    def __repr__(self):
        desc = "" if self.meta['description'] == '' else "(%s)" % self.meta['description']
        unit = "" if self.meta['unit'] == '' else "[%s]" % self.meta['unit']
        return "%s %s: %s %s" % (self.key, desc, self.value, unit)

    def get_value(self):
        return self._value

    def set_value(self, value):
        if self.meta['dtype'] != '':
            value = self.meta['dtype'](value)
        self._value = value

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
        if name == 'default':
            self.params = ConfigParam(key='profile_depth', value=2000., unit='m',
                                      description='Maximum profile depth', dtype=float)
            self.params = ConfigParam(key='parking_depth', value=1000., unit='m',
                                      description='Drifting depth', dtype=float)
            self.params = ConfigParam(key='vertical_speed', value=0.09, unit='m/s',
                                      description='Vertical profiling speed', dtype=float)
            self.params = ConfigParam(key='cycle_duration', value=10., unit='day',
                                      description='Maximum length of float complete cycle', dtype=float)
            self.params = ConfigParam(key='life_expectancy', value=200, unit='cycle',
                                      description='Maximum number of completed cycle', dtype=int)

    def __repr__(self):
        summary = ["<FloatConfiguration>"]
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
            raise ValueError("Invalid parameter '%s'" % key)
        self._params_dict[key].value = new_value
        return self

    @property
    def mission(self):
        """Return a simple dictionary with key/value of all parameters"""
        mission = {}
        for key in self._params_dict.keys():
            mission[key] = self._params_dict[key].value
        return mission

    def load_from_float(self):
        """Should be able to read simple parameters from a real float file"""
        pass

    def save(self):
        """Should be able to save on file a float configuration"""
        pass

    def load(self):
        """Should be able to read from file a float configuration"""
        pass


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
        for traj in ds['traj']:
            for cyc, grp in ds.sel(traj=traj).groupby(group='cycle_number'):
                ds_cyc = grp.isel(obs=-1)
                if ds_cyc['cycle_phase'] in [3, 4]:
                    ds_cyc['traj_id'] = xr.DataArray(np.full_like((1,), fill_value=traj.data), dims='obs')
                    ds_list.append(ds_cyc)
    else:
        for traj in ds['traj']:
            for iphase, grp in ds.sel(traj=traj).groupby(group='cycle_phase'):
                if iphase == 3:
                    sub_grp = splitonprofiles(grp, N=N)
                    sub_grp['cycle_number'] = xr.DataArray(np.arange(1, len(sub_grp['obs'])), dims='obs')
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

