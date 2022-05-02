import collections


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


class FloatConfiguration():
    """Float mission configuration manager

    Create a default configuration and then possibly update parameter values or add new parameters

    Can be used to create a virtual fleet, to save or load float configurations

    Examples
    --------
    >>> cfg = FloatConfiguration('default')
    >>> cfg.update('parking_depth', 500)
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
            self.params = ConfigParam(key='cycle_duration', value=10, unit='day',
                                      description='Maximum length of float complete cycle', dtype=float)

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